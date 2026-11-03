from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AuditLogBase(BaseModel):
    entity_type: str
    entity_id: str
    action: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    user_id: str
    reason: Optional[str] = None
    metadata: Optional[dict] = None
    
class AuditLogCreate(AuditLogBase):
    pass

class AuditLogResponse(AuditLogBase):
    log_id: str
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)
