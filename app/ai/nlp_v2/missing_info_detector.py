"""
FoodBridge NLP V2 — Missing Information Detection & Natural Clarification Generator
Validates field completeness against transaction schemas and generates human-like
clarification prompts for incomplete requests.
"""

from typing import Dict, List, Any, Optional

class MissingInfoDetector:
    """Detects missing mandatory fields and synthesizes targeted clarification questions."""

    def evaluate(self, intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates completeness of parsed entities based on intent requirements.
        """
        missing_fields: List[str] = []

        is_offer = intent in ["FOOD_DONATION_OFFER", "GROCERY_DONATION", "WATER_DONATION"]
        is_request = intent in [
            "FOOD_DONATION_REQUEST", "EMERGENCY_FOOD_REQUEST", "FOOD_SHORTAGE",
            "GROCERY_REQUIREMENT", "WATER_REQUIREMENT"
        ]
        is_emergency = intent in ["EMERGENCY_FOOD_REQUEST", "FOOD_SHORTAGE"]
        is_query_or_meta = intent in [
            "DONATION_STATUS_QUERY", "DONATION_CANCELLATION", "GENERAL_INFORMATION",
            "UNKNOWN_OR_UNSUPPORTED", "DONATION_UPDATE", "DONATION_CORRECTION"
        ]

        # For queries, cancellations, or unsupported intents, food item / quantity fields are not required
        if is_query_or_meta:
            return {
                "is_complete": True,
                "missing_fields": [],
                "clarification_question": None
            }

        items = entities.get("items", [])
        total_quantity = entities.get("total_quantity", 0)
        location = entities.get("location")
        beneficiary_count = entities.get("beneficiary_count") or 0

        # Field Checks
        # 1. Food items or category check
        if not items and not entities.get("primary_item_name"):
            missing_fields.append("food_type")

        # 2. Quantity check (either food quantity or number of people/beneficiaries)
        if total_quantity <= 0 and beneficiary_count <= 0:
            missing_fields.append("quantity")

        # 3. Location check
        if not location or str(location).strip().lower() in ["none", "null", ""]:
            missing_fields.append("location")

        # 4. Emergency specific checks
        if is_emergency and beneficiary_count <= 0 and total_quantity <= 0:
            if "quantity" not in missing_fields:
                missing_fields.append("beneficiary_count")

        is_complete = len(missing_fields) == 0

        # Generate contextual clarification question
        clarification_question = self._generate_clarification_question(
            is_offer=is_offer,
            is_emergency=is_emergency,
            missing_fields=missing_fields
        ) if not is_complete else None

        return {
            "is_complete": is_complete,
            "missing_fields": missing_fields,
            "clarification_question": clarification_question
        }

    def _generate_clarification_question(
        self,
        is_offer: bool,
        is_emergency: bool,
        missing_fields: List[str]
    ) -> str:
        """Constructs a polite, natural English clarification prompt."""
        m_set = set(missing_fields)

        if is_emergency:
            if "quantity" in m_set and "location" in m_set:
                return "This sounds urgent. Could you please provide your exact location and the number of people who need food assistance immediately?"
            if "location" in m_set:
                return "Please share your current location or landmark so our emergency relief dispatch team can reach you quickly."
            if "quantity" in m_set or "beneficiary_count" in m_set:
                return "How many people require immediate food assistance, or how many meals are needed?"

        if is_offer:
            if "food_type" in m_set and "quantity" in m_set and "location" in m_set:
                return "Thank you for wanting to donate! Could you please tell us what food items you have, how much quantity, and your pickup location?"
            if "quantity" in m_set and "location" in m_set:
                return "Thank you for your donation offer! Approximately how many meals or kilograms are available, and where can our volunteer pick them up?"
            if "location" in m_set:
                return "Great! Where should our volunteer or NGO team come to collect the donation?"
            if "quantity" in m_set:
                return "Approximately how many meals, packets, or kilograms would you like to donate?"
            if "food_type" in m_set:
                return "Could you specify what kind of food or grocery you have available for donation?"

        # Default requirement prompts
        if "food_type" in m_set and "quantity" in m_set and "location" in m_set:
            return "Please provide details on what food or ration items are needed, the required quantity, and your delivery area."
        if "quantity" in m_set and "location" in m_set:
            return "How many meals or people need support, and what is your location or community center address?"
        if "location" in m_set:
            return "What is the delivery or distribution location for this request?"
        if "quantity" in m_set:
            return "How many meals, food packets, or people require assistance?"
        if "food_type" in m_set:
            return "What type of food (cooked meals, dry groceries, or drinking water) is required?"

        return "Please provide more details regarding the required quantity and location to proceed."


missing_info_detector = MissingInfoDetector()
