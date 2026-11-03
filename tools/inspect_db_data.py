import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def print_data():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['food-bridge_db']
    
    print('=== DONATIONS IN MONGODB ===')
    dons = await db.donations.find().to_list(100)
    for d in dons:
        d['_id'] = str(d['_id'])
        print(f"ID: {d.get('_id')}, donation_id: {d.get('donation_id')}, donor_name: {d.get('donor_name')}, food_name: {d.get('food_name')}, quantity: {d.get('quantity')}, status: {d.get('status')}")

    print('\n=== USERS IN MONGODB ===')
    users = await db.users.find().to_list(100)
    print(f'Total users count: {len(users)}')
    for u in users:
        print(f"ID: {u.get('_id')}, email: {u.get('email')}, name: {u.get('name')}, role: {u.get('role')}")

if __name__ == '__main__':
    asyncio.run(print_data())
