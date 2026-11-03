from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

class MessageCreate(BaseModel):
    recipient_id: str = Field(..., description="Recipient user UID, 'admin', or 'broadcast'")
    text: Optional[str] = None
    content: Optional[str] = None
    sender_id: Optional[str] = None
    sender_role: Optional[str] = None
    recipient_role: Optional[str] = None
    conversation_id: Optional[str] = None
    context_type: Optional[str] = Field("GENERAL", description="GENERAL, DONATION, EMERGENCY, MISSION, DISPATCH")
    context_id: Optional[str] = None
    sender_name: Optional[str] = None
    recipient_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_text(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("text") and data.get("content"):
                data["text"] = str(data["content"])
            elif not data.get("content") and data.get("text"):
                data["content"] = str(data["text"])
        return data

class MessageResponse(BaseModel):
    id: str
    message_id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    recipient_id: str
    recipient_name: str
    text: str
    timestamp: datetime
    read: bool = False
    context_type: str = "GENERAL"
    context_id: Optional[str] = None

class ConversationResponse(BaseModel):
    conversation_id: str
    participants: List[str]
    participant_names: Dict[str, str] = {}
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    unread_count: int = 0
    context_type: str = "GENERAL"
    context_id: Optional[str] = None

class MarkReadRequest(BaseModel):
    conversation_id: Optional[str] = None
    message_ids: Optional[List[str]] = None

class ReportMessageRequest(BaseModel):
    message_id: str
    reason: str
    details: Optional[str] = None
