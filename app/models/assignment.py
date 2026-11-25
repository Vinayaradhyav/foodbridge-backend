import secrets
from datetime import datetime, timezone
from typing import Dict, Any

class AssignmentModel:
    @staticmethod
    def create_new_assignment(assignment_data: dict) -> Dict[str, Any]:
        """
        Create a new assignment document for MongoDB.
        """
        fallback_otp = str(secrets.randbelow(9000) + 1000)
        return {
            "donation_id": assignment_data.get("donation_id"),
            "volunteer_id": assignment_data.get("volunteer_id"),
            "pickup_location": assignment_data.get("pickup_location"),
            "delivery_location": assignment_data.get("delivery_location"),
            "status": "PENDING",
            "pickup_otp": fallback_otp,
            "delivery_otp": fallback_otp,
            "handover_otp": fallback_otp,
            "assigned_at": datetime.now(timezone.utc),
            "accepted_at": None,
            "completed_at": None
        }
    
    @staticmethod
    def format_for_response(assignment_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MongoDB document to Pydantic response format"""
        if not assignment_doc:
            return None
        
        response = dict(assignment_doc)
        if "_id" in response:
            response["assignment_id"] = str(response["_id"])
            del response["_id"]
        return response
