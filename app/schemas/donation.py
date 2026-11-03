from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum

class DonationStatus(str, Enum):
    # Core Flow
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    MATCHING = "MATCHING"
    NGO_PENDING = "NGO_PENDING"
    ACCEPTED = "ACCEPTED"
    VOLUNTEER_ASSIGNMENT = "VOLUNTEER_ASSIGNMENT"
    PICKUP_ASSIGNED = "PICKUP_ASSIGNED"
    VOLUNTEER_ON_THE_WAY = "VOLUNTEER_ON_THE_WAY"
    ARRIVED = "ARRIVED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    RECEIVER_CONFIRMED = "RECEIVER_CONFIRMED"
    COMPLETED = "COMPLETED"
    AVAILABLE = "AVAILABLE"
    MATCHED = "MATCHED"

    # Failure States
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED_PICKUP = "FAILED_PICKUP"
    FAILED_DELIVERY = "FAILED_DELIVERY"

class DonationBase(BaseModel):
    food_name: str
    food_type: str
    quantity: float
    unit: str
    number_of_meals: int
    preparation_time: Optional[datetime] = None
    available_from: Optional[datetime] = None
    pickup_deadline: Optional[datetime] = None
    pickup_location: str
    latitude: float
    longitude: float
    storage_condition: Optional[str] = "Room Temp"
    packaging_type: Optional[str] = "Boxes"
    description: Optional[str] = ""
    food_image: Optional[str] = ""

class DonationCreate(DonationBase):
    pass

class DonationUpdate(BaseModel):
    food_name: Optional[str] = None
    food_type: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    number_of_meals: Optional[int] = None
    preparation_time: Optional[datetime] = None
    available_from: Optional[datetime] = None
    pickup_deadline: Optional[datetime] = None
    pickup_location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    storage_condition: Optional[str] = None
    packaging_type: Optional[str] = None
    description: Optional[str] = None
    food_image: Optional[str] = None
    status: Optional[str] = None
    ngo_id: Optional[str] = None
    accepted_by: Optional[str] = None
    assigned_volunteer_id: Optional[str] = None
    volunteer_name: Optional[str] = None

class DonationResponse(DonationBase):
    id: str
    donor_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    donation_id: Optional[str] = None
    food_order_id: Optional[str] = None
    donor_name: Optional[str] = None
    ngo_id: Optional[str] = None
    accepted_by: Optional[str] = None
    assigned_volunteer_id: Optional[str] = None
    volunteer_name: Optional[str] = None
    category: Optional[str] = None
    veg_nonveg: Optional[str] = None
    pickup_otp: Optional[str] = None
    delivery_otp: Optional[str] = None
    rejected_by: Optional[list[str]] = []

    model_config = ConfigDict(from_attributes=True)
