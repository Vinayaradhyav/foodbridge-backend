import pytest
from app.ai.assignment.optimizer import assignment_optimizer

def test_assignment_filters_unavailable_and_unauthorized():
    task = {"pickup_lat": 12.0, "pickup_lon": 76.0, "quantity": 100}
    volunteers = [
        {"id": "V1", "name": "Alice", "lat": 12.01, "lon": 76.01, "is_authorized": False, "is_available": True, "vehicle_capacity": 500, "current_workload": 0},
        {"id": "V2", "name": "Bob", "lat": 12.01, "lon": 76.01, "is_authorized": True, "is_available": False, "vehicle_capacity": 500, "current_workload": 0}
    ]
    
    result = assignment_optimizer.optimize(task, volunteers)
    assert result["success"] == False
    assert "No eligible volunteers" in result["message"]

def test_assignment_filters_capacity():
    task = {"pickup_lat": 12.0, "pickup_lon": 76.0, "quantity": 1000}
    volunteers = [
        {"id": "V1", "name": "Charlie", "lat": 12.01, "lon": 76.01, "is_authorized": True, "is_available": True, "vehicle_capacity": 500, "current_workload": 0},
    ]
    
    result = assignment_optimizer.optimize(task, volunteers)
    assert result["success"] == False

def test_assignment_prefers_closer_volunteer():
    task = {"pickup_lat": 12.0, "pickup_lon": 76.0, "quantity": 100}
    volunteers = [
        {"id": "V1", "name": "Far", "lat": 13.0, "lon": 77.0, "is_authorized": True, "is_available": True, "vehicle_capacity": 500, "current_workload": 0, "vehicle_type": "Truck"},
        {"id": "V2", "name": "Near", "lat": 12.01, "lon": 76.01, "is_authorized": True, "is_available": True, "vehicle_capacity": 500, "current_workload": 0, "vehicle_type": "Van"}
    ]
    
    result = assignment_optimizer.optimize(task, volunteers)
    assert result["success"] == True
    assert result["recommended_volunteer"]["name"] == "Near"

def test_assignment_prefers_lower_workload():
    task = {"pickup_lat": 12.0, "pickup_lon": 76.0, "quantity": 100}
    # Both are at same location
    volunteers = [
        {"id": "V1", "name": "Busy", "lat": 12.01, "lon": 76.01, "is_authorized": True, "is_available": True, "vehicle_capacity": 500, "current_workload": 5, "vehicle_type": "Van"},
        {"id": "V2", "name": "Free", "lat": 12.01, "lon": 76.01, "is_authorized": True, "is_available": True, "vehicle_capacity": 500, "current_workload": 0, "vehicle_type": "Van"}
    ]
    
    result = assignment_optimizer.optimize(task, volunteers)
    assert result["success"] == True
    assert result["recommended_volunteer"]["name"] == "Free"
