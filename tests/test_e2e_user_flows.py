import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_full_user_workflow():
    with TestClient(app) as client:
        print("\n--- Starting E2E User Flow Test ---")
    
        # 1. NGO User Flow: Registration, Login, and Creating an Emergency Request
        print("User 1 (NGO): Registering and logging in...")
        ngo_uid = "test_ngo_uid_123"
        ngo_data = {
            "firebase_uid": ngo_uid,
            "email": "testngo@example.com",
            "name": "Test NGO",
            "role": "ngo",
            "latitude": 12.29,
            "longitude": 76.63,
            "phone": "9876543201"
        }
        # Register NGO
        resp = client.post("/api/auth/register", json=ngo_data)
        assert resp.status_code in (200, 201, 400)
        
        # Login NGO
        resp = client.post("/api/auth/login", json={"firebase_uid": ngo_uid, "email": "testngo@example.com"})
        assert resp.status_code == 200
        
        # NGO creates emergency request
        print("User 1 (NGO): Creating an emergency request...")
        emergency_data = {
            "created_by": ngo_uid,
            "food_type": "Meals",
            "quantity": 100,
            "number_of_people": 50,
            "location": "Flood Camp",
            "latitude": 12.29,
            "longitude": 76.63,
            "emergency_type": "FLOOD",
            "urgency": "HIGH",
            "deadline": "2026-10-10T12:00:00Z",
            "description": "Urgent flood relief needed"
        }
        resp = client.post(
            "/api/emergencies/", 
            json=emergency_data,
            headers={"Authorization": f"Bearer {ngo_uid}"}
        )
        assert resp.status_code in (200, 201)
        request_id = resp.json()["request_id"]
        print(f"Created Emergency Request: {request_id}")
        
        # 2. Donor User Flow: Registration, Login, and Pledging to the Emergency
        print("\nUser 2 (Donor): Registering and logging in...")
        donor_uid = "test_donor_uid_456"
        donor_data = {
            "firebase_uid": donor_uid,
            "email": "testdonor@example.com",
            "name": "Test Donor",
            "role": "donor",
            "latitude": 12.30,
            "longitude": 76.64,
            "phone": "9876543202"
        }
        client.post("/api/auth/register", json=donor_data)
        resp = client.post("/api/auth/login", json={"firebase_uid": donor_uid, "email": "testdonor@example.com"})
        assert resp.status_code == 200
        
        print("User 2 (Donor): Fetching active emergencies...")
        resp = client.get("/api/emergencies/")
        assert resp.status_code == 200
        emergencies = resp.json()
        assert len(emergencies) > 0
        assert any(e["request_id"] == request_id for e in emergencies)
        
        print("User 2 (Donor): Pledging support...")
        resp = client.put(
            f"/api/emergencies/{request_id}", 
            json={"fulfilled_quantity": 50},
            headers={"Authorization": f"Bearer {donor_uid}"}
        )
        assert resp.status_code == 200
        updated_req = resp.json()
        assert updated_req["fulfilled_quantity"] >= 50
        print(f"Pledged 50 meals. Fulfilled: {updated_req['fulfilled_quantity']}/{updated_req['quantity']}")
        
        # Donor creates a regular donation
        print("User 2 (Donor): Creating a regular donation...")
        donation_data = {
            "food_name": "Mixed Groceries",
            "food_type": "Groceries",
            "quantity": 20.0,
            "unit": "kg",
            "number_of_meals": 40,
            "preparation_time": "2026-10-10T10:00:00Z",
            "available_from": "2026-10-10T10:00:00Z",
            "pickup_deadline": "2026-12-31T23:59:59Z",
            "pickup_location": "Donor Home",
            "latitude": 12.30,
            "longitude": 76.64,
            "storage_condition": "Dry",
            "packaging_type": "Box"
        }
        resp = client.post(
            "/api/donations/", 
            json=donation_data,
            headers={"Authorization": f"Bearer {donor_uid}"}
        )
        assert resp.status_code in (200, 201)
        donation_id = resp.json()["id"]
        print(f"Created Donation: {donation_id}")
        
        # 3. Volunteer User Flow: Registration, Login, and Fetching Tasks
        print("\nUser 3 (Volunteer): Registering and logging in...")
        vol_uid = "test_vol_uid_789"
        vol_data = {
            "firebase_uid": vol_uid,
            "email": "testvol@example.com",
            "name": "Test Volunteer",
            "role": "volunteer",
            "latitude": 12.31,
            "longitude": 76.65,
            "phone": "9876543203",
            "vehicle_type": "Car",
            "max_capacity_kg": 50
        }
        client.post("/api/auth/register", json=vol_data)
        resp = client.post("/api/auth/login", json={"firebase_uid": vol_uid, "email": "testvol@example.com"})
        assert resp.status_code == 200
        
        print("\n--- E2E Flow Successful! ---")
        
if __name__ == "__main__":
    test_full_user_workflow()
