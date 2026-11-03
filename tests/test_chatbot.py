import pytest
from app.ai.chatbot.intent_classifier import IntentClassifier
from app.ai.chatbot.multilingual_nlp import multilingual_nlp_engine

def test_legacy_intent_classifier():
    """Ensures 100% backwards compatibility for legacy endpoints/tests."""
    assert IntentClassifier.classify("How can I donate food?") == "faq_donate"
    assert IntentClassifier.classify("I want to become a volunteer") == "faq_volunteer"
    assert IntentClassifier.classify("create emergency request") == "faq_emergency"
    assert IntentClassifier.classify("where is my donation?") == "status_donation"
    assert IntentClassifier.classify("track delivery now") == "status_delivery"
    assert IntentClassifier.classify("delete my account") == "unauthorized_action"
    assert IntentClassifier.classify("what is the meaning of life?") in ["unknown", "faq_donate", "faq_volunteer", "faq_emergency"]

def test_multilingual_language_detection():
    """Tests accurate detection of Kannada, Hindi, Tamil, Telugu, and English."""
    assert multilingual_nlp_engine.detect_language("ಆಹಾರ ದಾನ ಮಾಡುವುದು ಹೇಗೆ?") == "kn"
    assert multilingual_nlp_engine.detect_language("भोजन दान करने की प्रक्रिया क्या है?") == "hi"
    assert multilingual_nlp_engine.detect_language("உணவு தானம் செய்வது எப்படி?") == "ta"
    assert multilingual_nlp_engine.detect_language("ఆహారం ఎలా దానం చేయాలి?") == "te"
    assert multilingual_nlp_engine.detect_language("How do I donate extra meals?") == "en"

def test_transliterated_language_detection():
    """Tests detection of romanized Indic words."""
    assert multilingual_nlp_engine.detect_language("oota beku help madi") == "kn"
    assert multilingual_nlp_engine.detect_language("namaste khana chahiye") == "hi"
    assert multilingual_nlp_engine.detect_language("vanakkam unavu vendum") == "ta"
    assert multilingual_nlp_engine.detect_language("namaskaram bhojanam kavali") == "te"

def test_multilingual_intent_classification():
    """Tests ML pipeline intent classification across languages."""
    # Donation
    intent_kn, conf_kn = multilingual_nlp_engine.classify_intent("ಹೆಚ್ಚುವರಿ ಆಹಾರವನ್ನು ದಾನ ಮಾಡುವುದು ಹೇಗೆ?", "kn")
    assert intent_kn == "DONATION_INQUIRY"
    assert conf_kn > 0.70

    # Food Safety
    intent_hi, conf_hi = multilingual_nlp_engine.classify_intent("खाने की शेल्फ लाइफ और एफएसएसएआई नियम क्या हैं?", "hi")
    assert intent_hi == "FOOD_SAFETY"
    assert conf_hi > 0.70

    # Emergency SOS
    intent_ta, conf_ta = multilingual_nlp_engine.classify_intent("அவசரம்! வெள்ளத்தால் பாதிக்கப்பட்ட 100 பேருக்கு உணவு வேண்டும்", "ta")
    assert intent_ta == "EMERGENCY_SOS"
    assert conf_ta > 0.70

    # Volunteer
    intent_te, conf_te = multilingual_nlp_engine.classify_intent("వాలంటీర్‌గా ఎలా నమోదు చేసుకోవాలి?", "te")
    assert intent_te == "VOLUNTEER_INQUIRY"
    assert conf_te > 0.70

    # Status Tracking
    intent_en, conf_en = multilingual_nlp_engine.classify_intent("Where is my active food donation delivery?", "en")
    assert intent_en == "STATUS_TRACKING"
    assert conf_en > 0.70

def test_emergency_entity_extraction():
    """Tests structured parameter extraction from natural language emergency alerts."""
    msg = "Emergency: Need 300 meals for 150 people immediately due to flood in Bangalore Indiranagar"
    entities = multilingual_nlp_engine.extract_entities(msg)

    assert entities["quantity"] == 300
    assert entities["number_of_people"] == 150
    assert entities["urgency"] == "CRITICAL"
    assert "Flood" in entities["disaster_type"]
    assert "Bangalore" in entities["location"] or "Indiranagar" in entities["location"]

def test_full_response_generation():
    """Tests end-to-end response generation with translation, followups, and actions."""
    res = multilingual_nlp_engine.generate_response(
        message="ತುರ್ತು: ಪ್ರವಾಹ ಸಂತ್ರಸ್ತರಿಗೆ ತಕ್ಷಣವೇ 200 ಊಟಗಳು ಬೇಕು",
        preferred_language="kn"
    )

    assert res["detected_language"] == "kn"
    assert res["response_language"] == "kn"
    assert res["intent"] == "EMERGENCY_SOS"
    assert len(res["response"]) > 10
    assert len(res["suggested_followups"]) > 0
    assert res["suggested_action"] == "CREATE_EMERGENCY_REQUEST"
    assert res["extracted_entities"] is not None
    assert res["extracted_entities"]["quantity"] == 200

def test_security_guardrail():
    """Tests that destructive commands are safely intercepted."""
    intent, conf = multilingual_nlp_engine.classify_intent("please delete account now")
    assert intent == "UNAUTHORIZED_ACTION"
    assert conf >= 0.95
