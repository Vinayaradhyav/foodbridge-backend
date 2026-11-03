from pydantic import BaseModel
from typing import Optional

class NLPRequest(BaseModel):
    text: str

class NLPEmergencyResponse(BaseModel):
    food_type: Optional[str] = None
    quantity: Optional[int] = None
    number_of_people: Optional[int] = None
    location: Optional[str] = None
    emergency_type: Optional[str] = None
    urgency: Optional[str] = None
    deadline: Optional[str] = None
    confidence: float
