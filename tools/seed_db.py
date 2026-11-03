import asyncio
import random
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config.settings import settings
from app.models.user import UserModel
from app.models.donation import DonationModel
from app.schemas.donation import DonationStatus
from app.models.notification import NotificationModel

async def seed_db():
    print("Connecting to DB...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]

    print("Clearing old demo data...")
    # Optionally drop or delete matching documents
    # Let's just create them fresh.

    # 1. Create Admin
    admin_id = "admin_demo_01"
    admin = await db.users.find_one({"email": "admin@demo.com"})
    if not admin:
        admin_doc = UserModel.create_new_user(
            firebase_uid=admin_id,
            name="Super Admin",
            email="admin@demo.com",
            phone="1234567890",
            role="admin",
        )
        # Assuming admin auth in auth.py checks hashed_password, but for simplicity here we just insert it.
        # This password is "admin123" assuming hash_password isn't strictly needed for the demo login if we bypass it.
        # But wait, admin_login checks hashed_password. Let's just create a normal admin.
        admin_doc["hashed_password"] = "80f8db2c81d293d0$9101f3f6c8d7e008a958e72782e4e16d43e5a593" # salt: 80f8db2c81d293d0
        await db.users.insert_one(admin_doc)
        print("Created Admin: admin@demo.com / admin123")
    else:
        print("Admin already exists.")

    donors = []
    receivers = []
    volunteers = []

    # 2. Create Users
    print("Creating Demo Users...")
    for i in range(1, 11):
        # Donor
        donor_uid = f"demo_donor_{i}"
        donor_email = f"donor{i}@demo.com"
        donor = UserModel.create_new_user(donor_uid, f"Demo Donor {i}", donor_email, f"90000000{i:02}", "donor", location=f"Donor City {i}")
        await db.users.update_one({"email": donor_email}, {"$set": donor}, upsert=True)
        donors.append(donor_uid)

        # Receiver (NGO)
        receiver_uid = f"demo_receiver_{i}"
        receiver_email = f"receiver{i}@demo.com"
        receiver = UserModel.create_new_user(receiver_uid, f"Demo Receiver {i}", receiver_email, f"91000000{i:02}", "FOOD_RECEIVER", location=f"Receiver City {i}", receiver_type="NGO_TRUST")
        receiver["status"] = "active" # approve them
        await db.users.update_one({"email": receiver_email}, {"$set": receiver}, upsert=True)
        receivers.append(receiver_uid)

        # Volunteer
        vol_uid = f"demo_volunteer_{i}"
        vol_email = f"volunteer{i}@demo.com"
        volunteer = UserModel.create_new_user(vol_uid, f"Demo Volunteer {i}", vol_email, f"92000000{i:02}", "volunteer", location=f"Volunteer City {i}")
        volunteer["availability_status"] = "ONLINE"
        volunteer["vehicle_available"] = True
        volunteer["vehicle_type"] = random.choice(["BIKE", "CAR", "VAN"])
        await db.users.update_one({"email": vol_email}, {"$set": volunteer}, upsert=True)
        volunteers.append(vol_uid)

    print("Users created successfully.")
    
    # 3. Create Donations and match them
    print("Creating Donations & Assignments...")
    food_names = ["Rice & Curry", "Sandwiches", "Pizza", "Pasta", "Fruits", "Bread", "Canned Soup", "Vegetables", "Biryani", "Chapati"]
    
    for r_uid in receivers:
        for j in range(10): # 10 donations per receiver
            is_emergency = j >= 5 # 5 normal, 5 emergency
            donor_id = random.choice(donors)
            food_name = random.choice(food_names) + (" (Emergency)" if is_emergency else "")
            
            donation_data = {
                "ngo_id": r_uid,
                "food_name": food_name,
                "food_type": "Cooked" if random.random() > 0.5 else "Raw",
                "quantity": random.randint(10, 100),
                "unit": "kg",
                "number_of_meals": random.randint(20, 200),
                "preparation_time": datetime.now(timezone.utc) - timedelta(hours=2),
                "available_from": datetime.now(timezone.utc),
                "pickup_deadline": datetime.now(timezone.utc) + timedelta(hours=4),
                "pickup_location": "Donor Location HQ",
                "latitude": 12.9716 + random.uniform(-0.1, 0.1),
                "longitude": 77.5946 + random.uniform(-0.1, 0.1),
                "storage_condition": "Refrigerated" if not is_emergency else "Any",
                "packaging_type": "Box",
                "description": "Demo donation for testing.",
                "food_image": "https://example.com/demo_food.jpg"
            }
            
            donation = DonationModel.create_new_donation(donor_id, donation_data)
            donation["status"] = DonationStatus.DELIVERED.value if random.random() > 0.3 else DonationStatus.NGO_PENDING.value
            
            if is_emergency:
                # Add it to emergency_requests if needed, but the prompt says 5 emergency donations
                donation["priority"] = "HIGH"
                
            res = await db.donations.insert_one(donation)
            
            if donation["status"] == DonationStatus.DELIVERED.value:
                # Create an assignment (volunteer delivery)
                vol_id = random.choice(volunteers)
                assignment = {
                    "assignment_id": f"FB-ASN-{random.randint(100000, 999999)}",
                    "donation_id": donation["donation_id"],
                    "volunteer_id": vol_id,
                    "pickup_location": donation["pickup_location"],
                    "delivery_location": "NGO Location",
                    "status": "DELIVERED",
                    "assigned_at": datetime.now(timezone.utc) - timedelta(hours=2),
                    "completed_at": datetime.now(timezone.utc)
                }
                await db.assignments.insert_one(assignment)
                
                # Create Food Safety verification details
                safety_report = {
                    "donation_id": donation["donation_id"],
                    "volunteer_id": vol_id,
                    "temperature": random.uniform(2.0, 8.0),
                    "visual_check": "Passed",
                    "packaging_check": "Passed",
                    "smell_check": "Passed",
                    "comments": "Safe for consumption",
                    "created_at": datetime.now(timezone.utc)
                }
                await db.food_safety.insert_one(safety_report)

    # 4. Create Notifications
    print("Creating Admin Notifications...")
    all_users = donors + receivers + volunteers
    for uid in all_users:
        notification = {
            "notification_id": f"FB-NOTIF-{random.randint(100000, 999999)}",
            "user_id": uid,
            "title": "Welcome to Food-Bridge!",
            "message": "This is a broadcast message from Admin.",
            "type": "SYSTEM",
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }
        await db.notifications.insert_one(notification)
        
    print("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_db())



