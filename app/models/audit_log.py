from datetime import datetime, timezone
from typing import Dict, Any

class AuditLogModel:
    @staticmethod
    def create_new_log(data: dict) -> Dict[str, Any]:
        return {
            "entity_type": data.get("entity_type"),
            "entity_id": data.get("entity_id"),
            "action": data.get("action"),
            "old_status": data.get("old_status"),
            "new_status": data.get("new_status"),
            "user_id": data.get("user_id"),
            "reason": data.get("reason"),
            "metadata": data.get("metadata", {}),
            "timestamp": datetime.now(timezone.utc)
        }
    
    @staticmethod
    def format_for_response(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return None
        
        response = dict(doc)
        if "_id" in response:
            response["log_id"] = str(response["_id"])
            del response["_id"]
        return response
