import pytest
from app.ai.priority.predictor import predictor

def test_priority_critical_disaster():
    features = {
        "requested_quantity": 2500,
        "emergency_type": "Flood Relief",
        "is_weather_related": True,
        "number_of_people": 800,
        "deadline_hours": 3.0
    }
    result = predictor.predict(features)
    assert result["priority"] == "CRITICAL"
    assert result["priority_level"] == "CRITICAL"
    assert result["score"] >= 0.85
    assert "explanation" in result

def test_priority_normal_request():
    features = {
        "requested_quantity": 40,
        "emergency_type": "Standard Community Drive",
        "is_weather_related": False,
        "number_of_people": 25,
        "deadline_hours": 48.0,
        "urgency": "LOW"
    }
    result = predictor.predict(features)
    assert result["priority"] in ["LOW", "MEDIUM"]
    assert result["priority_level"] in ["LOW", "MEDIUM"]
    assert result["score"] <= 0.65
    assert "explanation" in result
