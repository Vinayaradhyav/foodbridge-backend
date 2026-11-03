import pytest
from app.services.matching_engine import MatchingEngine

def test_calculate_distance():
    # Test identical points (distance should be 0)
    assert MatchingEngine._calculate_distance(12.0, 77.0, 12.0, 77.0) == 0.0
    
    # Distance between Bangalore and Mysore is approx 130km
    # 12.9716, 77.5946 (Bangalore)
    # 12.2958, 76.6394 (Mysore)
    dist = MatchingEngine._calculate_distance(12.9716, 77.5946, 12.2958, 76.6394)
    assert 120 < dist < 140

def test_score_emergency_for_donation_perfect_match():
    donation = {
        "latitude": 12.9, "longitude": 77.6,
        "food_type": "Cooked Meals",
        "quantity": 100
    }
    emergency = {
        "latitude": 12.9, "longitude": 77.6,
        "food_type": "Meals",
        "quantity": 50, # Needs 50, donation has 100
    }
    
    result = MatchingEngine._score_emergency_for_donation(emergency, donation)
    
    # Quantity: 40, Type: 30, Dist: 30
    assert result["total_score"] == 100
    assert len(result["breakdown"]) == 3

def test_score_emergency_for_donation_weak_match():
    donation = {
        "latitude": 12.9, "longitude": 77.6,
        "food_type": "Raw Vegetables",
        "quantity": 10 # 10 items
    }
    emergency = {
        "latitude": 28.7, "longitude": 77.1, # Delhi, far away
        "food_type": "Meals",
        "quantity": 100,
    }
    
    result = MatchingEngine._score_emergency_for_donation(emergency, donation)
    
    # Quantity: 5 (donation partially satisfies request, quantity > 0)
    # Type: 0 (Raw Vegetables not in Meals)
    # Distance: 0 (far away)
    assert result["total_score"] == 5
    assert len(result["breakdown"]) == 1
