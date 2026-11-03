from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class EmergencyType(str, Enum):
    FLOOD = "FLOOD"
    EARTHQUAKE = "EARTHQUAKE"
    FIRE = "FIRE"
    ACCIDENT = "ACCIDENT"
    CYCLONE = "CYCLONE"
    DISASTER = "DISASTER"
    COMMUNITY_EMERGENCY = "COMMUNITY_EMERGENCY"
    OTHER = "OTHER"

class Urgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class EmergencyStatus(str, Enum):
    CREATED = "CREATED"
    BROADCAST = "BROADCAST"
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    ACCEPTED = "ACCEPTED"
    ASSIGNED = "ASSIGNED"
    DISPATCHED = "DISPATCHED"
    IN_PROGRESS = "IN_PROGRESS"
    MATCHING = "MATCHING"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FULFILLED = "FULFILLED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class EmergencyRequestCreate(BaseModel):
    created_by: str = Field(..., description="User ID of the NGO, Relief Hub, or Admin")
    food_type: str = Field(..., description="E.g., Meals, Groceries, Water")
    quantity: int = Field(..., description="Total quantity needed")
    number_of_people: int = Field(..., description="Estimated number of affected people")
    location: str = Field(..., description="Text description of the location")
    latitude: float
    longitude: float
    emergency_type: EmergencyType
    urgency: Urgency
    deadline: datetime
    description: str

class EmergencyRequestUpdate(BaseModel):
    status: Optional[EmergencyStatus] = None
    priority_score: Optional[float] = None
    fulfilled_quantity: Optional[int] = None

class EmergencyRequestResponse(EmergencyRequestCreate):
    request_id: str
    status: EmergencyStatus = EmergencyStatus.OPEN
    priority_score: float = 0.0
    priority_explanation: Optional[str] = None
    fulfilled_quantity: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
