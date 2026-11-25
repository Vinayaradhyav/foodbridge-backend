"""
FoodBridge Enterprise Base Repository.
Provides standard asynchronous CRUD abstractions for MongoDB collections.
"""
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId

class BaseRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def get_by_id(self, id_str: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.collection.find_one({"_id": ObjectId(id_str)})
        except Exception:
            return await self.collection.find_one({"id": id_str})

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one(query)

    async def find_many(self, query: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find(query).limit(limit)
        return await cursor.to_list(length=limit)
