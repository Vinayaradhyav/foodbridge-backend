import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ai.assignment.route_optimizer import route_optimizer, RouteOptimizer
from app.ai.assignment.optimizer import assignment_optimizer

client = TestClient(app)

# ==================== Core Algorithm Unit Tests ====================

def test_haversine_distance_accuracy():
    # Bangalore MG Road (12.9716, 77.5946) to Whitefield (12.9698, 77.7499) ~ 16.8 km
    dist = RouteOptimizer.haversine_distance(12.9716, 77.5946, 12.9698, 77.7499)
    assert 16.0 <= dist <= 17.5
    # Zero distance test
    assert RouteOptimizer.haversine_distance(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

def test_travel_time_vehicle_speed_profiles():
    # 30 km distance
    dist = 30.0
    # Van @ 35 km/h, 1.0 traffic -> (30 / 35) * 60 = 51.4 mins
    time_van = route_optimizer.estimate_travel_time(dist, vehicle_type="Van", traffic_multiplier=1.0)
    assert 50.0 <= time_van <= 53.0

    # Bike @ 25 km/h, 1.0 traffic -> (30 / 25) * 60 = 72.0 mins
    time_bike = route_optimizer.estimate_travel_time(dist, vehicle_type="Bike", traffic_multiplier=1.0)
    assert 71.0 <= time_bike <= 73.0

    # Traffic multiplier increases duration
    time_traffic = route_optimizer.estimate_travel_time(dist, vehicle_type="Van", traffic_multiplier=1.5)
    assert time_traffic > time_van

def test_two_opt_local_search_optimizes_or_preserves():
    # Square path: 0 -> (0,0), 1 -> (0,1), 2 -> (1,0), 3 -> (1,1)
    # A crossed route: 0 -> 3 -> 1 -> 2 -> 0 has crossing edges
    coords = [
        {"lat": 0.0, "lon": 0.0},
        {"lat": 0.0, "lon": 1.0},
        {"lat": 1.0, "lon": 0.0},
        {"lat": 1.0, "lon": 1.0}
    ]
    matrix = route_optimizer.compute_distance_matrix(coords)
    crossed_route = [0, 3, 1, 2]
    improved_route = route_optimizer.two_opt_optimize(crossed_route, matrix)

    def dist(r):
        return sum(matrix[r[i]][r[i+1]] for i in range(len(r)-1))

    assert dist(improved_route) <= dist(crossed_route)
    assert len(improved_route) == len(crossed_route)

def test_route_precedence_and_capacity_bounds():
    vehicle = {
        "id": "V-VAN-101",
        "name": "Relief Van",
        "vehicle_type": "Van",
        "vehicle_capacity": 500,
        "lat": 12.9716,
        "lon": 77.5946
    }
    pickups = [
        {"id": "P1", "donor_name": "Hotel Taj", "lat": 12.9800, "lon": 77.6000, "quantity": 150, "expiry_hours": 4.0},
        {"id": "P2", "donor_name": "Wedding Hall", "lat": 12.9850, "lon": 77.6100, "quantity": 200, "expiry_hours": 3.5}
    ]
    dropoffs = [
        {"id": "D1", "shelter_name": "Community Shelter", "lat": 12.9600, "lon": 77.6200, "quantity": 350, "expiry_hours": 4.0}
    ]

    result = route_optimizer.optimize_multi_stop_route(vehicle, pickups, dropoffs)
    assert result["success"] is True
    stops = result["stops"]

    # Verify first stop is DEPOT
    assert stops[0]["type"] == "DEPOT"

    # Verify all PICKUP stops precede all DROPOFF stops
    pickup_seen = False
    dropoff_seen = False
    for stop in stops[1:]:
        if stop["type"] == "PICKUP":
            assert not dropoff_seen, "Pickup occurred after a dropoff violation!"
            pickup_seen = True
        elif stop["type"] == "DROPOFF":
            dropoff_seen = True

    assert pickup_seen and dropoff_seen

    # Verify vehicle capacity was never exceeded at any stop
    for stop in stops:
        assert stop["quantity_onboard"] <= vehicle["vehicle_capacity"]
        assert stop["quantity_onboard"] >= 0

    # Final dropoff must leave load at 0
    assert stops[-1]["quantity_onboard"] == 0

def test_route_capacity_overflow_rejection():
    vehicle = {"vehicle_capacity": 100, "vehicle_type": "Bike", "lat": 12.97, "lon": 77.59}
    pickups = [{"lat": 12.98, "lon": 77.60, "quantity": 150, "expiry_hours": 4.0}]
    dropoffs = [{"lat": 12.99, "lon": 77.61, "quantity": 150, "expiry_hours": 4.0}]

    result = route_optimizer.optimize_multi_stop_route(vehicle, pickups, dropoffs)
    assert result["success"] is False
    assert "exceeds vehicle capacity" in result["message"]

def test_carbon_emission_savings_calculated():
    vehicle = {
        "id": "V-TEMPO-1",
        "vehicle_type": "Tempo",
        "vehicle_capacity": 1000,
        "lat": 12.9716,
        "lon": 77.5946
    }
    pickups = [
        {"id": "P1", "lat": 12.980, "lon": 77.600, "quantity": 100, "expiry_hours": 4.0},
        {"id": "P2", "lat": 12.985, "lon": 77.610, "quantity": 150, "expiry_hours": 4.0}
    ]
    dropoffs = [
        {"id": "D1", "lat": 12.960, "lon": 77.620, "quantity": 250, "expiry_hours": 4.0}
    ]

    result = route_optimizer.optimize_multi_stop_route(vehicle, pickups, dropoffs)
    assert result["success"] is True
    metrics = result["metrics"]
    assert metrics["co2_emissions_saved_kg"] > 0
    assert metrics["total_distance_km"] > 0
    assert metrics["capacity_utilization_pct"] == 25.0

# ==================== FastAPI Endpoint Integration Tests ====================

def test_api_optimize_route_endpoint():
    payload = {
        "vehicle": {
            "id": "VAN-01",
            "name": "Rapid Van",
            "vehicle_type": "Van",
            "vehicle_capacity": 400,
            "lat": 12.9716,
            "lon": 77.5946
        },
        "pickups": [
            {
                "id": "P-Taj",
                "donor_name": "Taj Residency Surplus",
                "lat": 12.9800,
                "lon": 77.6000,
                "quantity": 150,
                "expiry_hours": 4.0,
                "food_type": "Cooked Meals"
            },
            {
                "id": "P-ITC",
                "donor_name": "ITC Gardenia Buffet",
                "lat": 12.9720,
                "lon": 77.5980,
                "quantity": 120,
                "expiry_hours": 3.5,
                "food_type": "Biryani & Bread"
            }
        ],
        "dropoffs": [
            {
                "id": "D-Hub1",
                "shelter_name": "Koramangala Relief Shelter",
                "lat": 12.9352,
                "lon": 77.6245,
                "quantity": 270,
                "expiry_hours": 4.0,
                "food_type": "Meals"
            }
        ],
        "traffic_multiplier": 1.25
    }

    response = client.post("/api/ai/logistics/optimize-route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["stops"]) == 4 # DEPOT + 2 Pickups + 1 Dropoff
    assert data["metrics"]["total_food_delivered"] == 270
    assert data["metrics"]["spoilage_violations"] == 0
    assert data["metrics"]["co2_emissions_saved_kg"] > 0

def test_api_logistics_metrics_endpoint():
    response = client.get("/api/ai/logistics/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["module"] == "AI Module 6: Logistics & Vehicle Route Optimization Engine"
    assert "average_distance_reduction_pct" in data
    assert "spoilage_compliance_rate_pct" in data
    assert "supported_fleet_types" in data

def test_api_multi_stop_plan_endpoint():
    payload = {
        "donations": [
            {"id": "P1", "donor_name": "Donor A", "lat": 12.972, "lon": 77.595, "quantity": 80, "expiry_hours": 4.0},
            {"id": "P2", "donor_name": "Donor B", "lat": 12.975, "lon": 77.600, "quantity": 60, "expiry_hours": 3.5}
        ],
        "shelters": [
            {"id": "D1", "shelter_name": "Shelter X", "lat": 12.940, "lon": 77.610, "quantity": 140, "expiry_hours": 4.0}
        ]
    }
    response = client.post("/api/ai/logistics/multi-stop-plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PLANNED"
    assert data["total_demand"] == 140
    # Smallest vehicle that can carry 140 meals is Auto (capacity 150)
    assert data["selected_vehicle"]["vehicle_type"] == "Auto"
    assert data["route_plan"]["success"] is True
