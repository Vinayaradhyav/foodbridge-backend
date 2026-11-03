import logging
from bson import ObjectId
from app.database.mongodb import get_database

logger = logging.getLogger(__name__)

class NgoService:
    @property
    def collection(self):
        db = get_database()
        if db is not None:
            return db.ngos
        return None

    async def get_ngo(self, ngo_id: str) -> dict:
        """Fetch a specific NGO profile by ID."""
        coll = self.collection
        if coll is None:
            return {"error": "Database not connected"}
            
        try:
            ngo = await coll.find_one({"_id": ObjectId(ngo_id)})
            if ngo:
                ngo["id"] = str(ngo.pop("_id"))
            return ngo
        except Exception as e:
            logger.error(f"Error fetching NGO {ngo_id}: {e}")
            return None

    async def create_ngo(self, ngo_data: dict) -> str:
        """Create a new NGO profile."""
        coll = self.collection
        if coll is None:
            return None
            
        try:
            ngo_data["is_verified"] = False
            result = await coll.insert_one(ngo_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating NGO: {e}")
            return None

    async def update_verification_status(self, ngo_id: str, is_verified: bool) -> bool:
        """Update the verification status of an NGO."""
        coll = self.collection
        if coll is None:
            return False
            
        try:
            result = await coll.update_one(
                {"_id": ObjectId(ngo_id)},
                {"$set": {"is_verified": is_verified}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating NGO status {ngo_id}: {e}")
            return False

ngo_service = NgoService()
