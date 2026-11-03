import asyncio
import hashlib
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.security import verify_password

async def test():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['food-bridge_db']
    
    vinay = await db.users.find_one({'phone': '8971460118'})
    print("Vinay doc:", vinay)
    hp = vinay.get('hashed_password')
    print("Hashed password:", hp)
    
    print("vinay118 matches:", verify_password('vinay118', hp))
    print("Vinay118 matches:", verify_password('Vinay118', hp))
    print("User@123 matches:", verify_password('User@123', hp))

    if hp and '$' in hp:
        salt, h = hp.split('$', 1)
        print("Salt:", salt, "Hash:", h)
        for test_pw in ['vinay118', 'Vinay118', 'vinay118@', 'vinay@118', 'vinay123', 'Vinay123', 'User@123', 'password', '8971460118', 'vinayaradhya', 'vinay']:
            cand = hashlib.sha256((test_pw + salt).encode('utf-8')).hexdigest()
            if cand == h:
                print(f"FOUND MATCHING PASSWORD: '{test_pw}'")

    gimini = await db.users.find_one({'phone': '9036810242'})
    print("\nGimini doc:", gimini)

asyncio.run(test())
