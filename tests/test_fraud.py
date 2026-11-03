import pytest
from app.ai.fraud.predictor import fraud_predictor

def test_fraud_normal_behavior():
    data = {
        'daily_donations': 1,
        'avg_quantity': 45.0,
        'cancellations': 0,
        'distance_variance': 0.5,
        'duplicate_ips': 0
    }
    result = fraud_predictor.analyze(data)
    assert result['classification'] == 'NORMAL'
    assert result['risk_score'] < 30
    assert len(result['reasons']) == 0

def test_fraud_high_quantity():
    data = {
        'daily_donations': 1,
        'avg_quantity': 6000.0,
        'cancellations': 0,
        'distance_variance': 0.5,
        'duplicate_ips': 0
    }
    result = fraud_predictor.analyze(data)
    assert result['classification'] in ['SUSPICIOUS', 'HIGH_RISK']
    assert any("Extremely high quantity" in r for r in result['reasons'])

def test_fraud_extreme_anomalies():
    data = {
        'daily_donations': 15,
        'avg_quantity': 8000.0,
        'cancellations': 10,
        'distance_variance': 55.0,
        'duplicate_ips': 4
    }
    result = fraud_predictor.analyze(data)
    assert result['classification'] == 'HIGH_RISK'
    assert result['risk_score'] >= 70
    assert len(result['reasons']) >= 3

def test_fraud_evaluate_donation():
    normal_don = {"quantity": 50, "food_type": "Cooked Meals"}
    res_normal = fraud_predictor.evaluate_donation(normal_don)
    assert res_normal["is_flagged"] is False
    assert res_normal["risk_score"] < 30

    massive_don = {"quantity": 8000, "food_type": "Cooked Meals"}
    res_massive = fraud_predictor.evaluate_donation(massive_don)
    assert res_massive["is_flagged"] is True
    assert res_massive["risk_level"] == "HIGH_RISK"
    assert res_massive["requires_admin_review"] is True
