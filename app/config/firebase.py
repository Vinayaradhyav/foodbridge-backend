"""
FoodBridge Legacy Firebase Config Compatibility Module.

Re-exports centralized Firebase services from app.core.firebase_config.
"""

from app.core.firebase_config import (
    initialize_firebase,
    is_firebase_initialized,
    get_firebase_app,
    get_auth_client,
    get_messaging_client,
    get_firestore_client,
    get_storage_bucket,
    get_firebase_status,
)

__all__ = [
    "initialize_firebase",
    "is_firebase_initialized",
    "get_firebase_app",
    "get_auth_client",
    "get_messaging_client",
    "get_firestore_client",
    "get_storage_bucket",
    "get_firebase_status",
]
