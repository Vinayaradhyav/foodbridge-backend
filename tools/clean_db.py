import asyncio
from app.database.mongodb import mongodb, connect_to_mongo

async def cleanup():
    await connect_to_mongo()
    db = mongodb.db

    # Clean users: keep only Vinay Aradhya (donor), Akshaya Patra Foundation (receiver), Arjun Sharma (volunteer), admin
    await db.users.delete_many({
        "email": {"$nin": [
            "vinayaradhya@foodbridge.org",
            "donor@foodbridge.org",
            "receiver@foodbridge.org",
            "ngo@foodbridge.org",
            "volunteer@foodbridge.org",
            "admin@foodbridge.org",
            "admin@test.com",
            "admin@food-bridge.com"
        ]}
    })

    # Ensure legitimate accounts exist
    # 1. Donor
    await db.users.update_one(
        {"email": "vinayaradhya@foodbridge.org"},
        {"$set": {
            "name": "Vinay Aradhya",
            "email": "vinayaradhya@foodbridge.org",
            "phone": "+91 9876543211",
            "role": "DONOR",
            "location": "Indiranagar 100ft Road, Bangalore",
            "status": "active",
            "verification_status": "VERIFIED",
            "food_capacity": 500
        }},
        upsert=True
    )

    # 2. Receiver (Akshaya Patra Foundation)
    await db.users.update_one(
        {"email": "ngo@foodbridge.org"},
        {"$set": {
            "name": "Akshaya Patra Foundation",
            "email": "ngo@foodbridge.org",
            "phone": "+91 9876543212",
            "role": "FOOD_RECEIVER",
            "receiver_type": "NGO_TRUST",
            "location": "Rajajinagar Relief Center, Bangalore",
            "status": "active",
            "verification_status": "VERIFIED",
            "contact_person": "S. Ranganathan",
            "food_capacity": 3000,
            "beneficiary_capacity": 2500,
            "vehicle_availability": True
        }},
        upsert=True
    )

    # 3. Volunteer
    await db.users.update_one(
        {"email": "volunteer@foodbridge.org"},
        {"$set": {
            "name": "Arjun Sharma",
            "email": "volunteer@foodbridge.org",
            "phone": "+91 9876543213",
            "role": "VOLUNTEER",
            "location": "HSR Layout Sector 2, Bangalore",
            "status": "active",
            "verification_status": "VERIFIED",
            "vehicle_available": True,
            "vehicle_type": "Insulated Delivery Van",
            "availability_status": "AVAILABLE"
        }},
        upsert=True
    )

    # 4. Admin
    await db.users.update_one(
        {"email": "admin@test.com"},
        {"$set": {
            "name": "Food-Bridge Executive Admin",
            "email": "admin@test.com",
            "phone": "+91 9876543210",
            "role": "ADMIN",
            "location": "Central Control HQ, Bangalore",
            "status": "active",
            "verification_status": "VERIFIED"
        }},
        upsert=True
    )

    # Clean donations: reset to 2 verified donations from donor Vinay Aradhya
    await db.donations.delete_many({})
    
    clean_donations = [
        {
            "donation_id": "DON-VINAY-101",
            "donor_name": "Vinay Aradhya",
            "donor_email": "vinayaradhya@foodbridge.org",
            "food_name": "Fresh Cooked Vegetable Biryani and Dal",
            "food_type": "Prepared Meals",
            "category": "Prepared Meals",
            "veg_nonveg": "Vegetarian",
            "quantity": 50,
            "unit": "meals",
            "status": "AVAILABLE",
            "pickup_location": "Indiranagar 100ft Road, Bangalore",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "storage_condition": "Hot Insulated Container",
            "packaging_type": "Thermal Food Trays",
            "description": "Freshly cooked surplus biryani and dal, hygienic and packed.",
            "accepted_by": None,
            "assigned_volunteer": None
        },
        {
            "donation_id": "DON-VINAY-102",
            "donor_name": "Vinay Aradhya",
            "donor_email": "vinayaradhya@foodbridge.org",
            "food_name": "Nutritious Chapati, Mixed Vegetable Curry and Rice",
            "food_type": "Prepared Meals",
            "category": "Prepared Meals",
            "veg_nonveg": "Vegetarian",
            "quantity": 40,
            "unit": "meals",
            "status": "AVAILABLE",
            "pickup_location": "Indiranagar 100ft Road, Bangalore",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "storage_condition": "Room Temp",
            "packaging_type": "Sealed Foil Boxes",
            "description": "Packed nutritious warm meal boxes ready for immediate hunger relief.",
            "accepted_by": None,
            "assigned_volunteer": None
        }
    ]

    for d in clean_donations:
        await db.donations.insert_one(d)

    print('Cleaned MongoDB successfully!')
    print('Users remaining:', await db.users.count_documents({}))
    async for u in db.users.find():
        print('  User:', u.get('name'), '|', u.get('email'), '|', u.get('role'))
    print('Donations remaining:', await db.donations.count_documents({}))
    async for d in db.donations.find():
        print('  Donation:', d.get('donation_id'), '|', d.get('food_name'), '|', d.get('status'), '|', d.get('donor_name'))

if __name__ == '__main__':
    asyncio.run(cleanup())
