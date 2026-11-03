from app.nlp.base import BaseEmergencyExtractor
from app.nlp.rule_extractor import RuleBasedEmergencyExtractor
from app.nlp.ml_extractor import MultilingualMLEmergencyExtractor

class ExtractorFactory:
    _rule_instance = None
    _ml_instance = None

    @classmethod
    def get_extractor(cls, model_type: str = "ml") -> BaseEmergencyExtractor:
        if model_type in ["ml", "multilingual", "chatbot"]:
            if not cls._ml_instance:
                cls._ml_instance = MultilingualMLEmergencyExtractor()
            return cls._ml_instance
        elif model_type == "rule_based":
            if not cls._rule_instance:
                cls._rule_instance = RuleBasedEmergencyExtractor()
            return cls._rule_instance
        else:
            # Fallback to ML extractor
            if not cls._ml_instance:
                cls._ml_instance = MultilingualMLEmergencyExtractor()
            return cls._ml_instance
