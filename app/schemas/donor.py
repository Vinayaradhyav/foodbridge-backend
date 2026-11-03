from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class DonorCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    mobile_number: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6)

class DonorResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    mobile_number: str
    auth_provider: str
    account_status: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    id_token: str
