from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=4, max_length=25)
    role: str = Field(..., description="Role must be one of: donor, FOOD_RECEIVER, volunteer, admin")
    location: Optional[str] = ""
    verification_status: Optional[str] = None
    receiver_type: Optional[str] = Field(None, description="Type of receiver: NGO_TRUST, FOOD_BANK, RELIEF_HUB, COMMUNITY_ORGANIZATION, SHELTER_CARE_CENTER, OTHER_AUTHORIZED_ORGANIZATION")
    is_email_verified: Optional[bool] = False
    
    # Receiver / NGO Specific Fields
    organization_id: Optional[str] = None
    contact_person: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    food_capacity: Optional[int] = None
    beneficiary_capacity: Optional[int] = None
    vehicle_availability: Optional[bool] = None
    fleet_count: Optional[int] = None
    volunteer_capacity: Optional[int] = None

    # AI Verification & Screening Fields
    ai_trust_score: Optional[int] = None
    ai_safety_status: Optional[str] = None
    ai_classification: Optional[str] = None
    ai_notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Volunteer Specific Fields
    vehicle_available: Optional[bool] = None
    vehicle_type: Optional[str] = None
    vehicle_capacity: Optional[str] = None
    availability_status: Optional[str] = "OFFLINE"
    
    # Notifications
    fcm_token: Optional[str] = None

class UserCreate(UserBase):
    firebase_uid: Optional[str] = None
    password: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_indian_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        elif len(digits) > 10:
            digits = digits[-10:]
        if len(digits) == 10:
            return digits
        if len(digits) >= 4:
            return digits
        raise ValueError("Mobile phone number must contain at least 4 digits.")

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None

class NgoProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    organization_id: Optional[str] = None
    contact_person: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    food_capacity: Optional[int] = None
    beneficiary_capacity: Optional[int] = None
    vehicle_availability: Optional[bool] = None
    fleet_count: Optional[int] = None
    volunteer_capacity: Optional[int] = None

class VolunteerProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    vehicle_available: Optional[bool] = None
    vehicle_type: Optional[str] = None
    vehicle_capacity: Optional[str] = None

class VolunteerAvailabilityUpdate(BaseModel):
    availability_status: str

class FcmTokenUpdate(BaseModel):
    fcm_token: str

class UserResponse(UserBase):
    id: str
    firebase_uid: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    access_token: Optional[str] = None
    token_type: Optional[str] = "bearer"

    model_config = {"from_attributes": True}

class LoginRequest(BaseModel):
    firebase_uid: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., min_length=6)

class SendVerificationEmailRequest(BaseModel):
    email: EmailStr

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str
