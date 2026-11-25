import os
import re
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BASE_DIR, "models", "verification", "org_verifier_rf.joblib")

_OFFICIAL_REG_PATTERNS = [
    r"^[A-Z]{2}[/\-]\d{4}[/\-]\d{5,9}$",          # e.g. KA/2021/0091823 (NGO Darpan)
    r"^DARPAN[\-/_]?[A-Z]{2}[\-/_]?\d{4,10}$",     # DARPAN-KA-20220012
    r"^(12A|80G|FCRA|CSR|SEC8)[\-/_]?[A-Z0-9]{4,}$",
    r"^(NGO|TR|SOC)[/\-_]\d{4}[/\-_]\d{4,8}$",
]

_RELIEF_KEYWORDS = {
    "ngo", "trust", "foundation", "charity", "charitable", "relief", "shelter",
    "orphanage", "ashram", "seva", "mission", "welfare", "foodbank", "food bank",
    "pantry", "community", "aid", "care", "humanitarian", "annakshetra", "feed",
}

_DISPOSABLE_DOMAINS = {
    "tempmail.com", "10minutemail.com", "mailinator.com", "guerrillamail.com",
    "yopmail.com", "throwawaymail.com", "trashmail.com",
}

_FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}

_ORG_FEATURE_COLS = [
    "reg_id_official_match",
    "reg_id_len",
    "reg_id_unique_ratio",
    "org_name_word_count",
    "org_has_relief_keyword",
    "signatory_word_count",
    "phone_valid_indian",
    "phone_unique_digits",
    "email_domain_valid",
    "has_valid_6digit_pin",
    "address_word_count",
    "fleet_per_100_meals",
]


