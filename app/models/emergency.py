from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class EmergencyType(str, Enum):
    FLOOD = "FLOOD"
    EARTHQUAKE = "EARTHQUAKE"
    FIRE = "FIRE"
    ACCIDENT = "ACCIDENT"
    CYCLONE = "CYCLONE"
    DISASTER = "DISASTER"
    COMMUNITY_EMERGENCY = "COMMUNITY_EMERGENCY"
    FOOD_SHORTAGE = "FOOD_SHORTAGE"
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
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    ACCEPTED = "ACCEPTED"
    ASSIGNED = "ASSIGNED"
    DISPATCHED = "DISPATCHED"
    IN_PROGRESS = "IN_PROGRESS"
    IN_TRANSIT = "IN_TRANSIT"
    MATCHING = "MATCHING"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FULFILLED = "FULFILLED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class EmergencyRequestCreate(BaseModel):
    request_id: Optional[str] = None
    created_by: str = Field(..., description="User ID of the NGO, Relief Hub, or Admin")
    food_type: str = Field(..., description="E.g., Meals, Groceries, Water")
    food_category: Optional[str] = "Cooked Meals"
    quantity: int = Field(..., description="Total quantity needed")
    quantity_unit: Optional[str] = "meals"
    number_of_people: int = Field(..., description="Estimated number of affected people")
    location: str = Field(..., description="Text description of the location")
    latitude: float
    longitude: float
    emergency_type: EmergencyType = EmergencyType.COMMUNITY_EMERGENCY
    urgency: Urgency = Urgency.HIGH
    deadline: datetime
    description: str
    status: Optional[str] = None
    
    # Dual location architecture: Requester GPS vs Delivery Destination
    requester_gps: Optional[Dict[str, Any]] = None
    delivery_destination: Optional[Dict[str, Any]] = None
    
    # Multilingual & Voice Assistant tracking
    original_language: Optional[str] = "en"
    target_language: Optional[str] = "en"
    original_transcript: Optional[str] = None
    normalized_transcript: Optional[str] = None
    translated_transcript: Optional[str] = None
    english_translation: Optional[str] = None
    translation_status: Optional[str] = "completed"
    audio_id: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration_seconds: Optional[int] = 0
    packaging_required: Optional[bool] = False
    water_required: Optional[bool] = False
    water_quantity: Optional[int] = None
    delivery_time: Optional[str] = None
    confirmation_status: Optional[str] = "confirmed"
    extracted_parameters: Optional[Dict[str, Any]] = None
    
    # Assignment details
    assigned_donor_id: Optional[str] = None
    assigned_donor_name: Optional[str] = None
    assigned_donor_phone: Optional[str] = None
    assigned_volunteer_id: Optional[str] = None
    assigned_volunteer_name: Optional[str] = None
    assigned_volunteer_phone: Optional[str] = None
    handover_otp: Optional[str] = None

class EmergencyRequestUpdate(BaseModel):
    status: Optional[str] = None
    priority_score: Optional[float] = None
    priority_explanation: Optional[str] = None
    fulfilled_quantity: Optional[int] = None
    assigned_donor_id: Optional[str] = None
    assigned_donor_name: Optional[str] = None
    assigned_donor_phone: Optional[str] = None
    assigned_volunteer_id: Optional[str] = None
    assigned_volunteer_name: Optional[str] = None
    assigned_volunteer_phone: Optional[str] = None
    handover_otp: Optional[str] = None
    cancellation_reason: Optional[str] = None
    assignment_history: Optional[List[Dict[str, Any]]] = None

class EmergencyRequestResponse(EmergencyRequestCreate):
    request_id: Optional[str] = None
    status: Optional[str] = EmergencyStatus.OPEN.value
    priority_score: float = 0.0
    priority_explanation: Optional[str] = None
    fulfilled_quantity: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cancellation_reason: Optional[str] = None
    assignment_history: Optional[List[Dict[str, Any]]] = []

    model_config = {"populate_by_name": True}
