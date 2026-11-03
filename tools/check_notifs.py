import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(r'd:\food bridge\backend\.env')
url = os.getenv('MONGODB_URL')

async def check():
    client = AsyncIOMotorClient(url)
    db = client['food-bridge_db']
    notifs = await db['notifications'].find({}).to_list(100)
    for i, n in enumerate(notifs):
        print(f"[{i}] title: {n.get('title')} | user_id: {n.get('user_id')} | type: {n.get('type')} | message: {n.get('message')}")

if __name__ == '__main__':
    asyncio.run(check())

