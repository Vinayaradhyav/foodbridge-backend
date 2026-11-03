import random
from datetime import datetime, timezone
from typing import Dict, Any

class AssignmentModel:
    @staticmethod
    def create_new_assignment(assignment_data: dict) -> Dict[str, Any]:
        """
        Create a new assignment document for MongoDB.
        """
        return {
            "donation_id": assignment_data.get("donation_id"),
            "volunteer_id": assignment_data.get("volunteer_id"),
            "pickup_location": assignment_data.get("pickup_location"),
            "delivery_location": assignment_data.get("delivery_location"),
            "status": "PENDING",
            "pickup_otp": str(random.randint(1000, 9999)),
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
