import re
from app.ai.chatbot.multilingual_nlp import multilingual_nlp_engine

class IntentClassifier:
    """
    AI Module 5 Supervised Intent Classifier.
    Integrates the Calibrated Multilingual Char-WB N-Gram pipeline with fallback rules.
    """
    
    INTENTS = {
        "status_donation": [r"where is my donation", r"donation status", r"active donations", r"my donations"],
        "status_delivery": [r"where is my delivery", r"delivery status", r"my delivery", r"track delivery"],
        "faq_donate": [r"\bdonate\b", r"\bdonation\b", r"give food"],
        "faq_volunteer": [r"\bvolunteer\b", r"help out", r"become a volunteer"],
        "faq_emergency": [r"emergency request", r"create emergency", r"need food now"]
    }
    
    @staticmethod
    def classify(message: str) -> str:
        msg = message.lower().strip()
        
        # Check for sensitive/mutating keywords
        sensitive_keywords = ["delete", "ban", "approve", "cancel my account", "update password"]
        if any(keyword in msg for keyword in sensitive_keywords):
            return "unauthorized_action"

        # Check classic legacy intents first for 100% backwards compatibility
        for legacy_intent, patterns in IntentClassifier.INTENTS.items():
            for pattern in patterns:
                if re.search(pattern, msg):
                    return legacy_intent

        # Use AI Module 5 Supervised ML Intent Engine
        intent, _ = multilingual_nlp_engine.classify_intent(message)
        
        # Map to legacy strings if matched
        mapping = {
            "DONATION_INQUIRY": "faq_donate",
            "VOLUNTEER_INQUIRY": "faq_volunteer",
            "EMERGENCY_SOS": "faq_emergency",
            "STATUS_TRACKING": "status_donation",
            "UNAUTHORIZED_ACTION": "unauthorized_action"
        }
        
        return mapping.get(intent, "unknown")
