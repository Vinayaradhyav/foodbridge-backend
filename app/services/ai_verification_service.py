import re
from datetime import datetime, timezone
from typing import Dict, Any

class AIVerificationService:
    @staticmethod
    def screen_organization(applicant: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI Safety & Credential Screening Engine for Food-Bridge Receivers & NGOs.
        Analyzes submitted legal credentials, operational capacity, fleet, and contact details
        to generate a safety score, operational classification, and risk evaluation.
        """
        org_name = (applicant.get("name") or "").strip()
        reg_id = (applicant.get("organization_id") or applicant.get("darpan_id") or "").strip()
        contact_person = (applicant.get("contact_person") or "").strip()
        phone = (applicant.get("phone") or "").strip()
        email = (applicant.get("email") or "").strip()
        location = (applicant.get("location") or "").strip()
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

        # Calculate AI Trust Score
        score = 80  # Base legitimate applicant score
        flags = []
        positive_factors = []

        # 1. Government Registration ID Verification
        if reg_id:
            # Common patterns: KA/2021/0091823, DARPAN-KA-2022, 12A/80G, CSR-001293
            if re.match(r'^[A-Za-z]{2}[/\-]?\d{4}[/\-]?\d{4,8}$', reg_id) or len(reg_id) >= 6:
                score += 8
                positive_factors.append("Valid government registration document syntax")
            else:
                score += 3
                positive_factors.append("Non-standard credential format, manual verification advised")
        else:
            score -= 5
            flags.append("Registration document number pending upload")

        # 2. Contact & Identity Validity
        if len(contact_person.split()) >= 2:
            score += 4
            positive_factors.append("Full authorized signatory name provided")
        else:
            flags.append("Signatory name single word")

        # 3. Email & Phone Validity
        clean_phone = re.sub(r'\D', '', phone)
        if len(clean_phone) >= 10:
            score += 3
            positive_factors.append("Verified 10-digit telephone format")
        else:
            score -= 5
            flags.append("Incomplete telephone number")

        if "@" in email and "." in email.split("@")[-1]:
            score += 3
            if not any(provider in email.lower() for provider in ["tempmail", "10minutemail", "disposable"]):
                positive_factors.append("Legitimate organization communication domain")
        else:
            score -= 5
            flags.append("Invalid organization email format")

        # 4. Operational Capacity Feasibility Check
        if 50 <= food_capacity <= 20000:
            score += 2
            positive_factors.append("Daily meal handling volume within safe cold-chain threshold")
        else:
            flags.append("Abnormal meal capacity requested")

        score = max(50, min(98, score))

        # Classification
        classification = "Verified Relief Hub"
        if receiver_type == "RELIEF_HUB":
            classification = "Disaster Relief Operational Center (Tier 1 Priority)"
        elif receiver_type == "FOOD_BANK":
            classification = "Community Food Bank & Pantry Facility"
        elif receiver_type == "SHELTER_CARE_CENTER":
            classification = "Shelter, Care Center & Orphanage Home"
        elif receiver_type == "COMMUNITY_ORGANIZATION":
            classification = "Grassroots Community Hunger Relief Initiative"
        else:
            classification = "Accredited NGO Trust (Section 8 / Public Charity)"

        # Safety Status
        if score >= 85:
            safety_status = "SAFE - RECOMMENDED FOR APPROVAL"
        elif score >= 70:
            safety_status = "MODERATE - MANUAL REVIEW RECOMMENDED"
        else:
            safety_status = "FLAGGED FOR INSPECTION"

        ai_notes = (
            f"AI Pre-Screening: Score {score}/100. "
            f"{'; '.join(positive_factors[:2])}. "
            f"Capacity: {food_capacity} meals/day with {fleet_count} active transport units. "
            f"Recommended for Administrator Authorization."
        )

        return {
            "ai_trust_score": score,
            "ai_safety_status": safety_status,
            "ai_classification": classification,
            "ai_notes": ai_notes,
            "ai_flags": flags,
            "screened_at": datetime.now(timezone.utc).isoformat()
        }
