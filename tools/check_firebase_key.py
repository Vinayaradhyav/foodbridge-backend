"""
FoodBridge Firebase & Backend Diagnostic Utility.

Inspects Firebase Admin SDK credentials, environment configuration,
and MongoDB connectivity safely without printing secret keys or tokens.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load backend environment
backend_dir = Path(__file__).resolve().parent
load_dotenv(backend_dir / ".env")

# Ensure backend root is on sys.path
sys.path.insert(0, str(backend_dir))

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def run_diagnostics():
    print("=" * 65)
    print("  FOODBRIDGE BACKEND & FIREBASE CONNECTIVITY DIAGNOSTICS")
    print("=" * 65)

    # 1. Inspect Environment Variables
    print("\n[1] Environment Variables Inspection:")
    mongo_url = os.getenv("MONGODB_URL", "")
    db_name = os.getenv("DATABASE_NAME", "")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    project_id = os.getenv("FIREBASE_PROJECT_ID", "")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL", "")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY", "")

    print(f"  * MONGODB_URL configured: {bool(mongo_url)}")
    print(f"  * DATABASE_NAME: {db_name or '(not set)'}")
    print(f"  * FIREBASE_CREDENTIALS_PATH: {cred_path or '(not set)'}")
    print(f"  * FIREBASE_PROJECT_ID: {'[CONFIGURED]' if project_id else '[NOT SET]'}")
    print(f"  * FIREBASE_CLIENT_EMAIL: {'[CONFIGURED]' if client_email else '[NOT SET]'}")
    print(f"  * FIREBASE_PRIVATE_KEY present: {bool(private_key)}")
    if private_key:
        clean_key = private_key.replace("\\n", "\n").strip()
        has_header = clean_key.startswith("-----BEGIN PRIVATE KEY-----")
        has_footer = "-----END PRIVATE KEY-----" in clean_key
        is_placeholder = "YOUR_KEY_HERE" in clean_key or len(clean_key) < 500
        print(f"    - Key length: {len(clean_key)} characters")
        print(f"    - PEM header valid: {has_header}")
        print(f"    - PEM footer valid: {has_footer}")
        print(f"    - Placeholder detected: {is_placeholder}")
        if is_placeholder:
            print("    [!] WARNING: Private key is a template placeholder, not a real RSA private key.")

    # 2. Inspect Service Account JSON Candidates
    print("\n[2] Service Account JSON Discovery:")
    from app.core.firebase_config import _resolve_service_account_file
    resolved_file = _resolve_service_account_file()
    if resolved_file:
        print(f"  [+] Found valid service account file: {resolved_file}")
    else:
        print("  [-] No valid service account JSON file found in config/ or backend/ directories.")

    # 3. Test Firebase Initialization
    print("\n[3] Testing Firebase Admin SDK Initialization:")
    from app.core.firebase_config import initialize_firebase, get_firebase_status
    init_success = initialize_firebase()
    status = get_firebase_status()
    print(f"  * Initialization Success: {init_success}")
    print(f"  * Active Status: {status.get('initialized')}")
    print(f"  * Project ID: {status.get('project_id') or '(none)'}")
    print(f"  * Credential Source: {status.get('credential_source') or '(none)'}")
    print(f"  * Auth Client Available: {status.get('auth_available')}")
    print(f"  * FCM Messaging Available: {status.get('messaging_available')}")
    print(f"  * Status Detail: {status.get('status_detail')}")

    # 4. Test MongoDB Connectivity
    print("\n[4] Testing MongoDB Connectivity:")
    import asyncio
    from app.database.mongodb import mongodb, connect_to_mongo, close_mongo_connection

    async def check_mongo():
        try:
            await connect_to_mongo()
            if mongodb.client is not None:
                await mongodb.client.admin.command("ping")
                print("  [+] MongoDB connected and ping successful!")
                db = mongodb.db
                if db is not None:
                    users_count = await db.users.count_documents({})
                    donations_count = await db.donations.count_documents({})
                    print(f"    - Total users in database: {users_count}")
                    print(f"    - Total donations in database: {donations_count}")
            else:
                print("  [-] MongoDB client could not connect.")
        except Exception as e:
            print(f"  [-] MongoDB connection failed: {e}")
        finally:
            await close_mongo_connection()

    asyncio.run(check_mongo())

    print("\n" + "=" * 65)
    print("  DIAGNOSTICS COMPLETE")
    print("=" * 65)

if __name__ == "__main__":
    run_diagnostics()
