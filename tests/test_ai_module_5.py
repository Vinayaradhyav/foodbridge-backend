import pytest
from app.ai.chatbot.emergency_nlp_parser import (
    emergency_nlp_parser,
    EmergencyNLPParser,
    parse_emergency_text,
    parse_emergency_message,
    extract_emergency_parameters
)
from app.ai.chatbot.multilingual_nlp import multilingual_nlp_engine
from app.ai.chatbot.intent_classifier import IntentClassifier

def test_emergency_nlp_parser_initialization():
    parser = EmergencyNLPParser()
    assert parser is not None
    assert emergency_nlp_parser is not None

def test_parse_emergency_english():
    text = "Emergency! 500 meals needed for 200 people immediately due to flood in Bangalore"
    result = emergency_nlp_parser.parse(text)
    
    assert result["quantity"] == 500
    assert result["number_of_people"] == 200
    assert result["urgency"] == "CRITICAL"
    assert result["priority"] == "CRITICAL"
    assert "Flood" in result["disaster_type"]
    assert "Bangalore" in result["location"]
    assert result["language"] == "en"

def test_parse_emergency_kannada():
    text = "ತುರ್ತು: ಪ್ರವಾಹ ಸಂತ್ರಸ್ತರಿಗೆ ತಕ್ಷಣವೇ 300 ಊಟದ ಪೊಟ್ಟಣಗಳು ಬೇಕು"
    result = emergency_nlp_parser.parse(text)
    
    assert result["quantity"] == 300
    assert result["urgency"] == "CRITICAL"
    assert result["priority"] in ["HIGH", "CRITICAL"]
    assert result["language"] == "kn"

def test_parse_emergency_hindi():
    text = "आपातकालीन: 400 लोगों के लिए तुरंत 600 भोजन पैकेट चाहिए"
    result = emergency_nlp_parser.parse(text)
    
    assert result["quantity"] in [400, 600]
    assert result["urgency"] == "CRITICAL"
    assert result["priority"] == "CRITICAL"
    assert result["language"] == "hi"

def test_parse_emergency_tamil():
    text = "அவசரம்! வெள்ளத்தால் பாதிக்கப்பட்ட 100 பேருக்கு உணவு வேண்டும்"
    result = emergency_nlp_parser.parse(text)
    
    assert result["number_of_people"] == 100 or result["quantity"] >= 50
    assert result["urgency"] == "CRITICAL"
    assert result["priority"] in ["HIGH", "CRITICAL"]
    assert result["language"] == "ta"

def test_parse_emergency_telugu():
    text = "అత్యవసర: వరదలు వచ్చాయి వెంటనే 500 భోజనాలు కావాలి"
    result = emergency_nlp_parser.parse(text)
    
    assert result["quantity"] == 500 or result["number_of_people"] > 0
    assert result["urgency"] == "CRITICAL"
    assert result["priority"] == "CRITICAL"
    assert result["language"] == "te"

def test_calculate_priority():
    # Critical cases
    assert emergency_nlp_parser.calculate_priority({"urgency": "CRITICAL", "people_affected": 200}) == "CRITICAL"
    assert emergency_nlp_parser.calculate_priority({"urgency": "MEDIUM", "people_affected": 150}) == "CRITICAL"
    
    # High cases
    assert emergency_nlp_parser.calculate_priority({"urgency": "HIGH", "people_affected": 40}) == "HIGH"
    assert emergency_nlp_parser.calculate_priority({"urgency": "MEDIUM", "people_affected": 60}) == "HIGH"
    
    # Medium and Low
    assert emergency_nlp_parser.calculate_priority({"urgency": "MEDIUM", "people_affected": 25}) == "MEDIUM"
    assert emergency_nlp_parser.calculate_priority({"urgency": "LOW", "people_affected": 5}) == "LOW"

def test_convenience_helper_functions():
    text = "Need 100 food packets for 50 people soon"
    p1 = parse_emergency_text(text)
    p2 = parse_emergency_message(text)
    p3 = extract_emergency_parameters(text)
    
    assert p1["quantity"] == 100
    assert p2["quantity"] == 100
    assert p3["quantity"] == 100
