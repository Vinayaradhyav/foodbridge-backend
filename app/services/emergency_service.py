from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import re
from fastapi import HTTPException
from bson import ObjectId

from app.models.emergency import (
    EmergencyRequestCreate,
    EmergencyRequestResponse,
    EmergencyRequestUpdate,
    EmergencyStatus,
    Urgency,
)
from app.database.mongodb import mongodb
from app.services.workflow_service import log_audit
from app.services.notification_service import create_notification
from app.schemas.notification import NotificationCreate

class EmergencyService:
    @staticmethod
    def _calculate_priority(urgency: Urgency, num_people: int, deadline: datetime) -> Dict[str, Any]:
        """Calculates priority score and returns an explainable breakdown of factors."""
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
        elif time_left < 3600:
            score += 30.0
            reasons.append("Imminent deadline: <1 hour (+30)")
        elif time_left < 86400:
            score += 15.0
            reasons.append("Short deadline: <24 hours (+15)")
        elif time_left < 86400 * 3:
            score += 5.0

        return {
            "score": score,
            "explanation": " | ".join(reasons) if reasons else "Base Priority",
        }

    @staticmethod
    async def create_emergency(data: EmergencyRequestCreate) -> EmergencyRequestResponse:
        now = datetime.now(timezone.utc)
        cutoff_spam = now - timedelta(minutes=15)
        raw_loc = (getattr(data, "delivery_location", "") or "").strip()
        raw_food = (getattr(data, "food_category", "") or getattr(data, "food_type", "") or "").strip()
        ngo_id = getattr(data, "ngo_id", None) or getattr(data, "requester_id", None)

        # Anti-Spam Duplicate Flood Gate (3+ consecutive identical requests from same user & location)
        if ngo_id and raw_loc:
            recent_count = await mongodb.db.emergencies.count_documents({
                "$or": [{"ngo_id": ngo_id}, {"requester_id": ngo_id}],
                "delivery_location": {"$regex": f"^{re.escape(raw_loc)}$", "$options": "i"},
                "created_at": {"$gte": cutoff_spam},
                "status": {"$nin": ["CANCELLED", "FULFILLED"]}
            })
            if recent_count >= 3:
                auto_rej = {
                    "request_id": f"rej_{uuid.uuid4().hex[:8]}",
                    "ngo_id": ngo_id,
                    "food_category": raw_food,
                    "delivery_location": raw_loc,
                    "status": "AUTO_REJECTED",
                    "rejection_reason": "DUPLICATE_FLOOD_PROTECTION_3_PLUS",
                    "warning_message": "Excessive back-to-back emergency requests from this location.",
                    "created_at": now
                }
                await mongodb.db.emergencies.insert_one(auto_rej)
                try:
                    await mongodb.db.audit_logs.insert_one({
                        "action": "EMERGENCY_AUTO_REJECTED",
                        "entity": "emergency",
                        "actor_id": ngo_id,
                        "reason": "3+ consecutive emergency requests submitted back-to-back from same location",
                        "timestamp": now.isoformat()
                    })
                except Exception:
                    pass
                raise HTTPException(
                    status_code=429,
                    detail="Duplicate request limit reached: You have already submitted 3 back-to-back emergency requests from this location. Please wait for incoming relief dispatch."
                )

        priority_data = EmergencyService._calculate_priority(data.urgency, data.number_of_people, data.deadline)

        emergency_dict = data.model_dump()
        client_req_id = data.request_id or emergency_dict.get("request_id")
        req_id = client_req_id if client_req_id else f"em_{uuid.uuid4().hex[:8]}"
        emergency_dict["request_id"] = req_id
        emergency_dict["priority_score"] = priority_data["score"]
        emergency_dict["priority_explanation"] = priority_data["explanation"]
        emergency_dict["status"] = getattr(data, "status", None) or EmergencyStatus.OPEN.value
        emergency_dict["confirmation_status"] = getattr(data, "confirmation_status", None) or "confirmed"
        emergency_dict["fulfilled_quantity"] = data.quantity if emergency_dict["status"] in ["FULFILLED", "ASSIGNED"] else 0
        emergency_dict["created_at"] = datetime.now(timezone.utc)
        emergency_dict["assignment_history"] = []

        await mongodb.db.emergencies.insert_one(emergency_dict.copy())
        try:
            await mongodb.db.emergency_requests.insert_one(emergency_dict.copy())
        except Exception:
            pass

        # Broadcast notifications ONLY after explicit confirmation (never on drafts)
        if emergency_dict["confirmation_status"] != "draft":
            try:
                from app.services.matching_engine import MatchingEngine
                donors = await mongodb.db.users.find({"role": {"$in": ["DONOR", "donor"]}}).to_list(length=150)
                for d in donors:
                    d_lat = d.get("latitude")
                    d_lon = d.get("longitude")
                    if d_lat is not None and d_lon is not None and data.latitude and data.longitude:
                        dist = MatchingEngine._calculate_distance(data.latitude, data.longitude, float(d_lat), float(d_lon))
                        if dist > 50.0:
                            continue
                    await create_notification(NotificationCreate(
                        user_id=str(d.get("firebase_uid") or d.get("_id") or d.get("id")),
                        title=f"URGENT RELIEF SOS: {data.urgency.value}",
                        message=f"Need {data.quantity} {data.food_type} for {data.number_of_people} people at {data.location}.",
                        type="EMERGENCY_BROADCAST",
                        related_entity_id=req_id
                    ))
            except Exception:
                pass

        return EmergencyRequestResponse(**emergency_dict)

    @staticmethod
    async def get_active_emergencies() -> List[Dict[str, Any]]:
        query = {"status": {"$nin": ["CANCELLED", "DELETED", "REJECTED"]}}
        seen_ids = set()
        merged = []

        cursor1 = mongodb.db.emergencies.find(query).sort("created_at", -1)
        async for e in cursor1:
            req_id = e.get("request_id") or str(e["_id"])
            if req_id not in seen_ids:
                seen_ids.add(req_id)
                e["_id"] = str(e["_id"])
                e["request_id"] = req_id
                e.setdefault("priority_explanation", "Calculated Priority")
                e.setdefault("assignment_history", [])
                merged.append(e)

        cursor2 = mongodb.db.emergency_requests.find(query).sort("created_at", -1)
        async for e in cursor2:
            req_id = e.get("request_id") or str(e["_id"])
            if req_id not in seen_ids:
                seen_ids.add(req_id)
                e["_id"] = str(e["_id"])
                e["request_id"] = req_id
                e.setdefault("priority_explanation", "Calculated Priority")
                e.setdefault("assignment_history", [])
                merged.append(e)

        merged.sort(key=lambda x: (x.get("created_at") or datetime.min), reverse=True)
        return merged

    @staticmethod
    async def get_emergency_by_id(request_id: str) -> Optional[EmergencyRequestResponse]:
        or_list: list[dict[str, Any]] = [{"request_id": request_id}]
        try:
            or_list.append({"_id": ObjectId(request_id)})
        except Exception:
            pass
        query = {"$or": or_list}

        e = await mongodb.db.emergencies.find_one(query) or await mongodb.db.emergency_requests.find_one(query)
        if e:
            e["_id"] = str(e["_id"])
            e.setdefault("request_id", request_id)
            e.setdefault("assignment_history", [])
            return EmergencyRequestResponse(**e)
        return None

    @staticmethod
    async def pledge_emergency(
        request_id: str,
        donor_id: str,
        donor_name: str,
        donor_phone: Optional[str] = None,
        contributed_meals: Optional[int] = None,
        assigned_volunteer_id: Optional[str] = None,
        handover_otp: Optional[str] = None
    ) -> EmergencyRequestResponse:
        """
        Phase 7: Backend-side Atomic Assignment with MongoDB Conditional Locking.
        Guarantees that once a donor accepts an emergency request, other donors are blocked with HTTP 409 Conflict.
        """
        or_conditions: list[dict[str, Any]] = [{"request_id": request_id}]
        try:
            or_conditions.append({"_id": ObjectId(request_id)})
        except Exception:
            pass
        query_filter = {
            "$and": [
                {"$or": or_conditions},
                {"status": {"$in": ["OPEN", "AVAILABLE", "BROADCAST", "ACTIVE", "MATCHING", "CREATED"]}}
            ]
        }

        doc = await mongodb.db.emergencies.find_one(query_filter["$and"][0])
        if not doc:
            doc = await mongodb.db.emergency_requests.find_one(query_filter["$and"][0])
        if not doc:
            raise HTTPException(status_code=404, detail="Emergency request not found")

        current_status = doc.get("status")
        if current_status not in ["OPEN", "AVAILABLE", "BROADCAST", "ACTIVE", "MATCHING", "CREATED"]:
            raise HTTPException(
                status_code=409,
                detail=f"Emergency request is already reserved/assigned (Status: {current_status}). Another donor cannot claim it."
            )

        now = datetime.now(timezone.utc)
        otp = handover_otp or doc.get("handover_otp") or "7392"
        meals = contributed_meals or doc.get("quantity") or 100

        history_entry = {
            "action": "ASSIGNED",
            "donor_id": donor_id,
            "donor_name": donor_name,
            "timestamp": now.isoformat(),
            "meals": meals
        }

        update_payload = {
            "status": "ASSIGNED",
            "assigned_donor_id": donor_id,
            "assigned_donor_name": donor_name,
            "assigned_donor_phone": donor_phone,
            "fulfilled_quantity": meals,
            "handover_otp": otp,
            "updated_at": now
        }
        if assigned_volunteer_id:
            update_payload["assigned_volunteer_id"] = assigned_volunteer_id

        # Atomic find_one_and_update
        updated = await mongodb.db.emergencies.find_one_and_update(
            query_filter,
            {
                "$set": update_payload,
                "$push": {"assignment_history": history_entry}
            },
            return_document=True
        )
        if not updated:
            raise HTTPException(
                status_code=409,
                detail="Race condition detected: Request was just claimed by another donor."
            )

        await mongodb.db.emergency_requests.update_many(
            query_filter["$and"][0],
            {
                "$set": update_payload,
                "$push": {"assignment_history": history_entry}
            }
        )

        await log_audit("Emergency", request_id, f"Pledged by Donor {donor_name}", donor_id, current_status, "ASSIGNED")
        
        updated["_id"] = str(updated["_id"])
        return EmergencyRequestResponse(**updated)

    @staticmethod
    async def cancel_pledge(
        request_id: str,
        donor_id: str,
        reason: str
    ) -> EmergencyRequestResponse:
        """
        Phase 8: Donor Cancellation and Automatic Reassignment.
        Releases the assignment, reverts status back to AVAILABLE/OPEN, records reason in history,
        and broadcasts notification to eligible donors.
        """
        target_list: list[dict[str, Any]] = [{"request_id": request_id}]
        try:
            target_list.append({"_id": ObjectId(request_id)})
        except Exception:
            pass
        target_q = {"$or": target_list}

        doc = await mongodb.db.emergencies.find_one(target_q) or await mongodb.db.emergency_requests.find_one(target_q)
        if not doc:
            raise HTTPException(status_code=404, detail="Emergency request not found")

        current_donor = doc.get("assigned_donor_id")
        if current_donor and current_donor != donor_id and donor_id != "admin":
            raise HTTPException(status_code=403, detail="You do not own this emergency assignment")

        now = datetime.now(timezone.utc)
        history_entry = {
            "action": "CANCELLED_BY_DONOR",
            "donor_id": donor_id,
            "reason": reason,
            "timestamp": now.isoformat()
        }

        update_payload = {
            "status": "OPEN",
            "assigned_donor_id": None,
            "assigned_donor_name": None,
            "assigned_donor_phone": None,
            "cancellation_reason": reason,
            "fulfilled_quantity": 0,
            "updated_at": now
        }

        updated = await mongodb.db.emergencies.find_one_and_update(
            target_q,
            {
                "$set": update_payload,
                "$push": {"assignment_history": history_entry}
            },
            return_document=True
        )
        await mongodb.db.emergency_requests.update_many(
            target_q,
            {
                "$set": update_payload,
                "$push": {"assignment_history": history_entry}
            }
        )

        await log_audit("Emergency", request_id, f"Cancelled by Donor: {reason}", donor_id, "ASSIGNED", "OPEN")

        # Broadcast reassignment alert to other donors
        try:
            other_donors = await mongodb.db.users.find({"role": "DONOR", "$or": [{"_id": {"$ne": ObjectId(donor_id)}}, {"id": {"$ne": donor_id}}]}).to_list(length=100)
            for d in other_donors:
                await create_notification(NotificationCreate(
                    user_id=str(d.get("_id") or d.get("id")),
                    title="SOS REASSIGNMENT: Urgent Food Needed",
                    message=f"Request {request_id} for {doc.get('quantity')} meals at {doc.get('location')} is open again. Can you help?",
                    type="EMERGENCY_REASSIGNMENT",
                    related_entity_id=request_id
                ))
        except Exception:
            pass

        updated["_id"] = str(updated["_id"])
        return EmergencyRequestResponse(**updated)

    @staticmethod
    async def update_emergency(request_id: str, update_data: EmergencyRequestUpdate) -> Optional[EmergencyRequestResponse]:
        or_list: list[dict[str, Any]] = [{"request_id": request_id}]
        try:
            or_list.append({"_id": ObjectId(request_id)})
        except Exception:
            pass
        query = {"$or": or_list}

        e = await mongodb.db.emergencies.find_one(query) or await mongodb.db.emergency_requests.find_one(query)
        if not e:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        if "fulfilled_quantity" in update_dict:
            new_fulfilled = update_dict["fulfilled_quantity"]
            if new_fulfilled >= e.get("quantity", 0):
                update_dict["status"] = EmergencyStatus.FULFILLED.value
            elif new_fulfilled > 0:
                update_dict["status"] = EmergencyStatus.PARTIALLY_FULFILLED.value

        update_dict["updated_at"] = datetime.now(timezone.utc)

        await mongodb.db.emergencies.update_many(query, {"$set": update_dict})
        await mongodb.db.emergency_requests.update_many(query, {"$set": update_dict})

        updated_e = await mongodb.db.emergencies.find_one(query) or await mongodb.db.emergency_requests.find_one(query)
        if updated_e:
            updated_e["_id"] = str(updated_e["_id"])
            updated_e.setdefault("assignment_history", [])
            return EmergencyRequestResponse(**updated_e)
        return None

    @staticmethod
    async def delete_emergency(request_id: str) -> bool:
        del_list: list[dict[str, Any]] = [{"request_id": request_id}]
        try:
            del_list.append({"_id": ObjectId(request_id)})
        except Exception:
            pass
        query = {"$or": del_list}
        r1 = await mongodb.db.emergencies.delete_many(query)
        r2 = await mongodb.db.emergency_requests.delete_many(query)
        return (r1.deleted_count > 0 or r2.deleted_count > 0)
