import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.ai.chatbot.multilingual_nlp import multilingual_nlp_engine
from app.ai.chatbot.indic_nlp_engine import indic_nlp_engine

class EmergencyNLPParser:
    """
    AI Module 5: Emergency NLP Parser.
    Extracts structured relief entities (quantity, people count, urgency, food category,
    disaster type, location, and priority) from natural language disaster alerts across
    English, Kannada (ಕನ್ನಡ), Hindi (हिन्दी), Tamil (தமிழ்), and Telugu (తెలుగు).
    """

    def __init__(self):
        self.engine = multilingual_nlp_engine

    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parses raw natural language text and returns structured emergency parameters.
        """
        return self.extract_emergency_parameters(text)

    def extract_emergency_parameters(self, text: str) -> Dict[str, Any]:
        """
        Extracts structured parameters from an emergency message.
        Compatible with English and Indic scripts (Kannada, Hindi, Tamil, Telugu).
        """
        if not text or not text.strip():
            return {
                "food_type": "Assorted Meals",
                "quantity": 50,
                "food_quantity": 50,
                "number_of_people": 30,
                "beneficiaries": 30,
                "people_affected": 30,
                "urgency": "MEDIUM",
                "urgency_level": "MEDIUM",
                "disaster_type": "Community Relief",
                "emergency_type": "COMMUNITY_EMERGENCY",
                "location": "Mysuru",
                "language": "en",
                "priority": "MEDIUM",
                "confidence": 0.70
            }

        lang = self.engine.detect_language(text)
        intent, confidence = self.engine.classify_intent(text, lang)
        
        # Base multilingual extraction for language script, disaster type, and tokens
        multi_entities = self.engine.extract_entities(text)
        
        # High precision 12-factor Indic & English extraction
        indic_data = indic_nlp_engine.extract_entities(text)

        quantity = indic_data.get("food_quantity") or indic_data.get("quantity") or multi_entities.get("quantity") or 50
        people = indic_data.get("beneficiaries") or indic_data.get("number_of_people") or multi_entities.get("number_of_people") or 30
        
        # Urgency: if either engine detects critical, it's critical
        urgency_raw = multi_entities.get("urgency", "MEDIUM")
        if indic_data.get("urgency_level") == "CRITICAL" or urgency_raw == "CRITICAL":
            urgency = "CRITICAL"
        elif indic_data.get("urgency_level") == "HIGH" or urgency_raw == "HIGH":
            urgency = "HIGH"
        else:
            urgency = urgency_raw

        disaster_type = multi_entities.get("disaster_type") or "Community Relief"
        location = multi_entities.get("location") if multi_entities.get("location") != "Local Community" else (indic_data.get("delivery_location") or "Mysuru")
        food_type = indic_data.get("food_type") or multi_entities.get("food_type") or "cooked_meals"

        priority = self.calculate_priority({
            "number_of_people": people,
            "people_affected": people,
            "quantity": quantity,
            "urgency": urgency
        })

        # Calculate deadline
        now = datetime.now(timezone.utc)
        if priority == "CRITICAL" or str(urgency).upper() == "CRITICAL":
            deadline = now + timedelta(hours=3)
        elif priority == "HIGH" or str(urgency).upper() == "HIGH":
            deadline = now + timedelta(hours=8)
        else:
            deadline = now + timedelta(hours=24)

        res = dict(indic_data)
        res.update({
            "food_type": food_type,
            "quantity": quantity,
            "food_quantity": quantity,
            "number_of_people": people,
            "beneficiaries": people,
            "people_affected": people,
            "urgency": urgency,
            "urgency_level": str(urgency).upper(),
            "disaster_type": disaster_type,
            "emergency_type": "FLOOD" if "flood" in disaster_type.lower() else ("COMMUNITY_EMERGENCY" if "community" in disaster_type.lower() else disaster_type.upper()),
            "location": location,
            "language": lang,
            "detected_language": lang,
            "priority": priority,
            "deadline": deadline.isoformat(),
            "confidence": round(confidence, 3)
        })
        return res

    def calculate_priority(self, extracted_data: Dict[str, Any]) -> str:
        """
        Calculates dispatch priority based on urgency, people affected, and quantity.
        Returns: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'.
        """
        people = extracted_data.get("people_affected") or extracted_data.get("number_of_people") or 0
        urgency = str(extracted_data.get("urgency", "MEDIUM")).upper()
        quantity = extracted_data.get("quantity", 0)

        if urgency in ["CRITICAL", "IMMEDIATE"] or people >= 100 or quantity >= 500:
            return "CRITICAL"
        if urgency == "HIGH" or people >= 50 or quantity >= 200:
            return "HIGH"
        if people >= 20 or quantity >= 50:
            return "MEDIUM"
        return "LOW"

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Alias for extract_emergency_parameters."""
        return self.extract_emergency_parameters(text)

# Singleton parser instance
emergency_nlp_parser = EmergencyNLPParser()

# Convenience module-level helper functions
def parse_emergency_text(text: str) -> Dict[str, Any]:
    return emergency_nlp_parser.parse(text)

def parse_emergency_message(text: str) -> Dict[str, Any]:
    return emergency_nlp_parser.parse(text)

def extract_emergency_parameters(text: str) -> Dict[str, Any]:
    return emergency_nlp_parser.extract_emergency_parameters(text)
