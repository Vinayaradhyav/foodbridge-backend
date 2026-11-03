import asyncio
import os
import hashlib
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config.settings import settings

def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

async def seed_data():
    print("Connecting to MongoDB at:", settings.MONGODB_URL)
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    
    # Clear collections for a fresh unified seed
    collections = ['users', 'donations', 'matches', 'assignments', 'deliveries', 'notifications', 'food_safety', 'audit_logs', 'emergency_requests', 'emergencies']
    for col in collections:
        await db[col].delete_many({})
        print(f"Cleared {col}")

    now = datetime.now(timezone.utc)
    common_pass = hash_password("password123")
    admin_pass = hash_password("admin123")

    # 1. Super Admin Accounts
    admins = [
        {
            "firebase_uid": "admin_super",
            "name": "Super Admin",
            "email": "admin@food-bridge.com",
            "phone": "9999999999",
            "role": "admin",
            "hashed_password": admin_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Food Bridge HQ, Bangalore",
            "created_at": now - timedelta(days=30),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "admin_demo",
            "name": "Super Admin Demo",
            "email": "admin@demo.com",
            "phone": "9000000000",
            "role": "admin",
            "hashed_password": admin_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Food Bridge Operations Center",
            "created_at": now - timedelta(days=30),
            "updated_at": now,
            "last_login": now
        }
    ]
    await db.users.insert_many(admins)
    print("Created Admin accounts")

    # 2. Donors
    donors = [
        {
            "firebase_uid": "donor_vinay",
            "name": "Vinay Aradhya",
            "email": "vinayaradhya@foodbridge.org",
            "phone": "9876543210",
            "role": "donor",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore Central, MG Road",
            "food_capacity": 300,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "created_at": now - timedelta(days=20),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "d1",
            "name": "Fresh Foods Bakery",
            "email": "contact@freshfoods.com",
            "phone": "+91 7777777771",
            "role": "donor",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru City",
            "food_capacity": 500,
            "latitude": 12.2958,
            "longitude": 76.6394,
            "created_at": now - timedelta(days=15),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "d2",
            "name": "City Star Hotel",
            "email": "admin@citystar.com",
            "phone": "+91 7777777772",
            "role": "donor",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore Central",
            "food_capacity": 800,
            "latitude": 12.9780,
            "longitude": 77.5990,
            "created_at": now - timedelta(days=12),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "d3",
            "name": "Green Leaf Cafe",
            "email": "hello@greenleaf.com",
            "phone": "+91 7777777773",
            "role": "donor",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "PENDING",
            "location": "Hubli",
            "food_capacity": 150,
            "latitude": 15.3647,
            "longitude": 75.1240,
            "created_at": now - timedelta(days=2),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "d4",
            "name": "Maha Laxmi Sweets",
            "email": "info@mahalaxmi.com",
            "phone": "+91 7777777774",
            "role": "donor",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru South",
            "food_capacity": 250,
            "latitude": 12.2850,
            "longitude": 76.6450,
            "created_at": now - timedelta(days=8),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "d5",
            "name": "Royal Dine Resto",
            "email": "manager@royaldine.in",
            "phone": "+91 7777777775",
            "role": "donor",
            "hashed_password": common_pass,
            "status": "suspended",
            "verification_status": "REJECTED",
            "location": "Bangalore East",
            "food_capacity": 400,
            "latitude": 12.9650,
            "longitude": 77.6200,
            "created_at": now - timedelta(days=25),
            "updated_at": now,
            "last_login": now
        }
    ]
    await db.users.insert_many(donors)
    print("Created Donor accounts")

    # 3. Receivers (Detailed and organized strictly by receiver_type)
    receivers = [
        # NGO_TRUST
        {
            "firebase_uid": "ngo_greenvalley",
            "name": "Green Valley NGO",
            "email": "contact@greenvalley.org",
            "phone": "9876543211",
            "role": "ngo",
            "receiver_type": "NGO_TRUST",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore South, Jayanagar",
            "food_capacity": 1200,
            "latitude": 12.9250,
            "longitude": 77.5938,
            "created_at": now - timedelta(days=20),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "t1",
            "name": "Global Welfare Trust",
            "email": "info@welfaretrust.org",
            "phone": "+91 9000000001",
            "role": "ngo",
            "receiver_type": "NGO_TRUST",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru Central",
            "food_capacity": 600,
            "latitude": 12.3050,
            "longitude": 76.6550,
            "created_at": now - timedelta(days=14),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "t2",
            "name": "Sanjeevini Trust",
            "email": "contact@sanjeevini.in",
            "phone": "+91 9000000002",
            "role": "ngo",
            "receiver_type": "NGO_TRUST",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore South",
            "food_capacity": 350,
            "latitude": 12.9150,
            "longitude": 77.5850,
            "created_at": now - timedelta(days=10),
            "updated_at": now,
            "last_login": now
        },

        # FOOD_BANK
        {
            "firebase_uid": "fb1",
            "name": "City Food Bank",
            "email": "contact@cityfoodbank.org",
            "phone": "+91 9000000005",
            "role": "ngo",
            "receiver_type": "FOOD_BANK",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore Central",
            "food_capacity": 2000,
            "latitude": 12.9800,
            "longitude": 77.6000,
            "created_at": now - timedelta(days=18),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "fb2",
            "name": "Community Harvest Food Bank",
            "email": "harvest@community.in",
            "phone": "+91 9000000006",
            "role": "ngo",
            "receiver_type": "FOOD_BANK",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru",
            "food_capacity": 1500,
            "latitude": 12.3100,
            "longitude": 76.6400,
            "created_at": now - timedelta(days=11),
            "updated_at": now,
            "last_login": now
        },

        # RELIEF_HUB
        {
            "firebase_uid": "rh1",
            "name": "Mysuru Emergency Relief Center",
            "email": "relief@mysuru.gov.in",
            "phone": "+91 9000000007",
            "role": "ngo",
            "receiver_type": "RELIEF_HUB",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru East",
            "food_capacity": 3000,
            "latitude": 12.3150,
            "longitude": 76.6600,
            "created_at": now - timedelta(days=16),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "rh2",
            "name": "Bangalore Flood Relief Camp",
            "email": "floodrelief@bangalore.org",
            "phone": "+91 9000000008",
            "role": "ngo",
            "receiver_type": "RELIEF_HUB",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Flood Relief Camp, Bangalore East",
            "food_capacity": 2500,
            "latitude": 12.9750,
            "longitude": 77.6500,
            "created_at": now - timedelta(days=5),
            "updated_at": now,
            "last_login": now
        },

        # COMMUNITY_ORGANIZATION
        {
            "firebase_uid": "o1",
            "name": "People For People Org",
            "email": "help@pfp.org",
            "phone": "+91 9000000003",
            "role": "ngo",
            "receiver_type": "COMMUNITY_ORGANIZATION",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Hubli",
            "food_capacity": 800,
            "latitude": 15.3500,
            "longitude": 75.1300,
            "created_at": now - timedelta(days=9),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "o2",
            "name": "Food Alliance Org",
            "email": "support@foodalliance.in",
            "phone": "+91 9000000004",
            "role": "ngo",
            "receiver_type": "COMMUNITY_ORGANIZATION",
            "hashed_password": common_pass,
            "status": "pending",
            "verification_status": "PENDING",
            "location": "Mangalore",
            "food_capacity": 500,
            "latitude": 12.9141,
            "longitude": 74.8560,
            "created_at": now - timedelta(days=1),
            "updated_at": now,
            "last_login": now
        },

        # SHELTER_CARE_CENTER
        {
            "firebase_uid": "r1",
            "name": "Smile Foundation Orphanage",
            "email": "contact@smile.org",
            "phone": "+91 9999911111",
            "role": "ngo",
            "receiver_type": "SHELTER_CARE_CENTER",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru City",
            "food_capacity": 1000,
            "latitude": 12.3000,
            "longitude": 76.6400,
            "created_at": now - timedelta(days=22),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "r6",
            "name": "Silver Age Old Age Home",
            "email": "silverage@home.in",
            "phone": "+91 9999922221",
            "role": "ngo",
            "receiver_type": "SHELTER_CARE_CENTER",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru South",
            "food_capacity": 100,
            "latitude": 12.2800,
            "longitude": 76.6350,
            "created_at": now - timedelta(days=19),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "r11",
            "name": "City Homeless Shelter",
            "email": "shelter@city.org",
            "phone": "+91 9999933331",
            "role": "ngo",
            "receiver_type": "SHELTER_CARE_CENTER",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore Central",
            "food_capacity": 500,
            "latitude": 12.9700,
            "longitude": 77.5800,
            "created_at": now - timedelta(days=17),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "r5",
            "name": "Angel House Orphanage",
            "email": "angel@house.org",
            "phone": "+91 9999911115",
            "role": "ngo",
            "receiver_type": "SHELTER_CARE_CENTER",
            "hashed_password": common_pass,
            "status": "suspended",
            "verification_status": "REJECTED",
            "location": "Mysuru North",
            "food_capacity": 100,
            "latitude": 12.3300,
            "longitude": 76.6450,
            "created_at": now - timedelta(days=25),
            "updated_at": now,
            "last_login": now
        }
    ]
    await db.users.insert_many(receivers)
    print("Created Receiver accounts across all categories")

    # 4. Volunteers
    volunteers = [
        {
            "firebase_uid": "vol_rohit",
            "name": "Rohit Kumar",
            "email": "rohit.kumar@foodbridge.org",
            "phone": "9876543212",
            "role": "volunteer",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore Central, Indiranagar",
            "availability_status": "ONLINE",
            "vehicle_available": True,
            "vehicle_type": "Two Wheeler",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "created_at": now - timedelta(days=20),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "vol2",
            "name": "Priya Sharma",
            "email": "priya@foodbridge.org",
            "phone": "+91 9988776653",
            "role": "volunteer",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Bangalore South",
            "availability_status": "ONLINE",
            "vehicle_available": True,
            "vehicle_type": "Four Wheeler",
            "latitude": 12.9200,
            "longitude": 77.5900,
            "created_at": now - timedelta(days=12),
            "updated_at": now,
            "last_login": now
        },
        {
            "firebase_uid": "vol3",
            "name": "Rahul V",
            "email": "rahul@foodbridge.org",
            "phone": "+91 9988776651",
            "role": "volunteer",
            "hashed_password": common_pass,
            "status": "active",
            "verification_status": "VERIFIED",
            "location": "Mysuru City",
            "availability_status": "ONLINE",
            "vehicle_available": True,
            "vehicle_type": "Two Wheeler",
            "latitude": 12.3000,
            "longitude": 76.6400,
            "created_at": now - timedelta(days=10),
            "updated_at": now,
            "last_login": now
        }
    ]
    await db.users.insert_many(volunteers)
    print("Created Volunteer accounts")

    # 5. Connected Live Donations (Directly tied to Donors, Receivers, and Volunteers)
    donations = [
        {
            "donation_id": "DON-VINAY-101",
            "donor_id": "donor_vinay",
            "donor_name": "Vinay Aradhya",
            "food_name": "Fresh Cooked Vegetable Biryani",
            "food_type": "Cooked Food",
            "category": "Prepared Meals",
            "veg_nonveg": "Vegetarian",
            "quantity": 45.0,
            "unit": "meals",
            "number_of_meals": 45,
            "preparation_time": now - timedelta(minutes=45),
            "available_from": now - timedelta(minutes=30),
            "pickup_deadline": now + timedelta(hours=4),
            "pickup_location": "Bangalore Central, MG Road",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "storage_condition": "Hot / Insulated",
            "packaging_type": "Steel Containers",
            "status": "AVAILABLE",
            "created_at": now - timedelta(minutes=45),
            "updated_at": now
        },
        {
            "donation_id": "DON-VINAY-102",
            "donor_id": "donor_vinay",
            "donor_name": "Vinay Aradhya",
            "food_name": "Sandwiches & Fruit Snack Boxes",
            "food_type": "Cooked Food",
            "category": "Snacks",
            "veg_nonveg": "Vegetarian",
            "quantity": 30.0,
            "unit": "meals",
            "number_of_meals": 30,
            "preparation_time": now - timedelta(hours=2),
            "available_from": now - timedelta(hours=2),
            "pickup_deadline": now + timedelta(hours=3),
            "pickup_location": "Bangalore Central, MG Road",
            "latitude": 12.9720,
            "longitude": 77.5950,
            "storage_condition": "Room Temp",
            "packaging_type": "Cardboard Boxes",
            "status": "IN_TRANSIT",
            "ngo_id": "ngo_greenvalley",
            "accepted_by": "Green Valley NGO",
            "assigned_volunteer_id": "vol_rohit",
            "volunteer_name": "Rohit Kumar",
            "pickup_otp": "4829",
            "delivery_otp": "7193",
            "created_at": now - timedelta(hours=2),
            "updated_at": now
        },
        {
            "donation_id": "DON-VINAY-103",
            "donor_id": "donor_vinay",
            "donor_name": "Vinay Aradhya",
            "food_name": "Steamed Idli & Vegetable Sambar",
            "food_type": "Cooked Food",
            "category": "Prepared Meals",
            "veg_nonveg": "Vegetarian",
            "quantity": 50.0,
            "unit": "meals",
            "number_of_meals": 50,
            "preparation_time": now - timedelta(hours=4),
            "available_from": now - timedelta(hours=4),
            "pickup_deadline": now + timedelta(hours=2),
            "pickup_location": "Bangalore Central, MG Road",
            "latitude": 12.9715,
            "longitude": 77.5948,
            "storage_condition": "Hot / Insulated",
            "packaging_type": "Insulated Carriers",
            "status": "MATCHED",
            "ngo_id": "ngo_greenvalley",
            "accepted_by": "Green Valley NGO",
            "created_at": now - timedelta(hours=4),
            "updated_at": now
        },
        {
            "donation_id": "DON-VINAY-104",
            "donor_id": "donor_vinay",
            "donor_name": "Vinay Aradhya",
            "food_name": "High Protein Dal & Brown Rice",
            "food_type": "Cooked Food",
            "category": "Prepared Meals",
            "veg_nonveg": "Vegetarian",
            "quantity": 60.0,
            "unit": "meals",
            "number_of_meals": 60,
            "preparation_time": now - timedelta(days=1),
            "available_from": now - timedelta(days=1),
            "pickup_deadline": now - timedelta(hours=18),
            "pickup_location": "Bangalore Central, MG Road",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "storage_condition": "Room Temp",
            "packaging_type": "Containers",
            "status": "COMPLETED",
            "ngo_id": "ngo_greenvalley",
            "accepted_by": "Green Valley NGO",
            "assigned_volunteer_id": "vol_rohit",
            "volunteer_name": "Rohit Kumar",
            "created_at": now - timedelta(days=1),
            "updated_at": now
        },
        {
            "donation_id": "DON-BAKERY-201",
            "donor_id": "d1",
            "donor_name": "Fresh Foods Bakery",
            "food_name": "Fresh Whole Wheat Breads & Buns",
            "food_type": "Packaged Food",
            "category": "Bakery",
            "veg_nonveg": "Vegetarian",
            "quantity": 100.0,
            "unit": "packets",
            "number_of_meals": 100,
            "preparation_time": now - timedelta(hours=3),
            "available_from": now - timedelta(hours=3),
            "pickup_deadline": now + timedelta(hours=12),
            "pickup_location": "Mysuru City Bakery Store",
            "latitude": 12.2958,
            "longitude": 76.6394,
            "storage_condition": "Room Temp",
            "packaging_type": "Crates",
            "status": "IN_TRANSIT",
            "ngo_id": "r1",
            "accepted_by": "Smile Foundation Orphanage",
            "assigned_volunteer_id": "vol_rohit",
            "volunteer_name": "Rohit Kumar",
            "pickup_otp": "1290",
            "delivery_otp": "5531",
            "created_at": now - timedelta(hours=3),
            "updated_at": now
        },
        {
            "donation_id": "DON-HOTEL-301",
            "donor_id": "d2",
            "donor_name": "City Star Hotel",
            "food_name": "Prepared Dinner Buffet Packs",
            "food_type": "Cooked Food",
            "category": "Prepared Meals",
            "veg_nonveg": "Non-Vegetarian",
            "quantity": 120.0,
            "unit": "meals",
            "number_of_meals": 120,
            "preparation_time": now - timedelta(hours=5),
            "available_from": now - timedelta(hours=5),
            "pickup_deadline": now + timedelta(hours=2),
            "pickup_location": "Bangalore Central Hotel Kitchen",
            "latitude": 12.9780,
            "longitude": 77.5990,
            "storage_condition": "Hot / Insulated",
            "packaging_type": "Boxes",
            "status": "MATCHED",
            "ngo_id": "fb1",
            "accepted_by": "City Food Bank",
            "created_at": now - timedelta(hours=5),
            "updated_at": now
        },
        {
            "donation_id": "DON-SWEETS-401",
            "donor_id": "d4",
            "donor_name": "Maha Laxmi Sweets",
            "food_name": "Sweets & Snack Savories Assortment",
            "food_type": "Packaged Food",
            "category": "Sweets",
            "veg_nonveg": "Vegetarian",
            "quantity": 35.0,
            "unit": "packets",
            "number_of_meals": 35,
            "preparation_time": now - timedelta(days=2),
            "available_from": now - timedelta(days=2),
            "pickup_deadline": now - timedelta(days=1),
            "pickup_location": "Mysuru South Sweet Shop",
            "latitude": 12.2850,
            "longitude": 76.6450,
            "storage_condition": "Room Temp",
            "packaging_type": "Gift Boxes",
            "status": "COMPLETED",
            "ngo_id": "r6",
            "accepted_by": "Silver Age Old Age Home",
            "created_at": now - timedelta(days=2),
            "updated_at": now
        },
        {
            "donation_id": "DON-CAFE-501",
            "donor_id": "d3",
            "donor_name": "Green Leaf Cafe",
            "food_name": "Vegetable Wraps & Fresh Salads",
            "food_type": "Cooked Food",
            "category": "Prepared Meals",
            "veg_nonveg": "Vegetarian",
            "quantity": 25.0,
            "unit": "meals",
            "number_of_meals": 25,
            "preparation_time": now - timedelta(hours=1),
            "available_from": now - timedelta(hours=1),
            "pickup_deadline": now + timedelta(hours=5),
            "pickup_location": "Hubli City Center",
            "latitude": 15.3647,
            "longitude": 75.1240,
            "storage_condition": "Refrigerated",
            "packaging_type": "Packs",
            "status": "AVAILABLE",
            "created_at": now - timedelta(hours=1),
            "updated_at": now
        }
    ]
    await db.donations.insert_many(donations)
    print("Created live connected Donations")

    # 6. Connected Emergency Requests
    emergencies = [
        {
            "request_id": "EMG-RELIEF-01",
            "created_by": "rh2",
            "organization_name": "Bangalore Flood Relief Camp",
            "food_type": "Prepared Hot Meals",
            "quantity": 150,
            "number_of_people": 150,
            "location": "Flood Relief Camp, Bangalore East",
            "latitude": 12.9750,
            "longitude": 77.6500,
            "emergency_type": "FLOOD",
            "urgency": "HIGH",
            "deadline": now + timedelta(hours=6),
            "description": "Urgent meals needed for flood-affected families relocated to camp.",
            "status": "active",
            "created_at": now - timedelta(hours=2)
        },
        {
            "request_id": "EMG-ORPHAN-02",
            "created_by": "r1",
            "organization_name": "Smile Foundation Orphanage",
            "food_type": "Nutritious Meals & Milk",
            "quantity": 60,
            "number_of_people": 60,
            "location": "Mysuru City Orphanage Campus",
            "latitude": 12.3000,
            "longitude": 76.6400,
            "emergency_type": "GENERAL",
            "urgency": "HIGH",
            "deadline": now + timedelta(hours=8),
            "description": "Weekend food shortage for 60 residing children.",
            "status": "active",
            "created_at": now - timedelta(hours=3)
        },
        {
            "request_id": "EMG-SHELTER-03",
            "created_by": "r11",
            "organization_name": "City Homeless Shelter",
            "food_type": "Warm Dinner Packs",
            "quantity": 80,
            "number_of_people": 80,
            "location": "Bangalore Central Night Shelter",
            "latitude": 12.9700,
            "longitude": 77.5800,
            "emergency_type": "NIGHT_COLD",
            "urgency": "HIGH",
            "deadline": now + timedelta(hours=4),
            "description": "Cold night relief dinner for homeless shelter occupants.",
            "status": "active",
            "created_at": now - timedelta(hours=1)
        }
    ]
    await db.emergency_requests.insert_many([dict(e) for e in emergencies])
    await db.emergencies.insert_many([dict(e) for e in emergencies])
    print("Created live Emergency Requests in both collections")

    # 7. Assignments
    assignments = [
        {
            "assignment_id": "ASG-ROHIT-01",
            "donation_id": "DON-VINAY-102",
            "volunteer_id": "vol_rohit",
            "volunteer_name": "Rohit Kumar",
            "donor_name": "Vinay Aradhya",
            "pickup_location": "Bangalore Central, MG Road",
            "delivery_location": "Bangalore South, Jayanagar (Green Valley NGO)",
            "pickup_otp": "4829",
            "delivery_otp": "7193",
            "status": "IN_TRANSIT",
            "created_at": now - timedelta(hours=2),
            "updated_at": now
        },
        {
            "assignment_id": "ASG-ROHIT-02",
            "donation_id": "DON-BAKERY-201",
            "volunteer_id": "vol_rohit",
            "volunteer_name": "Rohit Kumar",
            "donor_name": "Fresh Foods Bakery",
            "pickup_location": "Mysuru City Bakery Store",
            "delivery_location": "Mysuru City Orphanage Campus (Smile Foundation)",
            "pickup_otp": "1290",
            "delivery_otp": "5531",
            "status": "IN_TRANSIT",
            "created_at": now - timedelta(hours=3),
            "updated_at": now
        }
    ]
    await db.assignments.insert_many(assignments)
    print("Created live Assignments")

    # 8. Notifications
    notifications = [
        {
            "user_id": "donor_vinay",
            "title": "Donation In Transit",
            "body": "Volunteer Rohit Kumar has picked up your donation of Sandwiches & Fruit Snack Boxes.",
            "type": "DONATION_STATUS",
            "read": False,
            "created_at": now - timedelta(hours=1)
        },
        {
            "user_id": "ngo_greenvalley",
            "title": "Incoming Food Delivery",
            "body": "Delivery on the way from Vinay Aradhya. Estimated arrival in 25 mins.",
            "type": "DELIVERY_ALERT",
            "read": False,
            "created_at": now - timedelta(hours=1)
        },
        {
            "user_id": "vol_rohit",
            "title": "New Pickup Assigned",
            "body": "You have been assigned to pick up 45 meals from Vinay Aradhya at MG Road.",
            "type": "ASSIGNMENT",
            "read": True,
            "created_at": now - timedelta(hours=2)
        },
        {
            "user_id": "admin",
            "title": "Emergency Request Logged",
            "body": "Bangalore Flood Relief Camp logged emergency request for 150 meals.",
            "type": "ADMIN_ALERT",
            "read": False,
            "created_at": now - timedelta(hours=2)
        }
    ]
    await db.notifications.insert_many(notifications)
    print("Created Notifications")

    # 9. Audit Logs
    audit_logs = [
        {
            "action": "DONATION_CREATED",
            "user_id": "donor_vinay",
            "details": "Created live donation DON-VINAY-101",
            "timestamp": now - timedelta(minutes=45)
        },
        {
            "action": "DONATION_MATCHED",
            "user_id": "ngo_greenvalley",
            "details": "Matched with Green Valley NGO",
            "timestamp": now - timedelta(hours=2)
        },
        {
            "action": "ASSIGNMENT_DISPATCHED",
            "user_id": "vol_rohit",
            "details": "Assigned to Rohit Kumar for delivery",
            "timestamp": now - timedelta(hours=2)
        }
    ]
    await db.audit_logs.insert_many(audit_logs)
    print("Created Audit Logs")

    print("\nDatabase seeding completed successfully!")
    u_count = await db.users.count_documents({})
    d_count = await db.donations.count_documents({})
    e_count = await db.emergency_requests.count_documents({})
    a_count = await db.assignments.count_documents({})
    print(f"Summary: {u_count} Users, {d_count} Donations, {e_count} Emergencies, {a_count} Assignments.")

if __name__ == "__main__":
    asyncio.run(seed_data())
