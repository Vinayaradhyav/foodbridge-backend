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
    """Retrieves user FCM token and sends the push notification."""
    db = get_database()
    user = await db["users"].find_one({
        "$or": [
            {"firebase_uid": notification.user_id},
            {"id": notification.user_id},
            {"user_id": notification.user_id},
            {"email": notification.user_id}
        ]
    })
    
    if not user:
        return
        
    fcm_token = user.get("fcm_token")
    if not fcm_token:
        logger.info(f"User {notification.user_id} has no FCM token. Skipping push.")
        return
        
    messaging_client = get_messaging_client()
    if not messaging_client:
        logger.info("Firebase Cloud Messaging (FCM) is not active. Push notification skipped.")
        return
        
    message = messaging.Message(
        notification=messaging.Notification(
            title=notification.title,
            body=notification.message,
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
    cursor = collection.find({
        "$or": [
            {"user_id": user_id},
            {"user_id": "admin_broadcast"} if user_id in ["admin", "admin_super_token", "mock_token_123"] else {"user_id": "broadcast"},
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
