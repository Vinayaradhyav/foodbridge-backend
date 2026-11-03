import asyncio
import os
import hashlib
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config.settings import settings
import random

def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

async def seed_admin_demo_data():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    
    print("Clearing collections...")
    collections = ['users', 'donations', 'matches', 'assignments', 'deliveries', 'emergency_requests']
    for col in collections:
        await db[col].delete_many({})

    # ADD 1 Admin User for testing
    admin_uid = f"admin_{os.urandom(4).hex()}"
    admin_doc = {
        "firebase_uid": admin_uid,
        "name": "Super Admin",
        "email": "admin@test.com",
        "phone": "9999999999",
        "role": "admin",
        "hashed_password": hash_password("admin123"),
        "status": "active",
        "verification_status": "VERIFIED",
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
        "updated_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(admin_doc)
    print("Added 1 Admin user (admin@test.com / admin123)")

    # 1. ADD 10 USERS (Donors, NGOs, Volunteers) - Some Pending, Some Active
    print("Adding 10 Demo Users...")
    users = []
    
    # 10 Donors (5 Active, 5 Pending)
    donors = []
    for i in range(1, 11):
        uid = f"donor_{os.urandom(4).hex()}"
        status = "active" if i <= 5 else "pending"
        verification = "VERIFIED" if i <= 5 else "PENDING"
        doc = {
            "firebase_uid": uid,
            "name": f"Test Donor {i}",
            "email": f"donor{i}@test.com",
            "phone": f"10000000{i:02d}",
            "role": "DONOR",
            "hashed_password": hash_password("password123"),
            "status": status,
            "verification_status": verification,
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc),
            "latitude": 12.9716 + (random.random() * 0.1),
            "longitude": 77.5946 + (random.random() * 0.1)
        }
        await db.users.insert_one(doc)
        donors.append(doc)
        users.append(doc)
        
        # If pending, also simulate the notification sent to admin
        if status == "pending":
            await db.notifications.insert_one({
                "user_id": "admin",
                "title": "New Registration Pending Approval",
                "body": f"A new DONOR (Test Donor {i}) has registered and requires approval.",
                "type": "ADMIN_ALERT",
                "read": False,
                "created_at": datetime.now(timezone.utc) - timedelta(days=i)
            })

    # 10 NGOs (5 Active, 5 Pending)
    ngos = []
    for i in range(1, 11):
        uid = f"ngo_{os.urandom(4).hex()}"
        status = "active" if i <= 5 else "pending"
        verification = "VERIFIED" if i <= 5 else "PENDING"
        doc = {
            "firebase_uid": uid,
            "name": f"Test NGO {i}",
            "email": f"ngo{i}@test.com",
            "phone": f"20000000{i:02d}",
            "role": "FOOD_RECEIVER",
            "receiver_type": "NGO",
            "hashed_password": hash_password("password123"),
            "status": status,
            "verification_status": verification,
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc),
            "latitude": 12.9716 + (random.random() * 0.1),
            "longitude": 77.5946 + (random.random() * 0.1)
        }
        await db.users.insert_one(doc)
        ngos.append(doc)
        users.append(doc)
        
        if status == "pending":
            await db.notifications.insert_one({
                "user_id": "admin",
                "title": "New Registration Pending Approval",
                "body": f"A new FOOD_RECEIVER (Test NGO {i}) has registered and requires approval.",
                "type": "ADMIN_ALERT",
                "read": False,
                "created_at": datetime.now(timezone.utc) - timedelta(days=i)
            })

    # 10 Volunteers (5 Active, 5 Pending)
    volunteers = []
    for i in range(1, 11):
        uid = f"vol_{os.urandom(4).hex()}"
        status = "active" if i <= 5 else "pending"
        verification = "VERIFIED" if i <= 5 else "PENDING"
        doc = {
            "firebase_uid": uid,
            "name": f"Test Volunteer {i}",
            "email": f"vol{i}@test.com",
            "phone": f"30000000{i:02d}",
            "role": "volunteer",
            "hashed_password": hash_password("password123"),
            "status": status,
            "verification_status": verification,
            "availabilityStatus": "available",
            "vehicleAvailable": True,
            "vehicleType": random.choice(["bike", "car", "van"]),
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc),
            "latitude": 12.9716 + (random.random() * 0.1),
            "longitude": 77.5946 + (random.random() * 0.1)
        }
        await db.users.insert_one(doc)
        volunteers.append(doc)
        users.append(doc)
        
        if status == "pending":
            await db.notifications.insert_one({
                "user_id": "admin",
                "title": "New Registration Pending Approval",
                "body": f"A new volunteer (Test Volunteer {i}) has registered and requires approval.",
                "type": "ADMIN_ALERT",
                "read": False,
                "created_at": datetime.now(timezone.utc) - timedelta(days=i)
            })

    print("Added 30 demo users with mixed pending/active status.")

    # 2. ADD 15 DONATIONS, 15 REQUESTS, and 15 ASSIGNMENTS
    print("Adding Donations, Requests, and Assignments...")
    
    active_donors = [d for d in donors if d["status"] == "active"]
    active_ngos = [n for n in ngos if n["status"] == "active"]
    active_vols = [v for v in volunteers if v["status"] == "active"]
    
    for i in range(1, 16):
        donor = random.choice(active_donors) if active_donors else random.choice(donors)
        ngo = random.choice(active_ngos) if active_ngos else random.choice(ngos)
        volunteer = random.choice(active_vols) if active_vols else random.choice(volunteers)
        
        donation_status = random.choice(["PENDING", "ACCEPTED", "ASSIGNED", "COMPLETED"])
        
        # DONATION
        donation_id = f"FB-DON-100{i}"
        donation = {
            "donation_id": donation_id,
            "donor_id": donor["firebase_uid"],
            "food_name": f"Fresh Meals Batch {i}",
            "food_type": "Cooked Food",
            "quantity": random.randint(20, 50),
            "unit": "meals",
            "number_of_meals": random.randint(20, 50),
            "preparation_time": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "available_from": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "pickup_deadline": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
            "pickup_location": f"Kitchen {i} Location",
            "latitude": donor["latitude"],
            "longitude": donor["longitude"],
            "storage_condition": "Room Temp",
            "packaging_type": "Containers",
            "is_emergency": False,
            "status": donation_status,
            "ngo_id": ngo["firebase_uid"],
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.donations.insert_one(donation)

        # REQUEST
        request_id = f"FB-REQ-100{i}"
        request_doc = {
            "request_id": request_id,
            "ngo_id": ngo["firebase_uid"],
            "title": f"Urgent Food Request {i}",
            "required_meals": random.randint(50, 200),
            "status": random.choice(["PENDING", "FULFILLED"]),
            "urgency": "HIGH",
            "latitude": ngo["latitude"],
            "longitude": ngo["longitude"],
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.emergency_requests.insert_one(request_doc)
        
        # ASSIGNMENT
        if donation_status in ["ASSIGNED", "COMPLETED"]:
            assignment_status = "COMPLETED" if donation_status == "COMPLETED" else random.choice(["PENDING", "ACCEPTED", "IN_TRANSIT"])
            assignment_doc = {
                "donation_id": donation_id,
                "volunteer_id": volunteer["firebase_uid"],
                "pickup_location": f"Kitchen {i} Location",
                "delivery_location": f"NGO {i} Location",
                "status": assignment_status,
                "pickup_otp": str(random.randint(1000, 9999)),
                "assigned_at": datetime.now(timezone.utc) - timedelta(hours=3),
                "accepted_at": (datetime.now(timezone.utc) - timedelta(hours=2)) if assignment_status != "PENDING" else None,
                "completed_at": (datetime.now(timezone.utc) - timedelta(hours=1)) if assignment_status == "COMPLETED" else None,
                "created_at": datetime.now(timezone.utc) - timedelta(days=i)
            }
            await db.assignments.insert_one(assignment_doc)
        
    print("Done! Demo data setup complete.")

if __name__ == "__main__":
    asyncio.run(seed_admin_demo_data())
