import pytest
from app.ai.food_safety.predictor import food_safety_predictor

def test_food_safety_insufficient_data():
    # Missing storage_condition
    data = {
        "food_type": "Cooked Meals",
        "elapsed_hours": 2.5
    }
    result = food_safety_predictor.predict(data)
    assert result["classification"] == "INSUFFICIENT_DATA"
    assert "disclaimer" in result

def test_food_safety_safe_prediction():
    data = {
        "food_type": "Cooked Meals",
        "elapsed_hours": 0.5,
        "storage_condition": "Room Temperature",
        "temperature_c": 25.0
    }
    result = food_safety_predictor.predict(data)
    # ML model or rule-based should predict SAFE for 0.5 hours at room temp
    assert result["classification"] in ["SAFE", "CAUTION"] 
    assert "disclaimer" in result

def test_food_safety_unsafe_prediction():
    data = {
        "food_type": "Cooked Meals",
        "elapsed_hours": 5.0,
        "storage_condition": "Room Temperature",
        "temperature_c": 30.0
    }
    result = food_safety_predictor.predict(data)
    # Both hard-rule fallback and ML model should flag this as UNSAFE or CAUTION at least
    assert result["classification"] in ["UNSAFE", "CAUTION"]

