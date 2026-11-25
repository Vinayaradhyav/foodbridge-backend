from pydantic import BaseModel
from typing import Optional, List, Tuple, Any

class NLPRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    existing_draft: Optional[dict] = None

class NLPEmergencyResponse(BaseModel):
    food_category: Optional[str] = "Cooked Meals"
    food_name: Optional[str] = "Cooked Meals"
    food_type: Optional[str] = "Cooked Meals"
    quantity: Optional[int] = None
    food_quantity: Optional[int] = None
    quantity_unit: Optional[str] = "meals"
    number_of_people: Optional[int] = None
    beneficiaries: Optional[int] = None
    people_affected: Optional[int] = 0
    urgency: Optional[str] = "HIGH"
    urgency_level: Optional[str] = "HIGH"
    emergency_type: Optional[str] = "COMMUNITY_EMERGENCY"
    delivery_location: Optional[str] = None
    delivery_coordinates: Optional[List[float]] = None
    location: Optional[str] = None
    cooking_required: Optional[bool] = True
    packaging_required: Optional[bool] = False
    water_quantity: Optional[int] = None
    delivery_time: Optional[str] = None
    storage_requirements: Optional[str] = None
    food_condition: Optional[str] = None
    additional_requirements: Optional[str] = None
    additional_instructions: Optional[str] = None
    original_language: Optional[str] = "en"
    original_transcript: Optional[str] = None
    english_translation: Optional[str] = None
    missing_fields: Optional[List[str]] = []
    is_complete: bool = False
    deadline: Optional[str] = None
    confidence: float = 0.95

    model_config = {"extra": "allow"}
