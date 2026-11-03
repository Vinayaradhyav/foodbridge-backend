from datetime import datetime, timezone
from typing import Optional, Dict, Any
from bson import ObjectId

class DonorModel:
    @staticmethod
    def create_new_donor(full_name: str, email: str, mobile_number: str, auth_provider: str = "email") -> Dict[str, Any]:
        return {
            "full_name": full_name,
            "email": email,
            "mobile_number": mobile_number,
            "auth_provider": auth_provider,
            "account_status": "active",
            "role": "donor",
            "created_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc)
        }
    
    @staticmethod
    def format_for_response(donor_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MongoDB document to Pydantic response format"""
        if not donor_doc:
            return None
        
        response = dict(donor_doc)
        if "_id" in response:
            response["id"] = str(response["_id"])
            del response["_id"]
        return response
