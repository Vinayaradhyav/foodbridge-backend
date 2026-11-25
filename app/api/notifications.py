from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.services.notification_service import (
    get_user_notifications,
    mark_as_read,
    mark_all_as_read,
    delete_notification,
    clear_all_notifications
)
from app.schemas.notification import NotificationResponse
from app.core.security import get_current_user
from app.schemas.user import UserResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationResponse])
async def fetch_notifications(current_user = Depends(get_current_user), limit: int = 50):
    user_id = current_user.get("firebase_uid") or current_user.get("id") or current_user.get("user_id") or str(current_user.get("_id", ""))
    notifications = await get_user_notifications(str(user_id), limit)
    return notifications

@router.get("/admin", response_model=List[NotificationResponse])
async def fetch_admin_notifications(current_user: dict = Depends(get_current_user), limit: int = 50):
    """
    Admin command center notifications. Scans recent system events and ensures they exist in the 
    standard notification infrastructure for 'admin_broadcast' to maintain read/unread state.
    """
    if current_user.get("role", "").upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin only")
        
    from app.database.mongodb import mongodb
    from datetime import datetime, timezone, timedelta
    import uuid
    
    # 1. Sync recent important events as admin notifications (strictly respecting admin Clear-All watermark!)
    now = datetime.now(timezone.utc)
    recent_threshold = now - timedelta(hours=24)
    try:
        wm_doc = await mongodb.db.system_settings.find_one({"key": "admin_notifications_cleared_at"})
        if wm_doc and wm_doc.get("timestamp"):
            wm_ts = wm_doc["timestamp"]
            if isinstance(wm_ts, datetime):
                if wm_ts.tzinfo is None:
                    wm_ts = wm_ts.replace(tzinfo=timezone.utc)
                if wm_ts > recent_threshold:
                    recent_threshold = wm_ts
    except Exception:
        pass
    
    # Sync Emergency Requests
    em_cursor = mongodb.db.emergencies.find({"created_at": {"$gte": recent_threshold}})
    async for em in em_cursor:
        notif_id = f"admin_em_{em['_id']}"
        exists = await mongodb.db.notifications.find_one({"notification_id": notif_id})
        if not exists:
            await mongodb.db.notifications.insert_one({
                "notification_id": notif_id,
                "user_id": "admin_broadcast",
                "title": "Emergency Request",
                "message": f"Critical emergency request in {em.get('location', 'Unknown')} requires attention.",
                "type": "EMERGENCY_REQUEST",
                "related_entity_id": str(em['_id']),
                "read": False,
                "created_at": em.get("created_at", now)
            })
            
    # Sync Anomalies (Suspicious Activity)
    an_cursor = mongodb.db.anomalies.find({"timestamp": {"$gte": recent_threshold}})
    async for an in an_cursor:
        notif_id = f"admin_an_{an['_id']}"
        exists = await mongodb.db.notifications.find_one({"notification_id": notif_id})
        if not exists:
            await mongodb.db.notifications.insert_one({
                "notification_id": notif_id,
                "user_id": "admin_broadcast",
                "title": "Suspicious Activity",
                "message": f"Anomaly detected for user {an.get('user_name', 'Unknown')}: {an.get('risk_level', '')}",
                "type": "SUSPICIOUS_ACTIVITY",
                "related_entity_id": str(an['_id']),
                "read": False,
                "created_at": an.get("timestamp", now)
            })
            
    # Sync New NGOs (Receiver Verification)
    user_cursor = mongodb.db.users.find({"role": "NGO", "created_at": {"$gte": recent_threshold}})
    async for u in user_cursor:
        notif_id = f"admin_ngo_{u['_id']}"
        exists = await mongodb.db.notifications.find_one({"notification_id": notif_id})
        if not exists:
            await mongodb.db.notifications.insert_one({
                "notification_id": notif_id,
                "user_id": "admin_broadcast",
                "title": "Receiver Verification Required",
                "message": f"New Food Receiver '{u.get('name', 'Unknown')}' is pending verification.",
                "type": "RECEIVER_VERIFICATION",
                "related_entity_id": str(u['_id']),
                "read": False,
                "created_at": u.get("created_at", now)
            })

    # Sync Donations (New & Expired)
    don_cursor = mongodb.db.donations.find({"created_at": {"$gte": recent_threshold}})
    async for d in don_cursor:
        type_str = "NEW_DONATION"
        title = "New Donation Available"
        msg = f"A new donation of {d.get('food_type', 'food')} was listed."
        
        if d.get("status") == "EXPIRED":
            type_str = "EXPIRED_FOOD"
            title = "Food Expired"
            msg = f"Donation {str(d['_id'])[:8]} has expired."
            
        notif_id = f"admin_don_{type_str}_{d['_id']}"
        exists = await mongodb.db.notifications.find_one({"notification_id": notif_id})
        if not exists:
            await mongodb.db.notifications.insert_one({
                "notification_id": notif_id,
                "user_id": "admin_broadcast",
                "title": title,
                "message": msg,
                "type": type_str,
                "related_entity_id": str(d['_id']),
                "read": False,
                "created_at": d.get("created_at", now)
            })

    # Sync Live Chat Messages sent to Admin
    msg_cursor = mongodb.db.messages.find({
        "recipient_id": {"$regex": r"admin", "$options": "i"},
        "timestamp": {"$gte": recent_threshold}
    })
    async for m in msg_cursor:
        sender_id = m.get("sender_id", "user")
        if "admin" in sender_id.lower():
            continue  # Do not notify admin of their own outgoing replies
        msg_id_val = m.get("message_id") or str(m.get("_id", "msg"))
        notif_id = f"admin_msg_{msg_id_val}"
        exists = await mongodb.db.notifications.find_one({"notification_id": notif_id})
        if not exists:
            sender_name = m.get("sender_name") or "Food Donor"
            await mongodb.db.notifications.insert_one({
                "notification_id": notif_id,
                "user_id": "admin_broadcast",
                "title": f"💬 New Message from {sender_name}",
                "message": m.get("text") or m.get("content") or "New message received",
                "type": "CHAT_MESSAGE",
                "related_entity_id": m.get("conversation_id", "conv_admin_donor"),
                "read": m.get("read", False),
                "created_at": m.get("timestamp", now)
            })

    # 2. Fetch and return standard notifications
    notifications = await get_user_notifications("admin_broadcast", limit)
    return notifications

