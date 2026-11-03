from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from app.nlp.base import BaseEmergencyExtractor
from app.ai.chatbot.multilingual_nlp import multilingual_nlp_engine

class MultilingualMLEmergencyExtractor(BaseEmergencyExtractor):
    """
    AI Module 5 Supervised Multilingual Machine Learning Extractor.
    Extracts structured relief requirements across English, Kannada, Hindi, Tamil, and Telugu.
    """

    def extract(self, text: str) -> Dict[str, Any]:
        lang = multilingual_nlp_engine.detect_language(text)
        intent, confidence = multilingual_nlp_engine.classify_intent(text, lang)
        entities = multilingual_nlp_engine.extract_entities(text)

        urgency_str = entities.get("urgency", "MEDIUM")
        
        # Calculate intelligent deadline based on extracted urgency
        now = datetime.now(timezone.utc)
        if urgency_str == "CRITICAL":
            deadline = now + timedelta(hours=3)
        elif urgency_str == "HIGH":
            deadline = now + timedelta(hours=8)
        else:
            deadline = now + timedelta(hours=24)

        return {
            "food_type": entities.get("food_type", "Assorted Meals"),
            "quantity": entities.get("quantity", 50),
            "number_of_people": entities.get("number_of_people", 30),
            "location": entities.get("location", "Bangalore"),
            "emergency_type": entities.get("disaster_type", "Flood Relief"),
            "urgency": urgency_str,
            "deadline": deadline.isoformat(),
            "confidence": round(confidence, 3)
        }
