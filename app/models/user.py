from datetime import datetime, timezone
from typing import Optional, Dict, Any
from bson import ObjectId

class UserModel:
    @staticmethod
    def create_new_user(
        firebase_uid: str,
        name: str, 
        email: str, 
        phone: str, 
        role: str,
        location: str = "",
        receiver_type: str = None
    ) -> Dict[str, Any]:
        """
        Create a new user document for MongoDB.
        Uses Firebase UID as the unique identifier where possible, or object ID if omitted.
        """
        return {
            "firebase_uid": firebase_uid,
            "name": name,
            "email": email,
            "phone": phone,
            "role": role,
            "receiver_type": receiver_type,
            "location": location,
            "status": "active",
            "verification_status": "VERIFIED" if role.lower() in ["donor", "volunteer", "admin"] else "PENDING",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc)
        }
    
    @staticmethod
    def format_for_response(user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MongoDB document to Pydantic response format"""
        if not user_doc:
            return None
        
        response = dict(user_doc)
        if "_id" in response:
            response["id"] = str(response["_id"])
            del response["_id"]
        # Security hardening: Strip sensitive security credentials from response
        if "hashed_password" in response:
            del response["hashed_password"]
        if "password" in response:
            del response["password"]
        return response

