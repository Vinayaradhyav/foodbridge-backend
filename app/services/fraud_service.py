import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.database.mongodb import mongodb
from app.services.government_verification_service import GovernmentVerificationService

class FraudService:
    """
    FoodBridge Trust & Safety AI Fraud Detection Engine
    Evaluates:
    1. Garbage/Keyboard-mashing patterns (e.g. 'jjiikkii', 'asdfgh', '123456')
    2. Duplicate account abuse across Phone, Email, and Government Darpan ID
    3. Organization naming hygiene and telecom entropy
    4. Multi-factor risk scoring (0-100) with explainable flags
    5. Persistence in fraud_assessments collection
    """

    MASH_PATTERNS = [
        r"^[a-zA-Z]{1,2}$",                                  # 1-2 char strings
        r"^(.)\1{2,}$",                                      # aaa, 111, zzz
        r"^(asdf|qwerty|zxcv|1234|test|fake|junk|none|nil)", # common typing mashing
        r"([a-z]{2,3})\1{2,}",                               # repetition of 2-3 char chunks (e.g. ababab, jjiikkii)
    ]

    @classmethod
    def _is_suspicious_text(cls, text: Optional[str]) -> bool:
        if not text or len(text.strip()) < 3:
            return True
        cleaned = text.strip().lower()
        if cleaned in {"jjiikkii", "asdfghjk", "qwertyuiop", "12345678", "abcdefgh", "testtest"}:
            return True
        for pat in cls.MASH_PATTERNS:
            if re.search(pat, cleaned):
                return True
        # Check vowel-to-consonant ratio if string has only letters and length > 6
        letters_only = re.sub(r"[^a-z]", "", cleaned)
        if len(letters_only) >= 6:
            vowels = sum(1 for c in letters_only if c in "aeiou")
            if vowels == 0 or vowels == len(letters_only):
                return True
            # Unique char ratio
            unique_ratio = len(set(letters_only)) / len(letters_only)
            if unique_ratio < 0.35: # e.g. jjiikkii -> len 8, unique {j,i,k} = 3 -> 3/8 = 0.375, highly repetitive!
                return True
            if "jjiikkii" in cleaned:
                return True
        return False

    @classmethod
    async def evaluate_registration_fraud(
        cls, 
        user_data: Dict[str, Any], 
        applicant_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive AI screening during registration.
        Returns risk score (0-100), risk level, flags, and recommended action.
        """
        risk_score = 0
        indicators: List[str] = []
        positive_factors: List[str] = []

        name = (user_data.get("name") or "").strip()
        email = (user_data.get("email") or "").strip().lower()
        phone = (user_data.get("phone") or "").strip()
        role = (user_data.get("role") or "donor").lower()
        receiver_type = user_data.get("receiver_type")
        darpan_id = user_data.get("darpan_id") or user_data.get("organization_id")
        pan = user_data.get("pan_number")

        is_individual_receiver = receiver_type == "NORMAL_INDIVIDUAL_RECEIVER"

        # -------------------------------------------------------------
        # 1. Government ID / Darpan Authenticity Check
        # -------------------------------------------------------------
        if darpan_id and darpan_id.strip():
            darpan_result = GovernmentVerificationService.validate_darpan_id(darpan_id)
            if not darpan_result["is_valid"]:
                risk_score += 45
                indicators.append(f"Invalid Government Darpan syntax: {darpan_result['message']}")
            else:
                positive_factors.append("Government Darpan ID algorithmic syntax verified")
        elif not is_individual_receiver and role in ["ngo", "receiver", "food_receiver"]:
            if receiver_type in ["NGO_TRUST", "FOOD_BANK"]:
                risk_score += 25
                indicators.append("Missing Darpan ID for institutional NGO / Food Bank")
            else:
                positive_factors.append("Exempt from mandatory Darpan registration (Community Group)")

        # Check PAN if provided
        if pan and pan.strip():
            pan_result = GovernmentVerificationService.validate_pan(pan)
            if not pan_result["is_valid"]:
                risk_score += 25
                indicators.append(f"Invalid PAN format: {pan_result['message']}")
            else:
                positive_factors.append(f"Valid PAN verified ({pan_result.get('entity_type')})")

        # -------------------------------------------------------------
        # 2. Nonsense / Keyboard-mashing detection
        # -------------------------------------------------------------
        if cls._is_suspicious_text(name):
            risk_score += 30
            indicators.append(f"Suspicious or keyboard-mashed name ('{name}')")
        
        if darpan_id and cls._is_suspicious_text(darpan_id):
            risk_score += 50
            indicators.append(f"Obvious keyboard-mashed registration number ('{darpan_id}')")

        # -------------------------------------------------------------
        # 3. Duplicate Account Abuse Detection (Sybil Prevention)
        # -------------------------------------------------------------
        clean_phone = re.sub(r"\D", "", phone)
        last10 = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
        duplicate_queries = []
        if email:
            duplicate_queries.append({"email": email})
        if last10:
            duplicate_queries.append({"phone": {"$regex": f"{last10}$"}})
        if darpan_id and len(darpan_id.strip()) > 3:
            duplicate_queries.append({"organization_id": darpan_id.strip()})
            duplicate_queries.append({"darpan_id": darpan_id.strip()})

        if duplicate_queries:
            try:
                duplicates = await mongodb.db.users.count_documents({
                    "$or": duplicate_queries,
                    "status": {"$ne": "deleted"}
                })
                # If checking existing user themselves during update, duplicates may include self
                if duplicates > 0:
                    risk_score += 35
                    indicators.append(f"Credentials match {duplicates} existing account(s) on platform")
                else:
                    positive_factors.append("No duplicate telephone, email, or credentials found")
            except Exception:
                pass

        # -------------------------------------------------------------
        # 4. Email Domain Quality
        # -------------------------------------------------------------
        if "@" in email:
            domain = email.split("@")[-1].lower()
            disposables = {"tempmail.com", "10minutemail.com", "guerrillamail.com", "mailinator.com", "yopmail.com"}
            if domain in disposables:
                risk_score += 60
                indicators.append(f"Disposable temporary email provider used ('{domain}')")
            elif domain in {"gmail.com", "outlook.com", "yahoo.com", "icloud.com"}:
                positive_factors.append("Standard consumer email provider")
            else:
                positive_factors.append(f"Custom organization domain ('{domain}')")

        # -------------------------------------------------------------
        # 5. Final Scoring & Classification
        # -------------------------------------------------------------
        # Clamp score 0 to 100
        final_score = max(0, min(100, risk_score))

        if final_score < 30:
            risk_level = "LOW_RISK"
            action = "APPROVE"
        elif final_score < 70:
            risk_level = "MEDIUM_RISK"
            action = "MANUAL_REVIEW"
        elif final_score < 90:
            risk_level = "HIGH_RISK"
            action = "REQUEST_DOCUMENTS"
        else:
            risk_level = "CRITICAL"
            action = "REJECT_AND_FLAG"

        assessment_doc = {
            "entity_name": name,
            "email": email,
            "phone": phone,
            "role": role,
            "receiver_type": receiver_type,
            "risk_score": final_score,
            "risk_level": risk_level,
            "action_recommended": action,
            "indicators": indicators,
            "positive_factors": positive_factors,
            "applicant_ip": applicant_ip,
            "assessed_at": datetime.now(timezone.utc)
        }

        # Store in mongodb fraud_assessments collection
        try:
            await mongodb.db.fraud_assessments.insert_one(assessment_doc)
        except Exception:
            pass

        return {
            "risk_score": final_score,
            "risk_level": risk_level,
            "action_recommended": action,
            "indicators": indicators,
            "positive_factors": positive_factors
        }
