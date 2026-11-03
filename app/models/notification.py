from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Any
from datetime import datetime, timezone
import uuid

class NotificationModel(BaseModel):
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str = "Notification"
    message: Optional[str] = ""
    body: Optional[str] = None
    type: str = "SYSTEM"
    related_entity_id: Optional[str] = None
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def normalize_message_and_body(cls, data: Any) -> Any:
        if isinstance(data, dict):
            msg = data.get("message") or data.get("body") or ""
            data["message"] = msg
            data["body"] = msg
        return data

    model_config = ConfigDict(populate_by_name=True)
