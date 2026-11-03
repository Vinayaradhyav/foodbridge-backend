import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(r'd:\food bridge\backend\.env')
url = os.getenv('MONGODB_URL')

async def check():
    client = AsyncIOMotorClient(url)
    dbs = await client.list_database_names()
    print('All databases:', dbs)
    for db_name in dbs:
        if db_name in ['admin', 'local']: continue
        db = client[db_name]
        colls = await db.list_collection_names()
        print(f"--- DB: {db_name} (Collections: {colls}) ---")
        for c in colls:
            count = await db[c].count_documents({})
            print(f"  {c}: {count} documents")
            # check for 'Test Volunteer' or 'Test NGO'
            sample = await db[c].find({'name': {'$regex': 'Test', '$options': 'i'}}).to_list(10)
            if sample:
                print(f"    FOUND Test in {c}: {[s.get('name') for s in sample]}")

if __name__ == '__main__':
    asyncio.run(check())

