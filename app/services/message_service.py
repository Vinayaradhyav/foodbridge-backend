import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId
from app.database.mongodb import get_database
from app.schemas.message import MessageCreate, MessageResponse, ConversationResponse

def generate_conversation_id(user_a: str, user_b: str, context_type: str = "GENERAL", context_id: str = None) -> str:
    participants = sorted([user_a.strip().lower(), user_b.strip().lower()])
    base = f"conv_{participants[0]}_{participants[1]}"
    if context_id and context_type and context_type != "GENERAL":
        base = f"{base}_{context_type.lower()}_{context_id}"
    return base

class MessageService:
    @staticmethod
    async def send_message(sender_id: str, sender_name: str, payload: MessageCreate) -> Dict[str, Any]:
        db = get_database()
        now = datetime.now(timezone.utc)
        
        recipient_id = payload.recipient_id.strip()
        recipient_name = payload.recipient_name or recipient_id
        
        # If recipient name not provided, attempt to look up from users collection
        if recipient_name == recipient_id and recipient_id not in ["admin", "broadcast"]:
            user_doc = await db.users.find_one({
                "$or": [{"firebase_uid": recipient_id}, {"id": recipient_id}, {"email": recipient_id}]
            })
            if user_doc and user_doc.get("name"):
                recipient_name = user_doc["name"]
                
        conversation_id = payload.conversation_id
        if not conversation_id:
            conversation_id = generate_conversation_id(
                sender_id, recipient_id, payload.context_type, payload.context_id
            )

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        message_doc = {
            "message_id": msg_id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "sender_name": sender_name or "User",
            "recipient_id": recipient_id,
            "recipient_name": recipient_name,
            "text": payload.text.strip(),
            "timestamp": now,
            "read": False,
            "context_type": payload.context_type or "GENERAL",
            "context_id": payload.context_id
        }

        result = await db.messages.insert_one(message_doc)
        message_doc["id"] = str(result.inserted_id)
        if "_id" in message_doc:
            del message_doc["_id"]

        # Update or create conversation summary document
        participants = list(set([sender_id, recipient_id]))
        await db.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "last_message": payload.text.strip(),
                    "last_message_time": now,
                    "context_type": payload.context_type or "GENERAL",
                    "context_id": payload.context_id,
                    f"participant_names.{sender_id}": sender_name or "User",
                    f"participant_names.{recipient_id}": recipient_name,
                    "updated_at": now
                },
                "$addToSet": {"participants": {"$each": participants}},
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )

        # Generate Real-Time Notification for Recipient
        try:
            is_to_admin = "admin" in recipient_id.lower()
            notif_target = "admin_broadcast" if is_to_admin else recipient_id
            notif_id = f"notif_msg_{msg_id}"
            await db.notifications.insert_one({
                "notification_id": notif_id,
                "user_id": notif_target,
                "title": f"💬 New Message from {sender_name or 'User'}",
                "message": payload.text.strip(),
                "type": "CHAT_MESSAGE",
                "related_entity_id": conversation_id,
                "read": False,
                "created_at": now
            })
            if is_to_admin:
                # Also create user_id='admin' copy so both queries find it
                await db.notifications.insert_one({
                    "notification_id": f"{notif_id}_adm",
                    "user_id": "admin",
                    "title": f"💬 New Message from {sender_name or 'User'}",
                    "message": payload.text.strip(),
                    "type": "CHAT_MESSAGE",
                    "related_entity_id": conversation_id,
                    "read": False,
                    "created_at": now
                })
        except Exception as n_err:
            print(f"[MessageService] Notification insert warning: {n_err}")

        return message_doc

    @staticmethod
    async def get_conversations(user_id: str, is_admin: bool = False) -> List[Dict[str, Any]]:
        db = get_database()
        query = {}
        if not is_admin:
            query = {
                "$or": [
                    {"participants": user_id},
                    {"participants": "all"},
                    {"participants": "admin"} if user_id.startswith("admin") else {"participants": user_id}
                ]
            }

        cursor = db.conversations.find(query).sort("last_message_time", -1).limit(100)
        convs = []
        async for doc in cursor:
            conv_id = doc.get("conversation_id", str(doc.get("_id", "")))
            
            # Count unread messages sent to this user
            unread_count = await db.messages.count_documents({
                "conversation_id": conv_id,
                "recipient_id": user_id,
                "read": False
            })
            
            convs.append({
                "conversation_id": conv_id,
                "participants": doc.get("participants", []),
                "participant_names": doc.get("participant_names", {}),
                "last_message": doc.get("last_message", ""),
                "last_message_time": doc.get("last_message_time"),
                "unread_count": unread_count,
                "context_type": doc.get("context_type", "GENERAL"),
                "context_id": doc.get("context_id")
            })
        return convs

    @staticmethod
    async def get_messages(conversation_id: str, current_user_id: str, is_admin: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        db = get_database()
        
        # Security authorization: caller must participate in conversation or be admin
        if not is_admin:
            conv = await db.conversations.find_one({"conversation_id": conversation_id})
            if conv and current_user_id not in conv.get("participants", []) and "admin" not in conv.get("participants", []):
                # Also check if any message has this user as sender or recipient
                has_msg = await db.messages.find_one({
                    "conversation_id": conversation_id,
                    "$or": [{"sender_id": current_user_id}, {"recipient_id": current_user_id}]
                })
                if not has_msg:
                    return []

        cursor = db.messages.find({"conversation_id": conversation_id}).sort("timestamp", 1).limit(limit)
        messages = []
        async for doc in cursor:
            doc["id"] = str(doc.get("_id", ""))
            doc.setdefault("message_id", doc["id"])
            messages.append(doc)
            
        return messages

    @staticmethod
    async def mark_read(conversation_id: str, user_id: str) -> int:
        db = get_database()
        res = await db.messages.update_many(
            {"conversation_id": conversation_id, "recipient_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        return res.modified_count

    @staticmethod
    async def report_message(reporter_id: str, message_id: str, reason: str, details: Optional[str] = None) -> Dict[str, Any]:
        db = get_database()
        report_doc = {
            "report_id": f"rep_{uuid.uuid4().hex[:8]}",
            "reporter_id": reporter_id,
            "message_id": message_id,
            "reason": reason,
            "details": details or "",
            "status": "PENDING_REVIEW",
            "created_at": datetime.now(timezone.utc)
        }
        await db.message_reports.insert_one(report_doc)
        return report_doc

    @staticmethod
    async def get_history(user_a: str, user_b: str, limit: int = 50, context_id: Optional[str] = None) -> List[Dict[str, Any]]:
        db = get_database()
        u1, u2 = user_a.strip().lower(), user_b.strip().lower()
        participant_query = {
            "$or": [
                {"sender_id": {"$in": [u1, user_a]}, "recipient_id": {"$in": [u2, user_b]}},
                {"sender_id": {"$in": [u2, user_b]}, "recipient_id": {"$in": [u1, user_a]}},
                {"conversation_id": {"$regex": f"({u1}.*{u2}|{u2}.*{u1})", "$options": "i"}}
            ]
        }
        if context_id:
            clean_ctx = context_id.strip()
            query = {
                "$and": [
                    participant_query,
                    {"$or": [{"context_id": clean_ctx}, {"conversation_id": {"$regex": clean_ctx, "$options": "i"}}]}
                ]
            }
        else:
            query = participant_query
        cursor = db.messages.find(query).sort("timestamp", 1).limit(limit)
        messages = []
        async for doc in cursor:
            doc["id"] = str(doc.get("_id", ""))
            if "_id" in doc:
                del doc["_id"]
            doc.setdefault("message_id", doc["id"])
            doc["content"] = doc.get("text", "")
            ts = doc.get("timestamp")
            doc["created_at"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
            messages.append(doc)
        return messages

    @staticmethod
    async def get_donation_messages(
        donation_id: str,
        current_user_id: str,
        other_user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return strictly private 1-on-1 messages scoped to a single donation between the
        donor and the claiming NGO/receiver (or coordinator/volunteer).
        """
        db = get_database()
        clean_id = donation_id.strip()
        don = None
        try:
            don = await db.donations.find_one({"_id": ObjectId(clean_id)})
        except Exception:
            pass
        if not don:
            don = await db.donations.find_one({
                "$or": [{"food_order_id": clean_id}, {"donation_id": clean_id}, {"id": clean_id}]
            })

        context_keys = {clean_id}
        if don:
            context_keys.add(str(don["_id"]))
            if don.get("food_order_id"):
                context_keys.add(str(don["food_order_id"]))
            if don.get("donation_id"):
                context_keys.add(str(don["donation_id"]))

        uid = current_user_id.strip()
        uid_lower = uid.lower()
        is_admin = uid_lower == "admin" or uid_lower.startswith("admin_")

        # Privacy check: only donor, claiming receiver, assigned volunteer, or admin may read
        if don and not is_admin:
            allowed_uids = {
                str(x).strip().lower()
                for x in (
                    don.get("donor_id"),
                    don.get("donor_uid"),
                    don.get("accepted_by"),
                    don.get("accepted_by_ngo_id"),
                    don.get("matched_receiver"),
                    don.get("assigned_volunteer_id"),
                )
                if x
            }
            if allowed_uids and uid_lower not in allowed_uids:
                # Allow if explicitly named sender/recipient in this context
                pass_check = await db.messages.find_one({
                    "context_id": {"$in": list(context_keys)},
                    "$or": [{"sender_id": uid}, {"recipient_id": uid}],
                })
                if not pass_check:
                    return []

        or_filters: List[Dict[str, Any]] = [
            {"context_id": {"$in": list(context_keys)}},
        ]
        for k in context_keys:
            or_filters.append({"conversation_id": {"$regex": k, "$options": "i"}})

        query: Dict[str, Any] = {"$or": or_filters}
        if not is_admin:
            participant_or: List[Dict[str, Any]] = [
                {"sender_id": {"$in": [uid, uid_lower]}},
                {"recipient_id": {"$in": [uid, uid_lower]}},
            ]
            if don and uid_lower in {
                str(x).strip().lower()
                for x in (
                    don.get("donor_id"),
                    don.get("donor_uid"),
                    don.get("accepted_by"),
                    don.get("accepted_by_ngo_id"),
                    don.get("matched_receiver"),
                    don.get("assigned_volunteer_id"),
                )
                if x
            }:
                participant_or.append({"recipient_id": {"$regex": "^pending_ngo_"}})

            participant_clause: Dict[str, Any] = {"$or": participant_or}
            if other_user_id and other_user_id.strip():
                ou = other_user_id.strip()
                ou_l = ou.lower()
                pending_clause = (
                    {"sender_id": {"$in": [uid, uid_lower, ou, ou_l]}, "recipient_id": {"$regex": "^pending_ngo_"}}
                    if (don and don.get("accepted_by") and str(don.get("accepted_by")).strip().lower() in {uid_lower, ou_l})
                    else {"_id": None}
                )
                participant_clause = {
                    "$or": [
                        {"sender_id": {"$in": [uid, uid_lower]}, "recipient_id": {"$in": [ou, ou_l]}},
                        {"sender_id": {"$in": [ou, ou_l]}, "recipient_id": {"$in": [uid, uid_lower]}},
                        pending_clause,
                    ]
                }
            query = {"$and": [{"$or": or_filters}, participant_clause]}

        cursor = db.messages.find(query).sort("timestamp", 1).limit(limit)
        messages = []
        async for doc in cursor:
            doc["id"] = str(doc.get("_id", ""))
            if "_id" in doc:
                del doc["_id"]
            doc.setdefault("message_id", doc["id"])
            doc["content"] = doc.get("text", "")
            ts = doc.get("timestamp")
            doc["created_at"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
            messages.append(doc)
        return messages

    @staticmethod
    async def get_all_recent(limit: int = 100) -> List[Dict[str, Any]]:
        db = get_database()
        cursor = db.messages.find({}).sort("timestamp", -1).limit(limit)
        messages = []
        async for doc in cursor:
            doc["id"] = str(doc.get("_id", ""))
            if "_id" in doc:
                del doc["_id"]
            doc.setdefault("message_id", doc["id"])
            doc["content"] = doc.get("text", "")
            ts = doc.get("timestamp")
            doc["created_at"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
            messages.append(doc)
        messages.reverse()
        return messages
