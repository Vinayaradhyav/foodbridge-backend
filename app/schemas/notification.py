from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class NotificationBase(BaseModel):
    user_id: str
    title: str
    message: str
    type: str  # e.g., 'DONATION_CREATED', 'ASSIGNED', 'DELIVERY_COMPLETED'
    related_entity_id: Optional[str] = None
    read: bool = False

class NotificationCreate(NotificationBase):
    pass

class NotificationUpdate(BaseModel):
    read: Optional[bool] = None

class NotificationResponse(NotificationBase):
    notification_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
