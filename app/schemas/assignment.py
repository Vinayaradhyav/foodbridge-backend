from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum

class AssignmentStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PICKUP_STARTED = "PICKUP_STARTED"
    ARRIVED_AT_PICKUP = "ARRIVED_AT_PICKUP"
    FOOD_PICKED_UP = "FOOD_PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class AssignmentBase(BaseModel):
    donation_id: str
    volunteer_id: str
    pickup_location: str
    delivery_location: str

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentUpdate(BaseModel):
    status: Optional[AssignmentStatus] = None

class AssignmentResponse(AssignmentBase):
    assignment_id: str
    status: AssignmentStatus
    pickup_otp: Optional[str] = None
    pickup_proof_image_url: Optional[str] = None
    pickup_verified_at: Optional[datetime] = None
    assigned_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
