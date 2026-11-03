import asyncio
import os
import hashlib
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config.settings import settings
import random

def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

async def seed_10_data():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    
    print("Clearing collections...")
    collections = ['users', 'donations', 'matches', 'assignments', 'deliveries', 'emergency_requests']
    for col in collections:
        await db[col].delete_many({})

    # 1. ADD 10 USERS (Donors, NGOs, Volunteers)
    print("Adding 10 Users...")
    users = []
    
    # 10 Donors
    donors = []
    for i in range(1, 11):
        uid = f"donor_{os.urandom(4).hex()}"
        doc = {
            "firebase_uid": uid,
            "name": f"Test Donor {i}",
            "email": f"donor{i}@test.com",
            "phone": f"100000000{i}",
            "role": "DONOR",
            "hashed_password": hash_password("password123"),
            "status": "active",
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc),
            "latitude": 12.9716 + (random.random() * 0.1),
            "longitude": 77.5946 + (random.random() * 0.1)
        }
        res = await db.users.insert_one(doc)
        donors.append(doc)
        users.append(doc)

    # 10 NGOs
    ngos = []
    for i in range(1, 11):
        uid = f"ngo_{os.urandom(4).hex()}"
        doc = {
            "firebase_uid": uid,
            "name": f"Test NGO {i}",
            "email": f"ngo{i}@test.com",
            "phone": f"200000000{i}",
            "role": "FOOD_RECEIVER",
            "receiver_type": "NGO",
            "hashed_password": hash_password("password123"),
            "status": "active",
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc),
            "latitude": 12.9716 + (random.random() * 0.1),
            "longitude": 77.5946 + (random.random() * 0.1)
        }
        res = await db.users.insert_one(doc)
        ngos.append(doc)
        users.append(doc)

    # 10 Volunteers
    volunteers = []
    for i in range(1, 11):
        uid = f"vol_{os.urandom(4).hex()}"
        doc = {
            "firebase_uid": uid,
            "name": f"Test Volunteer {i}",
            "email": f"vol{i}@test.com",
            "phone": f"300000000{i}",
            "role": "volunteer",
            "hashed_password": hash_password("password123"),
            "status": "active",
            "availabilityStatus": "available",
            "vehicleAvailable": True,
            "vehicleType": random.choice(["bike", "car", "van"]),
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc),
            "latitude": 12.9716 + (random.random() * 0.1),
            "longitude": 77.5946 + (random.random() * 0.1)
        }
        res = await db.users.insert_one(doc)
        volunteers.append(doc)
        users.append(doc)

    # 2. ADD 30 DONATIONS & 30 REQUESTS & 30 MATCHES & 30 DELIVERIES
    print("Adding 30 Donations, Requests, Matches, and Deliveries...")
    
    for i in range(1, 31):
        donor = random.choice(donors)
        ngo = random.choice(ngos)
        volunteer = random.choice(volunteers)
        
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
            "status": "COMPLETED",
            "ngo_id": ngo["firebase_uid"],
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.donations.insert_one(donation)

        # REQUEST (Emergency Request to match the prompt's 'requests')
        request_id = f"FB-REQ-100{i}"
        request_doc = {
            "request_id": request_id,
            "ngo_id": ngo["firebase_uid"],
            "title": f"Urgent Food Request {i}",
            "required_meals": random.randint(50, 200),
            "status": "FULFILLED",
            "urgency": "HIGH",
            "latitude": ngo["latitude"],
            "longitude": ngo["longitude"],
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.emergency_requests.insert_one(request_doc)

        # MATCHING
        match_id = f"FB-MAT-100{i}"
        match_doc = {
            "match_id": match_id,
            "donation_id": donation_id,
            "ngo_id": ngo["firebase_uid"],
            "score": random.uniform(80.0, 99.9),
            "status": "ACCEPTED",
            "created_at": datetime.now(timezone.utc) - timedelta(days=i)
        }
        await db.matches.insert_one(match_doc)

        # DELIVERY (Assignments & Deliveries)
        assignment_id = f"FB-ASN-100{i}"
        delivery_doc = {
            "assignment_id": assignment_id,
            "donation_id": donation_id,
            "volunteer_id": volunteer["firebase_uid"],
            "pickup_location": donation["pickup_location"],
            "delivery_location": f"NGO Center {i}",
            "status": "DELIVERED",
            "assigned_at": datetime.now(timezone.utc) - timedelta(hours=4),
            "completed_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "created_at": datetime.now(timezone.utc) - timedelta(days=i),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.assignments.insert_one(delivery_doc)
        await db.deliveries.insert_one(delivery_doc)
        
    print("Done! Added exactly 10 of each user type, and 30 interconnected donations, requests, matches, and deliveries.")

if __name__ == "__main__":
    asyncio.run(seed_10_data())
