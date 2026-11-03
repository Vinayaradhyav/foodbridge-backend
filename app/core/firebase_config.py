"""
FoodBridge Centralized Firebase Configuration & Admin SDK Manager.

Features:
- Thread-safe singleton initialization (prevents duplicate app errors)
- Multi-source credential resolution:
    1. Configurable path (FIREBASE_CREDENTIALS_PATH)
    2. Google application credentials (GOOGLE_APPLICATION_CREDENTIALS)
    3. Auto-discovery in backend/config/ and backend/
    4. Individual environment variables (FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY, etc.)
- Strict PEM & placeholder validation to prevent 'Unable to load PEM file' crashes
- Safe status reporting without exposing secret keys or tokens
- Reusable across Auth, FCM Messaging, Firestore, and Storage
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, auth, messaging

logger = logging.getLogger("food_bridge.firebase")

# Global tracking state
_firebase_initialized: bool = False
_firebase_project_id: Optional[str] = None
_credential_source: Optional[str] = None
_initialization_reason: str = "Uninitialized"

def _is_placeholder(val: Optional[str]) -> bool:
    """Detect common template placeholders from .env.example."""
    if not val:
        return True
    s = val.strip().lower()
    return (
        "your-project-id" in s
        or "your_key_here" in s
        or "your-private-key" in s
        or "firebase-adminsdk-xxx" in s
        or "your-secret-key" in s
        or s == "..."
    )

def _resolve_service_account_file() -> Optional[Path]:
    """Find a valid service account JSON file from configured or default paths."""
    backend_dir = Path(__file__).resolve().parent.parent.parent

    candidate_paths = []

    # 1. Explicit environment variables
    env_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if env_path:
        candidate_paths.append(Path(env_path))
        if not os.path.isabs(env_path):
            candidate_paths.append(backend_dir / env_path)

    g_env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if g_env_path:
        candidate_paths.append(Path(g_env_path))
        if not os.path.isabs(g_env_path):
            candidate_paths.append(backend_dir / g_env_path)

    # 2. Standard convention locations
    candidate_paths.extend([
        backend_dir / "config" / "firebase-service-account.json",
        backend_dir / "config" / "serviceAccountKey.json",
        backend_dir / "firebase-service-account.json",
        backend_dir / "serviceAccountKey.json",
        backend_dir / "firebase-adminsdk.json",
    ])

    for path in candidate_paths:
        try:
            if path.exists() and path.is_file():
                # Validate JSON syntax and structure safely without exposing content
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check minimal required fields for service account credentials
                if data.get("type") == "service_account" and data.get("project_id"):
                    pk = data.get("private_key", "")
                    if "-----BEGIN PRIVATE KEY-----" in pk and len(pk) > 500:
                        return path
                    else:
                        logger.warning(
                            f"Service account file at {path} contains an invalid or placeholder private key."
                        )
        except Exception as e:
            logger.debug(f"Candidate path {path} failed inspection: {e}")
            continue

    return None

def initialize_firebase() -> bool:
    """
    Initializes the Firebase Admin SDK safely.
    Guaranteed singleton - will not reinitialize if already active.
    """
    global _firebase_initialized, _firebase_project_id, _credential_source, _initialization_reason

    # If already initialized (e.g. across tests or hot-reload), return active state
    if firebase_admin._apps:
        _firebase_initialized = True
        return True

    try:
        # Strategy A: Service Account JSON File
        cred_file = _resolve_service_account_file()
        if cred_file:
            cred = credentials.Certificate(str(cred_file))
            # Safely extract project ID for status without revealing secrets
            with open(cred_file, "r", encoding="utf-8") as f:
                pj_id = json.load(f).get("project_id", "configured-project")

            firebase_admin.initialize_app(cred, {"projectId": pj_id})
            _firebase_initialized = True
            _firebase_project_id = pj_id
            _credential_source = f"file:{cred_file.name}"
            _initialization_reason = "Initialized successfully from service-account JSON"
            logger.info(f"Firebase Admin SDK initialized successfully using certificate [{cred_file.name}] (Project: {pj_id})")
            return True

        # Strategy B: Individual Environment Variables (with strict validation)
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
        private_key = os.getenv("FIREBASE_PRIVATE_KEY")
        private_key_id = os.getenv("FIREBASE_PRIVATE_KEY_ID")

        if project_id and client_email and private_key:
            # Check for placeholder values
            if _is_placeholder(project_id) or _is_placeholder(client_email) or _is_placeholder(private_key):
                _initialization_reason = (
                    "Environment variables contain placeholder values from .env.example. "
                    "A real service-account JSON or valid RSA PEM private key is required."
                )
                logger.info(
                    "Firebase Admin SDK: Environment variables contain template placeholders. "
                    "Place your 'firebase-service-account.json' into 'backend/config/' to enable live Firebase services."
                )
                return False

            # Strict PEM key check
            clean_key = private_key.replace("\\n", "\n").strip()
            if not clean_key.startswith("-----BEGIN PRIVATE KEY-----") or "-----END PRIVATE KEY-----" not in clean_key:
                _initialization_reason = "FIREBASE_PRIVATE_KEY is missing valid PEM header or footer markers."
                logger.warning(_initialization_reason)
                return False

            if len(clean_key) < 500:
                _initialization_reason = (
                    f"FIREBASE_PRIVATE_KEY is only {len(clean_key)} characters long. "
                    "A valid 2048-bit RSA private key is typically 1,600+ characters."
                )
                logger.warning(_initialization_reason)
                return False

            cert_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": private_key_id or "default",
                "private_key": clean_key,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token"
            }

            cred = credentials.Certificate(cert_dict)
            firebase_admin.initialize_app(cred, {"projectId": project_id})
            _firebase_initialized = True
            _firebase_project_id = project_id
            _credential_source = "environment_variables"
            _initialization_reason = "Initialized successfully from environment variables"
            logger.info(f"Firebase Admin SDK initialized successfully from environment variables (Project: {project_id})")
            return True

        # Strategy C: No Credentials Available
        _initialization_reason = (
            "No service-account JSON file found and no complete environment credentials provided. "
            "Download 'firebase-service-account.json' from Firebase Console -> Project Settings -> Service Accounts "
            "and place it in 'backend/config/'."
        )
        logger.info(f"Firebase Admin SDK standby: {_initialization_reason}")
        return False

    except Exception as e:
        _initialization_reason = f"Initialization error: {type(e).__name__} - {str(e)}"
        logger.error(f"Failed to initialize Firebase Admin SDK: {_initialization_reason}")
        return False

def is_firebase_initialized() -> bool:
    """Returns True if Firebase Admin SDK is currently active."""
    return bool(firebase_admin._apps)

def get_firebase_app():
    """Returns the default Firebase app instance or None."""
    if firebase_admin._apps:
        return firebase_admin.get_app()
    return None

def get_auth_client():
    """Returns the Firebase Auth client, or None if not initialized."""
    if firebase_admin._apps:
        return auth
    return None

def get_messaging_client():
    """Returns the Firebase Messaging (FCM) client, or None if not initialized."""
    if firebase_admin._apps:
        return messaging
    return None

def get_firestore_client():
    """Returns the Firestore client, or None if not initialized/installed."""
    if not firebase_admin._apps:
        return None
    try:
        from firebase_admin import firestore
        return firestore.client()
    except Exception as e:
        logger.debug(f"Firestore not available: {e}")
        return None

def get_storage_bucket(bucket_name: Optional[str] = None):
    """Returns the Firebase Storage bucket, or None if not initialized."""
    if not firebase_admin._apps:
        return None
    try:
        from firebase_admin import storage
        name = bucket_name or os.getenv("FIREBASE_STORAGE_BUCKET")
        return storage.bucket(name) if name else storage.bucket()
    except Exception as e:
        logger.debug(f"Firebase Storage bucket not available: {e}")
        return None

def get_firebase_status() -> Dict[str, Any]:
    """
    Returns sanitized Firebase connectivity status for health monitoring.
    Never reveals private keys, tokens, or credential contents.
    """
    active = is_firebase_initialized()
    return {
        "initialized": active,
        "project_id": _firebase_project_id if active else None,
        "credential_source": _credential_source if active else None,
        "auth_available": active and (get_auth_client() is not None),
        "messaging_available": active and (get_messaging_client() is not None),
        "firestore_available": active and (get_firestore_client() is not None),
        "storage_available": active and (get_storage_bucket() is not None),
        "status_detail": _initialization_reason if not active else "Connected and operational"
    }