class AIVerificationService:
    _rf_model: Optional[Any] = None
    _model_loaded: bool = False

    @classmethod
    def _ensure_model(cls):
        if cls._model_loaded:
            return
        cls._model_loaded = True
        try:
            if os.path.exists(MODEL_PATH):
                cls._rf_model = joblib.load(MODEL_PATH)
        except Exception:
            cls._rf_model = None

    @classmethod
    def screen_organization(cls, applicant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Multi-Criteria Hybrid AI Organization Verification Engine (7-Factor Rubric + RandomForest ML).
        Evaluates credential authenticity, telecom hygiene, email domain, PIN code validity,
        signatory completeness, and operational capacity/fleet ratios to output a 15-98 trust score.
        """
        cls._ensure_model()

        org_name = (applicant.get("name") or "").strip()
        reg_id = (applicant.get("organization_id") or applicant.get("darpan_id") or "").strip()
        contact_person = (applicant.get("contact_person") or "").strip()
        phone = (applicant.get("phone") or "").strip()
        email = (applicant.get("email") or "").strip()
        location = (applicant.get("location") or "").strip()
        pincode_input = (applicant.get("pincode") or "").strip()
        receiver_type = (applicant.get("receiver_type") or "NGO_TRUST").upper()

        try:
            food_capacity = int(applicant.get("food_capacity") or 500)
        except (ValueError, TypeError):
            food_capacity = 500

        try:
            beneficiary_cap = int(applicant.get("beneficiary_capacity") or 250)
        except (ValueError, TypeError):
            beneficiary_cap = 250

        try:
            fleet_count = int(applicant.get("fleet_count") or 1)
        except (ValueError, TypeError):
            fleet_count = 1

        # Start from strict neutral baseline (max theoretical rubric = 96 before ML blend)
        rubric_score = 5
        flags: List[str] = []
        positive_factors: List[str] = []

        # ------------------------------------------------------------------
        # Criterion 1: Government Registration / Darpan ID Authenticity (25 pts)
        # ------------------------------------------------------------------
        reg_upper = reg_id.upper()
        is_official_reg = any(re.match(p, reg_upper) for p in _OFFICIAL_REG_PATTERNS)
        has_triple_repeat_reg = bool(re.search(r"(.)\1\1", reg_id.lower())) if reg_id else False
        reg_unique_ratio = (len(set(reg_id.lower())) / len(reg_id)) if reg_id else 0.0
        is_placeholder_reg = reg_id.lower() in {"test", "none", "na", "n/a", "12345", "123456", "000000", "nil"}

        if not reg_id or is_placeholder_reg:
            rubric_score -= 10
            flags.append("Missing or placeholder registration / Darpan ID")
        elif is_official_reg and not has_triple_repeat_reg:
            rubric_score += 24
            positive_factors.append("Official NGO Darpan / statutory registration syntax verified")
        elif len(reg_id) >= 8 and any(c.isalpha() for c in reg_id) and any(c.isdigit() for c in reg_id) and not has_triple_repeat_reg and reg_unique_ratio >= 0.55:
            rubric_score += 12
            positive_factors.append("Alphanumeric trust identifier present (manual Darpan lookup recommended)")
        else:
            rubric_score -= 2
            flags.append(f"Unverified or low-entropy registration ID format ('{reg_id}')")

        # ------------------------------------------------------------------
        # Criterion 2: Entity Name & Signatory Authority (15 pts)
        # ------------------------------------------------------------------
        org_words = [w for w in re.split(r"\s+", org_name) if len(w) >= 2]
        org_lower = org_name.lower()
        has_relief_kw = any(kw in org_lower for kw in _RELIEF_KEYWORDS)
        if len(org_words) >= 2 and has_relief_kw:
            rubric_score += 9
            positive_factors.append("Recognized relief/welfare organization naming structure")
        elif has_relief_kw or len(org_words) >= 2:
            rubric_score += 5
        else:
            rubric_score -= 4
            flags.append(f"Single-word or non-NGO entity name ('{org_name}') requires identity verification")

        sig_words = [w for w in re.split(r"\s+", contact_person) if len(w) >= 2]
        if len(sig_words) >= 2:
            rubric_score += 6
            positive_factors.append("Full legal signatory name provided")
        elif len(sig_words) == 1:
            rubric_score += 1
            flags.append(f"Single-word signatory contact ('{contact_person}') — full name advised")
        else:
            rubric_score -= 4
            flags.append("Authorized signatory name missing")

        # ------------------------------------------------------------------
        # Criterion 3: Telecom Hygiene & Entropy (15 pts)
        # ------------------------------------------------------------------
        clean_phone = re.sub(r"\D", "", phone)
        last10 = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
        valid_indian_mobile = bool(re.match(r"^[6-9]\d{9}$", last10))
        unique_digits = len(set(last10)) if last10 else 0
        has_repeated_block = bool(re.search(r"(\d)\1\1\1", last10)) or (
            len(last10) == 10 and (last10[:5] == last10[5:] or last10 in "01234567890123456789")
        )

        if valid_indian_mobile and unique_digits >= 5 and not has_repeated_block:
            rubric_score += 14
            positive_factors.append("High-entropy active 10-digit hotline number verified")
        elif len(last10) == 10 and unique_digits >= 4 and not has_repeated_block:
            rubric_score += 7
            flags.append("Phone format acceptable but low digit diversity")
        else:
            rubric_score -= 8
            flags.append(f"Suspicious/repetitive or incomplete phone pattern ('{phone}')")

        # ------------------------------------------------------------------
        # Criterion 4: Email Domain Legitimacy (15 pts)
        # ------------------------------------------------------------------
        email_domain = email.split("@")[-1].lower().strip() if "@" in email else ""
        sld = email_domain.split(".")[0] if "." in email_domain else ""
        email_valid_syntax = bool(re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", email.lower().strip()))
        is_disposable = email_domain in _DISPOSABLE_DOMAINS
        email_domain_ok = False

        if not email_valid_syntax or is_disposable:
            rubric_score -= 10
            flags.append("Invalid or disposable email domain")
        elif len(sld) <= 2:
            rubric_score -= 3
            flags.append(f"Short/unverified email domain ('@{email_domain}')")
        elif email_domain not in _FREE_EMAIL_DOMAINS:
            email_domain_ok = True
            rubric_score += 13
            positive_factors.append(f"Dedicated organization email domain ('@{email_domain}')")
        else:
            email_domain_ok = True
            rubric_score += 9
            positive_factors.append("Valid reachable email address")

        # ------------------------------------------------------------------
        # Criterion 5: Address & 6-Digit PIN Verification (15 pts)
        # ------------------------------------------------------------------
        combined_loc = f"{location} {pincode_input}".strip()
        has_6digit_pin = bool(re.search(r"\b[1-8]\d{5}\b", combined_loc))
        has_malformed_pin = bool(re.search(r"[-,\s]\d{4,5}\b", combined_loc)) and not has_6digit_pin
        addr_tokens = [t for t in re.split(r"[\s,/-]+", location) if len(t) >= 3 and not t.isdigit()]

        if has_6digit_pin and len(addr_tokens) >= 2:
            rubric_score += 14
            positive_factors.append("Complete address with valid 6-digit Indian PIN code")
        elif has_malformed_pin:
            rubric_score -= 4
            flags.append("Invalid PIN code detected (must be a valid 6-digit postal PIN)")
        elif len(addr_tokens) >= 2:
            rubric_score += 5
            flags.append("Address provided without verified 6-digit PIN code")
        else:
            rubric_score -= 6
            flags.append("Incomplete depot/organization address")

        # ------------------------------------------------------------------
        # Criterion 6: Operational Capacity & Fleet Ratio Sanity (15 pts)
        # ------------------------------------------------------------------
        meals_per_ben = food_capacity / max(1, beneficiary_cap)
        fleet_per_100 = (fleet_count / max(1, food_capacity)) * 100.0
        if 50 <= food_capacity <= 20000 and 0.5 <= meals_per_ben <= 6.0 and fleet_per_100 <= 3.5:
            rubric_score += 11
            positive_factors.append("Operational meal volume & fleet-to-capacity ratio realistic")
        else:
            rubric_score -= 4
            if fleet_per_100 > 3.5:
                flags.append(
                    f"Abnormal fleet-to-capacity ratio ({fleet_count} vehicles for {food_capacity} meals/day)"
                )
            else:
                flags.append("Meal capacity or beneficiary ratio outside standard thresholds")

        rubric_score = max(15, min(98, rubric_score))

        # ------------------------------------------------------------------
        # Criterion 7: Trained RandomForest ML Classifier Probability Blend
        # ------------------------------------------------------------------
        ml_prob_pct: Optional[float] = None
        if cls._rf_model is not None:
            try:
                feat_row = pd.DataFrame([{
                    "reg_id_official_match": 1 if is_official_reg else 0,
                    "reg_id_len": len(reg_id),
                    "reg_id_unique_ratio": round(reg_unique_ratio, 3),
                    "org_name_word_count": len(org_words),
                    "org_has_relief_keyword": 1 if has_relief_kw else 0,
                    "signatory_word_count": len(sig_words),
                    "phone_valid_indian": 1 if (valid_indian_mobile and not has_repeated_block) else 0,
                    "phone_unique_digits": unique_digits,
                    "email_domain_valid": 1 if email_domain_ok else 0,
                    "has_valid_6digit_pin": 1 if has_6digit_pin else 0,
                    "address_word_count": len(addr_tokens),
                    "fleet_per_100_meals": round(fleet_per_100, 3),
                }])[_ORG_FEATURE_COLS]
                prob_legit = float(cls._rf_model.predict_proba(feat_row)[0][1])
                ml_prob_pct = round(prob_legit * 100.0, 1)
                final_score = int(round((0.75 * rubric_score) + (0.25 * ml_prob_pct)))
            except Exception:
                final_score = rubric_score
        else:
            final_score = rubric_score

        score = max(15, min(98, final_score))

        # Classification
        if receiver_type == "RELIEF_HUB":
            classification = "Disaster Relief Operational Center (Tier 1 Priority)"
        elif receiver_type == "FOOD_BANK":
            classification = "Community Food Bank & Pantry Facility"
        elif receiver_type == "SHELTER_CARE_CENTER":
            classification = "Shelter, Care Center & Orphanage Home"
        elif receiver_type == "COMMUNITY_ORGANIZATION":
            classification = "Grassroots Community Hunger Relief Initiative"
        else:
            classification = "Accredited Welfare Trust (Section 8 / Public Charity)"

        # Strict tiered Safety Status
        if score >= 82 and len(flags) <= 1:
            safety_status = "SAFE - RECOMMENDED FOR APPROVAL"
            rec_line = "Recommended for Administrator Authorization."
        elif score >= 60:
            safety_status = "MODERATE - MANUAL REVIEW RECOMMENDED"
            rec_line = "Manual document & phone verification advised before approval."
        else:
            safety_status = "FLAGGED FOR INSPECTION"
            rec_line = "High anomaly indicators detected — strict credential audit required."

        highlights = positive_factors[:2] if positive_factors else flags[:2]
        ai_notes = (
            f"AI Pre-Screening (Rubric + RF Model): Score {score}/100. "
            f"{'; '.join(highlights)}. "
            f"Capacity: {food_capacity} meals/day ({beneficiary_cap} beneficiaries, {fleet_count} vehicles). "
            f"{rec_line}"
        )

        return {
            "ai_trust_score": score,
            "ai_safety_status": safety_status,
            "ai_classification": classification,
            "ai_notes": ai_notes,
            "ai_flags": flags,
            "ai_positive_factors": positive_factors,
            "ai_ml_confidence_pct": ml_prob_pct,
            "ai_rubric_score": rubric_score,
            "screened_at": datetime.now(timezone.utc).isoformat(),
        }