@router.put("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_notification(notification_id: str, current_user: dict = Depends(get_current_user)):
    target_user_id: str = "admin_broadcast" if current_user.get("role", "").upper() == "ADMIN" else str(current_user.get("firebase_uid") or current_user.get("_id") or "user")
    await mark_as_read(notification_id, target_user_id)
    return

@router.put("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all_notifications(current_user: dict = Depends(get_current_user)):
    target_user_id: str = "admin_broadcast" if current_user.get("role", "").upper() == "ADMIN" else str(current_user.get("firebase_uid") or current_user.get("_id") or "user")
    await mark_all_as_read(target_user_id)
    return

@router.delete("/clear-all", status_code=status.HTTP_200_OK)
async def clear_all(current_user: dict = Depends(get_current_user)):
    from app.database.mongodb import mongodb
    from datetime import datetime, timezone
    target_user_id = current_user.get("firebase_uid") or str(current_user.get("_id", "user"))
    if current_user.get("role", "").upper() == "ADMIN":
        try:
            await mongodb.db.system_settings.update_one(
                {"key": "admin_notifications_cleared_at"},
                {"$set": {"key": "admin_notifications_cleared_at", "timestamp": datetime.now(timezone.utc)}},
                upsert=True,
            )
        except Exception:
            pass
        target_user_id = "admin_broadcast"
    deleted = await clear_all_notifications(target_user_id)
    return {"status": "success", "deleted_count": deleted}

@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_single_notification(notification_id: str, current_user: dict = Depends(get_current_user)):
    target_user_id = current_user.get("firebase_uid") or str(current_user.get("_id", "user"))
    if current_user.get("role", "").upper() == "ADMIN":
        target_user_id = "admin_broadcast"
    await delete_notification(notification_id, target_user_id)
    return {"status": "success", "notification_id": notification_id}
