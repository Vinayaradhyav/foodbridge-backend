from datetime import datetime, timezone
from typing import Dict, Any
import uuid

class DonationModel:
    @staticmethod
    def create_new_donation(donor_id: str, donation_data: dict) -> Dict[str, Any]:
        """
        Create a new donation document for MongoDB.
        Uses standardized unique collision-resistant ID DON-{YYYYMMDD}-{UUID8}.
        """
        ngo_id = donation_data.get("ngo_id")
        status = "NGO_PENDING" if ngo_id else "AVAILABLE"
        
        today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        ref_id = f"DON-{today_str}-{uuid.uuid4().hex[:8].upper()}"

        return {
            "donation_id": ref_id, # Custom requested UI ID
            "donor_id": donor_id,
            "food_name": donation_data.get("food_name"),
            "food_type": donation_data.get("food_type"),
            "quantity": donation_data.get("quantity"),
            "unit": donation_data.get("unit"),
            "number_of_meals": donation_data.get("number_of_meals"),
            "preparation_time": donation_data.get("preparation_time"),
            "available_from": donation_data.get("available_from"),
            "pickup_deadline": donation_data.get("pickup_deadline"),
            "pickup_location": donation_data.get("pickup_location"),
            "latitude": donation_data.get("latitude"),
            "longitude": donation_data.get("longitude"),
            "storage_condition": donation_data.get("storage_condition"),
            "packaging_type": donation_data.get("packaging_type"),
            "description": donation_data.get("description", ""),
            "food_image": donation_data.get("food_image", ""),
            "status": status,
            "ngo_id": ngo_id,
            "accepted_by": None,
            "rejected_by": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
    
    @staticmethod
    def format_for_response(donation_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MongoDB document to Pydantic response format"""
        if not donation_doc:
            return None
        
        response = dict(donation_doc)
        if "_id" in response:
            if "donation_id" not in response:
                response["donation_id"] = str(response["_id"])
            del response["_id"]
        return response
