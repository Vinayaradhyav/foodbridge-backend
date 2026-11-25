import logging
from typing import List, Optional
from datetime import datetime
from app.database.mongodb import get_database
from app.models.notification import NotificationModel
from app.schemas.notification import NotificationCreate
from app.core.firebase_config import get_messaging_client
import firebase_admin
from firebase_admin import messaging

logger = logging.getLogger(__name__)

async def get_notification_collection():
    db = get_database()
    return db["notifications"]

async def create_notification(notification_data: NotificationCreate) -> NotificationModel:
    """Creates a notification in DB and attempts to push to FCM."""
    collection = await get_notification_collection()
    db_notif = NotificationModel(**notification_data.model_dump())
    
    await collection.insert_one(db_notif.model_dump(by_alias=True))
    
    # Try sending push notification
    try:
        await send_push_notification(db_notif)
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        
    return db_notif

async def send_push_notification(notification: NotificationModel):
    """Retrieves recipient FCM token(s) and sends live Firebase push notification."""
    db = get_database()
    messaging_client = get_messaging_client()
    if not messaging_client:
        logger.info("Firebase Cloud Messaging (FCM) is not active. Push notification skipped.")
        return

    # 1. Admin Broadcast / Support Notifications -> push to all admin devices
    if notification.user_id in ["admin", "admin_broadcast"] or "admin" in notification.user_id.lower():
        cursor = db["users"].find({
            "$or": [
                {"role": {"$regex": "^admin$", "$options": "i"}},
                {"email": "admin@foodbridge.org"},
                {"id": "admin_master_001"},
                {"firebase_uid": "admin_master_001"}
            ]
        })
        admins = await cursor.to_list(20)
        for adm in admins:
            token = adm.get("fcm_token")
            if token:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title=notification.title,
                            body=notification.message or notification.body or "",
                        ),
                        data={
                            "type": notification.type,
                            "related_entity_id": notification.related_entity_id or "",
                            "notification_id": notification.notification_id,
                        },
                        token=token,
                    )
                    messaging_client.send(message)
                    logger.info(f"Successfully sent FCM push to admin: {adm.get('email')}")
                except Exception as e:
                    logger.warning(f"FCM push to admin failed: {e}")
        return

    # 2. Targeted User Notification -> find user by UID, ID, Email, or Phone
    target = notification.user_id.strip()
    digits = "".join([c for c in target if c.isdigit()])
    user = await db["users"].find_one({
        "$or": [
            {"firebase_uid": target},
            {"id": target},
            {"user_id": target},
            {"email": target},
            {"phone": target},
            {"phone": {"$regex": digits}} if len(digits) >= 7 else {"firebase_uid": target}
        ]
    })
    
    fcm_token = user.get("fcm_token") if user else None
    if not fcm_token:
        # Check dedicated fcm_tokens collection
        token_doc = await db["fcm_tokens"].find_one({"user_id": target})
        if token_doc:
            fcm_token = token_doc.get("token")

    if not fcm_token:
        logger.info(f"User {notification.user_id} has no FCM token. Skipping push.")
        return
        
    message = messaging.Message(
        notification=messaging.Notification(
            title=notification.title,
            body=notification.message or notification.body or "",
        ),
        data={
            "type": notification.type,
            "related_entity_id": notification.related_entity_id or "",
            "notification_id": notification.notification_id,
        },
        token=fcm_token,
    )
    
    try:
        response = messaging_client.send(message)
        logger.info(f"Successfully sent FCM push notification: {response}")
    except Exception as e:
        logger.error(f"FCM push notification delivery failed: {e}")

async def get_user_notifications(user_id: str, limit: int = 50) -> List[NotificationModel]:
    collection = await get_notification_collection()
    is_adm = "admin" in user_id.lower()
    cursor = collection.find({
        "$or": [
            {"user_id": user_id},
            {"user_id": "admin_broadcast"} if is_adm else {"user_id": "broadcast"},
            {"user_id": "admin"} if is_adm else {"user_id": user_id},
            {"user_id": "all"}
        ]
    }).sort("created_at", -1).limit(limit)
    return [NotificationModel(**doc) async for doc in cursor]

async def mark_as_read(notification_id: str, user_id: str):
    collection = await get_notification_collection()
    await collection.update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"read": True}}
    )

async def mark_all_as_read(user_id: str):
    collection = await get_notification_collection()
    await collection.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True}}
    )

async def delete_notification(notification_id: str, user_id: str) -> bool:
    collection = await get_notification_collection()
    f = {"notification_id": notification_id}
    res = await collection.delete_many(f)
    return res.deleted_count > 0

async def clear_all_notifications(user_id: str) -> int:
    collection = await get_notification_collection()
    if user_id == "admin_broadcast" or "admin" in user_id.lower():
        f = {"user_id": {"$in": ["admin_broadcast", "admin"]}}
    else:
        f = {"user_id": user_id}
    res = await collection.delete_many(f)
    return res.deleted_count
