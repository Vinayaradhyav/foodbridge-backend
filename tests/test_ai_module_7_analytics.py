import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ai.analytics.heatmap_aggregator import heatmap_aggregator, HungerHeatmapAggregator

client = TestClient(app)

# ==================== Core Algorithm Unit Tests ====================

def test_haversine_distance():
    # Koramangala (12.9352, 77.6245) to Indiranagar (12.9784, 77.6408) ~ 5.1 km
    dist = HungerHeatmapAggregator.haversine_distance(12.9352, 77.6245, 12.9784, 77.6408)
    assert 4.5 <= dist <= 5.8
    assert HungerHeatmapAggregator.haversine_distance(12.0, 77.0, 12.0, 77.0) == 0.0

def test_find_nearest_zone():
    zones = HungerHeatmapAggregator.DEFAULT_REFERENCE_ZONES
    # Coordinate near Koramangala
    nearest = heatmap_aggregator.find_nearest_zone(12.9360, 77.6250, zones, max_radius_km=5.0)
    assert nearest["id"] == "ZONE-KORA"

def test_hunger_severity_index_scaling():
    # 1. Zero demand -> HSI = 0, LOW
    hsi_zero, level_zero = heatmap_aggregator.calculate_hunger_severity_index(supply_meals=100, demand_meals=0)
    assert hsi_zero == 0.0
    assert level_zero == "LOW"

    # 2. Complete deficit with emergency -> CRITICAL
    hsi_crit, level_crit = heatmap_aggregator.calculate_hunger_severity_index(
        supply_meals=20,
        demand_meals=500,
        is_emergency=True
    )
    assert hsi_crit >= 75.0
    assert level_crit == "CRITICAL"

    # 3. Balanced supply and demand -> LOW or MODERATE
    hsi_bal, level_bal = heatmap_aggregator.calculate_hunger_severity_index(
        supply_meals=400,
        demand_meals=420,
        is_emergency=False
    )
    assert hsi_bal < 30.0

def test_heatmap_aggregation_clustering_and_redistribution():
    # Synthetic donations clustered in Koramangala and Indiranagar
    donations = [
        {"latitude": 12.9350, "longitude": 77.6240, "quantity": 800}, # Heavy surplus in Koramangala
        {"latitude": 12.9780, "longitude": 77.6400, "quantity": 100}
    ]
    # Heavy demand in Shivajinagar
    demands = [
        {"latitude": 12.9850, "longitude": 77.6050, "required_meals": 600, "severity": "CRITICAL", "is_emergency": True}
    ]

    result = heatmap_aggregator.aggregate_hunger_heatmap(donations, demands, cluster_radius_km=6.0)

    assert "summary" in result
    assert "hotspots" in result
    assert result["summary"]["total_monitored_zones"] >= 8
    assert result["summary"]["total_supply_meals"] >= 900

    # Verify heat weight is normalized between 0.0 and 1.0
    for h in result["hotspots"]:
        assert 0.05 <= h["heat_weight"] <= 1.0
        assert h["severity_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]

    # Verify inter-zone redistribution recommendation
    redist = result["redistribution_recommendations"]
    assert len(redist) > 0
    first_transfer = redist[0]
    assert "from_zone" in first_transfer
    assert "to_zone" in first_transfer
    assert first_transfer["recommended_transfer_meals"] > 0
    assert first_transfer["distance_km"] > 0

def test_environmental_impact_calculations():
    food_kg = 1000.0
    meals = 2500

    impact = heatmap_aggregator.compute_environmental_impact(food_kg, meals)

    # 1 kg food waste diverted = 2.5 kg CO2e
    assert impact["co2_emissions_avoided_kg"] == 2500.0
    # 1 kg food waste = 0.15 kg methane
    assert impact["methane_avoided_kg"] == 150.0
    # 1 meal = 1,000 Liters of water
    assert impact["water_footprint_conserved_liters"] == 2500000
    assert impact["equivalent_passenger_car_days_removed"] > 0
    assert impact["equivalent_urban_trees_planted_year"] > 0

def test_diurnal_temporal_patterns():
    profiles = heatmap_aggregator.compute_temporal_diurnal_patterns()
    assert len(profiles) == 12
    # Verify post-lunch and post-dinner surplus peaks
    peak_lunch = next(p for p in profiles if p["hour"] == "14:00")
    peak_dinner = next(p for p in profiles if p["hour"] == "22:00")
    assert peak_lunch["supply_pct"] >= 20.0
    assert peak_dinner["supply_pct"] >= 25.0

# ==================== FastAPI Endpoint Integration Tests ====================

def test_api_analytics_dashboard():
    response = client.get("/api/analytics/dashboard?timeframe=weekly")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "environmental_impact" in data
    assert "food_categories" in data
    assert "temporal_diurnal_patterns" in data
    assert data["environmental_impact"]["co2_emissions_avoided_kg"] > 0
    assert data["metrics"]["match_efficiency_pct"] > 90.0

def test_api_analytics_heatmap():
    response = client.get("/api/analytics/heatmap?cluster_radius_km=5.0")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "hotspots" in data
    assert len(data["hotspots"]) >= 8
    # Check HSI fields
    first_spot = data["hotspots"][0]
    assert "hunger_severity_index" in first_spot
    assert "heat_weight" in first_spot
    assert "recommended_action" in first_spot

def test_api_analytics_heatmap_filter_severity():
    response = client.get("/api/analytics/heatmap?min_severity=CRITICAL")
    assert response.status_code == 200
    data = response.json()
    for h in data["hotspots"]:
        assert h["severity_level"] == "CRITICAL"

def test_api_analytics_heatmap_aggregate_post():
    payload = {
        "cluster_radius_km": 4.5,
        "custom_supply_points": [
            {"latitude": 12.9716, "longitude": 77.5946, "quantity": 300}
        ],
        "custom_demand_points": [
            {"latitude": 12.9850, "longitude": 77.6050, "required_meals": 450, "severity": "HIGH"}
        ]
    }
    response = client.post("/api/analytics/heatmap/aggregate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_monitored_zones"] >= 8

def test_api_hunger_index_rankings():
    response = client.get("/api/analytics/hunger-index")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "ranked_zones" in data
    assert len(data["ranked_zones"]) >= 8
    # Ranks must be ordered 1, 2, 3...
    assert data["ranked_zones"][0]["rank"] == 1

def test_api_environmental_impact():
    response = client.get("/api/analytics/environmental-impact")
    assert response.status_code == 200
    data = response.json()
    assert data["co2_emissions_avoided_kg"] > 0
    assert data["water_footprint_conserved_liters"] > 0
    assert data["waste_diversion_efficiency_pct"] >= 90.0

def test_api_analytics_metrics():
    response = client.get("/api/analytics/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "AI Module 7" in data["module"]
    assert "aggregation_latency_ms" in data
