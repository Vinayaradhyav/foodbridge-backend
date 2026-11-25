import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ai.chatbot.indic_nlp_engine import indic_nlp_engine
from app.core.security import hash_password, verify_password
from app.main import app


def test_multi_segment_pause_english_disambiguation():
    """Verify Test 1 & Test A/G: 4 sentences merged across pauses with strict number disambiguation."""
    text = (
        "There are 200 people in a shelter near Mysuru. "
        "We urgently need 500 cooked meals. "
        "The food must be properly packed. "
        "We also need drinking water bottles tonight."
    )
    res = indic_nlp_engine.extract_entities(text)
    assert res["number_of_people"] == 200
    assert res["food_quantity"] == 500
    assert res["quantity"] == 500
    assert res["delivery_location"] == "Mysuru"
    assert res["packaging_required"] is True
    assert res["water_required"] is True
    assert res["delivery_time"] == "tonight"
    assert res["missing_fields"] == []


def test_number_isolation_three_entities():
    """Verify Test G / Number Isolation: 500 meals for 200 people and 100 water bottles."""
    text = "500 meals for 200 people and 100 water bottles in Mysuru"
    res = indic_nlp_engine.extract_entities(text)
    assert res["food_quantity"] == 500
    assert res["number_of_people"] == 200
    assert res["water_quantity"] == 100
    assert res["delivery_location"] == "Mysuru"


def test_kannada_script_and_digits():
    """Verify Test B: Kannada food packets + Kannada numeral transliteration."""
    text = "ಮೈಸೂರಿನಲ್ಲಿ 70 ಜನರಿಗೆ 300 ಊಟದ ಪ್ಯಾಕೆಟ್ಗಳು ಬೇಕು."
    res = indic_nlp_engine.extract_entities(text)
    assert res["original_language"] == "kn"
    assert res["delivery_location"] == "Mysuru"
    assert res["number_of_people"] == 70
    assert res["food_quantity"] == 300
    assert res["packaging_required"] is True
    assert res["original_transcript"] == text

    # Also test Kannada native digits (೭೦ & ೩೦೦)
    kn_digits = "ಮೈಸೂರಿನಲ್ಲಿ ೭೦ ಜನರಿಗೆ ೩೦೦ ಊಟದ ಪ್ಯಾಕೆಟ್ಗಳು ಬೇಕು."
    res_d = indic_nlp_engine.extract_entities(kn_digits)
    assert res_d["number_of_people"] == 70
    assert res_d["food_quantity"] == 300
    assert "70" in res_d["normalized_transcript"]
    assert "300" in res_d["normalized_transcript"]


def test_hindi_script_and_digits():
    """Verify Test C: Hindi numerals (२००, ५००, १००) & script preservation."""
    text = "मैसूर में २०० लोगों के लिए ५०० भोजन पैकेट और १०० पानी की बोतलें चाहिए"
    res = indic_nlp_engine.extract_entities(text)
    assert res["original_language"] == "hi"
    assert res["delivery_location"] == "Mysuru"
    assert res["number_of_people"] == 200
    assert res["food_quantity"] == 500
    assert res["water_quantity"] == 100
    assert res["original_transcript"] == text


def test_password_hashing_and_verification_all_formats():
    """Verify security hashing & verification works cleanly without breaking seeded/registered users."""
    hp = hash_password("FoodBridge@123")
    assert verify_password("FoodBridge@123", hp) is True
    assert verify_password("wrong", hp) is False
    assert verify_password("legacy", "legacy") is True


def test_process_voice_endpoint_contract():
    """Verify FastAPI /api/emergencies/process-voice and /api/v1/emergencies/process-voice."""
    client = TestClient(app)
    resp = client.post(
        "/api/emergencies/process-voice",
        json={
            "transcript": "There are 200 people in a shelter near Mysuru. We urgently need 500 cooked meals. The food must be properly packed. We also need 100 drinking water bottles tonight.",
            "original_language": "en",
            "target_language": "en",
            "session_id": "test_sos_001",
            "audio_duration_seconds": 18,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert data["number_of_people"] == 200
    assert data["food_quantity"] == 500
    assert data["water_quantity"] == 100
    assert data["packaging_required"] is True
    assert data["water_required"] is True
    assert data["location"] == "Mysuru"

    # Also confirm v1 path works
    resp_v1 = client.post(
        "/api/v1/emergencies/process-voice",
        json={
            "transcript": "ಮೈಸೂರಿನಲ್ಲಿ 70 ಜನರಿಗೆ 300 ಊಟದ ಪ್ಯಾಕೆಟ್ಗಳು ಬೇಕು.",
            "original_language": "kn",
            "target_language": "en",
        },
    )
    assert resp_v1.status_code == 200
    d2 = resp_v1.json()
    assert d2["number_of_people"] == 70
    assert d2["food_quantity"] == 300
    assert d2["location"] == "Mysuru"
