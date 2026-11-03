"""
FoodBridge Unified Authentication & Token Verification Service.

Verifies:
1. Firebase ID Tokens (when Firebase Admin SDK is initialized)
2. FoodBridge Cryptographically Signed JWT Tokens (standard backend auth)
3. Testing tokens in development/test environment only
"""

import os
import logging
from typing import Dict, Any, Optional

from app.core.firebase_config import get_auth_client, is_firebase_initialized
from app.core.security import decode_access_token

logger = logging.getLogger("food_bridge.auth_service")

class AuthService:
    """Authentication service providing unified token verification."""

    @property
    def auth_client(self):
        """Dynamically get the Firebase Auth client when initialized."""
        return get_auth_client()

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verifies an incoming authentication token.
        
        Resolution order:
        1. Firebase ID token verification (if Firebase is initialized)
        2. FoodBridge signed JWT verification (using SECRET_KEY)
        3. Test suite mock tokens (only allowed when ENVIRONMENT is development or test)
        """
        if not token or not isinstance(token, str):
            raise ValueError("Authentication token is required")

        token = token.strip()

        # 1. Attempt Firebase ID Token verification if Firebase Admin is active
        auth_client = self.auth_client
        if auth_client:
            try:
                decoded = auth_client.verify_id_token(token)
                return {
                    "uid": decoded.get("uid"),
                    "email": decoded.get("email", ""),
                    "role": decoded.get("role", "donor"),
                    "email_verified": decoded.get("email_verified", False),
                    "firebase_user": True,
                    "auth_provider": "firebase"
                }
            except Exception as e:
                # If it wasn't a Firebase token, fall through to check backend JWT
                logger.debug(f"Token is not a valid Firebase ID token: {e}")

        # 2. Attempt Backend HMAC-SHA256 JWT decoding
        jwt_payload = decode_access_token(token)
        if jwt_payload and "sub" in jwt_payload:
            return {
                "uid": str(jwt_payload["sub"]),
                "email": jwt_payload.get("email", ""),
                "role": jwt_payload.get("role", "donor"),
                "email_verified": True,
                "firebase_user": False,
                "auth_provider": "jwt"
            }

        # 3. Allow prefixed mock tokens solely during automated testing or development
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env in ("development", "test", "testing") and (
            token.startswith("mock_") or token.startswith("test_")
        ):
            role = "admin" if "admin" in token else ("ngo" if "ngo" in token else "donor")
            return {
                "uid": token,
                "email": f"{token}@foodbridge.org",
                "role": role,
                "email_verified": True,
                "mock": True,
                "auth_provider": "mock"
            }

        # If neither verification succeeds, reject the request
        if not is_firebase_initialized():
            raise ValueError("Invalid authentication credentials. Firebase service is not initialized and token is not a valid backend session.")
        else:
            raise ValueError("Invalid or expired authentication credentials")

auth_service = AuthService()
