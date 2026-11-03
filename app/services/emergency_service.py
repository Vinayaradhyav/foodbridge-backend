from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from app.models.emergency import EmergencyRequestCreate, EmergencyRequestResponse, EmergencyRequestUpdate, EmergencyStatus, Urgency
from app.database.mongodb import mongodb

class EmergencyService:
    @staticmethod
    def _calculate_priority(urgency: Urgency, num_people: int, deadline: datetime) -> Dict[str, Any]:
        """
        Calculates priority score and returns an explainable breakdown of factors.
        """
        score = 0.0
        reasons = []
        
        # 1. Base score from urgency
        if urgency == Urgency.CRITICAL:
            score += 40.0
            reasons.append("Critical Urgency (+40)")
        elif urgency == Urgency.HIGH:
            score += 30.0
            reasons.append("High Urgency (+30)")
        elif urgency == Urgency.MEDIUM:
            score += 20.0
            reasons.append("Medium Urgency (+20)")
        elif urgency == Urgency.LOW:
            score += 10.0
            
        # 2. Scale based on people affected
        if num_people >= 1000:
            score += 30.0
            reasons.append("Massive scale: >1000 people (+30)")
        elif num_people >= 500:
            score += 20.0
            reasons.append("Large scale: >500 people (+20)")
        elif num_people >= 100:
            score += 10.0
            reasons.append("Medium scale: >100 people (+10)")
        elif num_people >= 50:
            score += 5.0
            
        # 3. Time factor
        now = datetime.now(timezone.utc)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
            
        time_left = (deadline - now).total_seconds()
        
        if time_left < 0:
            score += 50.0
            reasons.append("Deadline Exceeded (+50)")
        elif time_left < 3600: # Less than 1 hour
            score += 30.0
            reasons.append("Imminent deadline: <1 hour (+30)")
        elif time_left < 86400: # Less than 24 hours
            score += 15.0
            reasons.append("Short deadline: <24 hours (+15)")
        elif time_left < 86400 * 3: # Less than 3 days
            score += 5.0
            
        return {
            "score": score,
            "explanation": " | ".join(reasons) if reasons else "Base Priority"
        }

    @staticmethod
    async def create_emergency(data: EmergencyRequestCreate) -> EmergencyRequestResponse:
        priority_data = EmergencyService._calculate_priority(data.urgency, data.number_of_people, data.deadline)
        
        emergency_dict = data.model_dump()
        emergency_dict["request_id"] = f"em_{uuid.uuid4().hex[:8]}"
        emergency_dict["priority_score"] = priority_data["score"]
        emergency_dict["priority_explanation"] = priority_data["explanation"]
        emergency_dict["status"] = EmergencyStatus.OPEN.value
        emergency_dict["fulfilled_quantity"] = 0
        emergency_dict["created_at"] = datetime.now(timezone.utc)
        
        # Dual-persist into both emergencies and emergency_requests collections for complete system consistency
        await mongodb.db.emergencies.insert_one(emergency_dict.copy())
        try:
            await mongodb.db.emergency_requests.insert_one(emergency_dict.copy())
        except Exception:
            pass
        
        return EmergencyRequestResponse(**emergency_dict)

    @staticmethod
    async def get_active_emergencies() -> List[Dict[str, Any]]:
        active_statuses = [
            EmergencyStatus.OPEN.value, 
            EmergencyStatus.MATCHING.value, 
            EmergencyStatus.PARTIALLY_FULFILLED.value,
            "OPEN", "ACTIVE", "MATCHING", "PARTIALLY_FULFILLED"
        ]
        
        # Pull from both collections to ensure seeded and newly created requests are visible
        seen_ids = set()
        merged = []
        
        cursor1 = mongodb.db.emergencies.find({"status": {"$in": active_statuses}}).sort("priority_score", -1)
        async for e in cursor1:
            req_id = e.get("request_id") or str(e["_id"])
            if req_id not in seen_ids:
                seen_ids.add(req_id)
                e["_id"] = str(e["_id"])
                e["request_id"] = req_id
                e.setdefault("priority_explanation", "Calculated Priority")
                merged.append(e)
                
        cursor2 = mongodb.db.emergency_requests.find({"status": {"$in": active_statuses}}).sort("priority_score", -1)
        async for e in cursor2:
            req_id = e.get("request_id") or str(e["_id"])
            if req_id not in seen_ids:
                seen_ids.add(req_id)
                e["_id"] = str(e["_id"])
                e["request_id"] = req_id
                e.setdefault("priority_explanation", "Calculated Priority")
                merged.append(e)
                
        merged.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        return merged

    @staticmethod
    async def get_emergency_by_id(request_id: str) -> Optional[EmergencyRequestResponse]:
        from bson import ObjectId
        query = {"request_id": request_id}
        e = await mongodb.db.emergencies.find_one(query)
        if not e:
            e = await mongodb.db.emergency_requests.find_one(query)
        if not e:
            try:
                e = await mongodb.db.emergencies.find_one({"_id": ObjectId(request_id)})
            except Exception:
                pass
        if not e:
            try:
                e = await mongodb.db.emergency_requests.find_one({"_id": ObjectId(request_id)})
            except Exception:
                pass
                
        if e:
            e["_id"] = str(e["_id"])
            e.setdefault("request_id", request_id)
            return EmergencyRequestResponse(**e)
        return None

    @staticmethod
    async def update_emergency(request_id: str, update_data: EmergencyRequestUpdate) -> Optional[EmergencyRequestResponse]:
        from bson import ObjectId
        query = {"request_id": request_id}
        e = await mongodb.db.emergencies.find_one(query) or await mongodb.db.emergency_requests.find_one(query)
        if not e:
            return None
            
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # Check for fulfillment status transitions
        if "fulfilled_quantity" in update_dict:
            new_fulfilled = update_dict["fulfilled_quantity"]
            if new_fulfilled >= e.get("quantity", 0):
                update_dict["status"] = EmergencyStatus.FULFILLED.value
            elif new_fulfilled > 0:
                update_dict["status"] = EmergencyStatus.PARTIALLY_FULFILLED.value
                
        await mongodb.db.emergencies.update_many(
            {"$or": [{"request_id": request_id}, {"_id": e["_id"]}]},
            {"$set": update_dict}
        )
        await mongodb.db.emergency_requests.update_many(
            {"$or": [{"request_id": request_id}, {"_id": e["_id"]}]},
            {"$set": update_dict}
        )
        
        updated_e = await mongodb.db.emergencies.find_one({"$or": [{"request_id": request_id}, {"_id": e["_id"]}]})
        if not updated_e:
            updated_e = await mongodb.db.emergency_requests.find_one({"$or": [{"request_id": request_id}, {"_id": e["_id"]}]})
        if updated_e:
            updated_e["_id"] = str(updated_e["_id"])
            return EmergencyRequestResponse(**updated_e)
        return None

    @staticmethod
    async def delete_emergency(request_id: str) -> bool:
        from bson import ObjectId
        query = {"$or": [{"request_id": request_id}]}
        try:
            query["$or"].append({"_id": ObjectId(request_id)})
        except Exception:
            pass
            
        r1 = await mongodb.db.emergencies.delete_many(query)
        r2 = await mongodb.db.emergency_requests.delete_many(query)
        return (r1.deleted_count > 0 or r2.deleted_count > 0)

    @staticmethod
    async def reject_emergency(request_id: str, reason: str = "Rejected by administrator") -> bool:
        from bson import ObjectId
        query = {"$or": [{"request_id": request_id}]}
        try:
            query["$or"].append({"_id": ObjectId(request_id)})
        except Exception:
            pass
            
        update_data = {
            "status": "REJECTED",
            "rejection_reason": reason,
            "updated_at": datetime.now(timezone.utc)
        }
        r1 = await mongodb.db.emergencies.update_many(query, {"$set": update_data})
        r2 = await mongodb.db.emergency_requests.update_many(query, {"$set": update_data})
        return (r1.modified_count > 0 or r2.modified_count > 0)
