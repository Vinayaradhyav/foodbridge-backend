from pydantic import BaseModel, Field
from typing import Optional, List

class PriorityPredictionRequest(BaseModel):
    number_of_people: Optional[int] = 50
    requested_quantity: Optional[int] = 100
    emergency_type: Optional[str] = "Relief Operation"
    urgency: Optional[str] = "HIGH"
    shortage: Optional[int] = 50
    deadline_hours: Optional[float] = 12.0
    distance_km: Optional[float] = 5.0
    available_food: Optional[int] = 20
    available_volunteers: Optional[int] = 5
    available_vehicles: Optional[int] = 2
    is_weather_related: Optional[bool] = False

class PriorityPredictionResponse(BaseModel):
    priority: str
    priority_level: str
    score: float
    confidence: float
    explanation: str
    model_version: str
    recommendation: Optional[str] = ""
