import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def clean_db():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['food-bridge_db']
    
    # 1. Genuine user accounts to keep
    keep_emails = [
        'vinay@gmail.com',
        'vinayaradhyav9036@gmail.com',
        'ffff@g.com',
        'admin@foodbridge.org',
        'vinaydev@food.com',
        'giminirelief@gmail.com'
    ]
    
    del_res = await db.users.delete_many({'email': {'$nin': keep_emails}})
    print(f'Deleted {del_res.deleted_count} test/deleted users from users collection.')
    
    # 2. Clear test donations
    don_del = await db.donations.delete_many({})
    print(f'Cleared {don_del.deleted_count} donations.')

    # 3. Clear assignments
    asg_del = await db.assignments.delete_many({})
    print(f'Cleared {asg_del.deleted_count} assignments.')

    # 4. Clear emergency_requests and emergencies
    emg1 = await db.emergencies.delete_many({})
    emg2 = await db.emergency_requests.delete_many({})
    print(f'Cleared {emg1.deleted_count} emergencies and {emg2.deleted_count} emergency requests.')

    # Print remaining users
    users = await db.users.find().to_list(100)
    print(f'Remaining genuine users count: {len(users)}')
    for u in users:
        print(f"  - {u.get('name')} ({u.get('email')}): {u.get('role')} (status: {u.get('status')}, verified: {u.get('verification_status')})")

if __name__ == '__main__':
    asyncio.run(clean_db())
