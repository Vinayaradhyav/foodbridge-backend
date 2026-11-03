import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(r'd:\food bridge\backend\.env')
url = os.getenv('MONGODB_URL')
name = os.getenv('DATABASE_NAME')

async def check():
    client = AsyncIOMotorClient(url)
    db = client[name]
    collections = await db.list_collection_names()
    print('DB:', name)
    print('Collections:', collections)
    users = await db['users'].find({}).to_list(100)
    print('Total users:', len(users))
    for u in users:
        print(f"User: {u.get('name')} | Email: {u.get('email')} | Phone: {u.get('phone')} | Role: {u.get('role')} | Status: {u.get('status')} | Verified: {u.get('is_verified')}")
    notifs = await db['notifications'].find({}).to_list(100)
    print('Total notifs:', len(notifs))
    for n in notifs[:10]:
        print(f"Notif: {n.get('title')} | {n.get('message')}")

if __name__ == '__main__':
    asyncio.run(check())
