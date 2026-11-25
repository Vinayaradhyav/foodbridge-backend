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
        receiver_type: Optional[str] = None
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
    def format_for_response(user_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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

        # Ensure required fields for UserResponse schema are never None/missing
        if not response.get("firebase_uid"):
            response["firebase_uid"] = response.get("id") or str(user_doc.get("_id", "unknown_uid"))
        raw_phone = str(response.get("phone", "")).strip()
        if not raw_phone or len(raw_phone) < 4:
            response["phone"] = "0000000000"
        if not response.get("name"):
            response["name"] = response.get("organization_name") or str(response.get("email", "FoodBridge User")).split("@")[0]
        if not response.get("role"):
            response["role"] = "DONOR"
        if not response.get("status"):
            response["status"] = "active"
        if not response.get("location"):
            response["location"] = ""

        # Normalize profile image URLs
        img_url = response.get("profile_image_url") or response.get("avatar_url") or response.get("profile_image")
        if img_url:
            response["profile_image_url"] = img_url
            response["avatar_url"] = img_url
            response["profile_image"] = img_url

        return response

