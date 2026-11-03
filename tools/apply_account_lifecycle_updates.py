import os

# 1. Update backend/app/api/auth.py
auth_path = os.path.join("app", "api", "auth.py")
with open(auth_path, "r", encoding="utf-8") as f:
    auth_code = f.read()

old_auth_check = """        if user.get("status") == "deleted":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deleted."
            )"""

new_auth_check = """        if user.get("status") == "deleted":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been permanently deleted."
            )

        if user.get("status") == "rejected" or user.get("verification_status") == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account application has been rejected by administration. Please contact support."
            )"""

auth_norm = auth_code.replace("\r\n", "\n")
if old_auth_check.replace("\r\n", "\n") in auth_norm:
    auth_norm = auth_norm.replace(old_auth_check.replace("\r\n", "\n"), new_auth_check)
    with open(auth_path, "w", encoding="utf-8") as f:
        f.write(auth_norm)
    print("Updated app/api/auth.py: Rejection check added.")
else:
    print("Could not find old_auth_check in auth.py")

# 2. Update backend/app/api/users.py for hard deletion
users_path = os.path.join("app", "api", "users.py")
with open(users_path, "r", encoding="utf-8") as f:
    users_code = f.read()

old_delete_logic = """    # 4. Mark account status as deleted and anonymize personal identifiers
    anonymized_email = f"deleted_{os.urandom(6).hex()}@foodbridge.invalid"
    await mongodb.db.users.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {
            "status": "deleted",
            "name": "Deleted Account",
            "email": anonymized_email,
            "phone": "0000000000",
            "hashed_password": None,
            "fcm_token": None,
            "deleted_at": now,
            "updated_at": now
        }}
    )"""

new_delete_logic = """    # 4. Permanently delete user document from database as required by administrative control
    await mongodb.db.users.delete_one({"_id": user_doc["_id"]})
    # Also clean up any lingering sessions/notifications for this user
    await mongodb.db.notifications.delete_many({"user_id": uid})"""

users_norm = users_code.replace("\r\n", "\n")
if old_delete_logic.replace("\r\n", "\n") in users_norm:
    users_norm = users_norm.replace(old_delete_logic.replace("\r\n", "\n"), new_delete_logic)
    with open(users_path, "w", encoding="utf-8") as f:
        f.write(users_norm)
    print("Updated app/api/users.py: Hard delete implemented.")
else:
    print("Could not find old_delete_logic in users.py")
