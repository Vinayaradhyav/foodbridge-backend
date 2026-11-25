from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from app.nlp.base import BaseEmergencyExtractor
from app.ai.chatbot.indic_nlp_engine import indic_nlp_engine

class MultilingualMLEmergencyExtractor(BaseEmergencyExtractor):
    """
    AI Module: Supervised Multilingual Machine Learning Extractor.
    Extracts structured relief requirements across English, Kannada, Hindi, and Code-Mixed text.
    """

    def extract(self, text: str) -> Dict[str, Any]:
        data = indic_nlp_engine.extract_entities(text)

        urgency_str = str(data.get("urgency_level") or data.get("urgency") or "HIGH").upper()
        now = datetime.now(timezone.utc)
        if urgency_str == "CRITICAL":
            deadline = now + timedelta(hours=3)
        elif urgency_str == "HIGH":
            deadline = now + timedelta(hours=8)
        else:
            deadline = now + timedelta(hours=24)

        data["deadline"] = deadline.isoformat()
        if not data.get("food_type"):
            data["food_type"] = data.get("food_name") or data.get("food_category") or "Cooked Meals"
        data["location"] = data.get("delivery_location")
        if data.get("delivery_coordinates"):
            data["delivery_coordinates"] = list(data["delivery_coordinates"])

        return data
