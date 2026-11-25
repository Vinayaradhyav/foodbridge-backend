from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Response
from typing import List, Optional, Dict, Any
from app.database.mongodb import mongodb
from app.core.security import get_current_user, require_role, revoke_token
from app.models.user import UserModel
from app.schemas.user import UserResponse
from bson import ObjectId
from datetime import datetime, timezone
import os
import re
import base64

router = APIRouter(prefix="/users", tags=["Users"])

UPLOADS_PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "profiles"
)
os.makedirs(UPLOADS_PROFILE_DIR, exist_ok=True)


def is_synthetic_user(u: Optional[Dict[str, Any]]) -> bool:
    """Returns True only for soft-deleted accounts. Retains all registered Android, web, and operational users."""
    if not u:
        return True
    st = str(u.get("status", "")).lower().strip()
    if st == "deleted":
        return True
    email = str(u.get("email", "")).lower().strip()
    if email.startswith("deleted_") or email.endswith("@foodbridge.invalid"):
        return True
    return False


@router.get("", response_model=List[UserResponse])
async def get_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    include_admins: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    query: Dict[str, Any] = {"status": {"$ne": "deleted"}}
    if not include_admins and not role:
        query["role"] = {"$not": {"$regex": "^admin$", "$options": "i"}}
    if role:
        r_clean = role.lower().strip()
        if r_clean in ["ngo", "receiver", "food_receiver"]:
            query["$or"] = [
                {"role": {"$regex": "^(ngo|receiver|food_receiver)$", "$options": "i"}},
                {"receiver_type": {"$ne": None}}
            ]
        elif r_clean in ["volunteer", "courier"]:
            query["role"] = {"$regex": "^(volunteer|courier)$", "$options": "i"}
        elif r_clean == "donor":
            query["role"] = {"$regex": "^donor$", "$options": "i"}
        else:
            query["role"] = {"$regex": f"^{role}$", "$options": "i"}
    if status:
        query["status"] = {"$regex": f"^{status}$", "$options": "i"}

    if search and search.strip():
        s = re.escape(search.strip())
        search_filter = {
            "$or": [
                {"name": {"$regex": s, "$options": "i"}},
                {"email": {"$regex": s, "$options": "i"}},
                {"phone": {"$regex": s, "$options": "i"}},
                {"organization_name": {"$regex": s, "$options": "i"}}
            ]
        }
        if "$or" in query:
            query = {"$and": [query, search_filter]}
        else:
            query.update(search_filter)
        
    skip_val = max(0, skip)
    limit_val = max(1, min(1000, limit))

    users = (
        await mongodb.db.users.find(query)
        .sort("created_at", -1)
        .skip(skip_val)
        .limit(limit_val)
        .to_list(length=limit_val)
    )
    formatted_users = []
    for u in users:
        if not u or is_synthetic_user(u):
            continue
        try:
            # Sanitize malformed email so a single legacy document never triggers HTTP 500
            raw_email = str(u.get("email") or "").strip()
            if "@" not in raw_email or "." not in raw_email.split("@")[-1]:
                safe_uid = str(u.get("firebase_uid") or u.get("_id") or "user").replace(" ", "_")
                u["email"] = f"{safe_uid}@foodbridge.org"
            doc = UserModel.format_for_response(u)
            formatted_users.append(UserResponse.model_validate(doc))
        except Exception:
            continue
    return formatted_users

async def _find_user(user_id: str):
    if not user_id:
        return None
    user = None
    try:
        user = await mongodb.db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        pass
    if user:
        return user
    
    clean_id = user_id.strip()
    digits = re.sub(r'\D', '', clean_id)
    search: List[Dict[str, Any]] = [
        {"firebase_uid": clean_id},
        {"email": clean_id.lower()},
        {"phone": clean_id},
    ]
    if digits:
        last10 = digits[-10:] if len(digits) >= 10 else digits
        search.append({"phone": digits})
        search.append({"phone": last10})
        search.append({"phone": f"+91{last10}"})
        search.append({"phone": f"+91 {last10}"})
        search.append({"phone": {"$regex": f"{last10}$"}})
    return await mongodb.db.users.find_one({"$or": search})

@router.get("/pending-approvals", response_model=List[UserResponse])
async def get_pending_approvals(current_user: dict = Depends(get_current_user)):
    """Fetch all users currently awaiting AI & Admin authorization."""
    query: Dict[str, Any] = {
        "$or": [
            {"verification_status": {"$in": ["PENDING", "UNDER_REVIEW"]}},
            {"status": {"$in": ["pending", "pending_approval"]}}
        ],
        "status": {"$ne": "deleted"},
        "role": {"$not": {"$regex": "^admin$", "$options": "i"}}
    }
    users = await mongodb.db.users.find(query).sort("created_at", -1).to_list(length=500)
    return [UserModel.format_for_response(u) for u in users if u and not is_synthetic_user(u)]

from pydantic import BaseModel

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    pincode: Optional[str] = None
    organization_id: Optional[str] = None
    darpan_id: Optional[str] = None
    pan_number: Optional[str] = None
    cin_number: Optional[str] = None
    contact_person: Optional[str] = None
    designation: Optional[str] = None
    tax_exemption_status: Optional[str] = None
    profile_image: Optional[str] = None
    profile_image_url: Optional[str] = None
    avatar_url: Optional[str] = None
    family_size: Optional[int] = None
    dietary_needs: Optional[str] = None
    id_proof_type: Optional[str] = None
    id_proof_number_masked: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ProfileImageBase64Request(BaseModel):
    image_base64: str
    content_type: Optional[str] = "image/jpeg"
    filename: Optional[str] = "profile.jpg"


async def _save_user_profile_media(user_doc: dict, image_bytes: bytes, content_type: str, filename: str) -> dict:
    """Permanently store user profile image in MongoDB Atlas and disk cache."""
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image size exceeds maximum limit of 10 MB.")
    
    # Auto-detect mime type from byte signatures
    if image_bytes.startswith(b"\xff\xd8\xff"):
        content_type = "image/jpeg"
    elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type = "image/png"
    elif image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        content_type = "image/webp"
    elif content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Unsupported image format. Allowed: JPEG, PNG, WebP.")

    user_id = str(user_doc.get("firebase_uid") or user_doc.get("_id", ""))
    safe_file_id = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)
    cache_path = os.path.join(UPLOADS_PROFILE_DIR, f"{safe_file_id}.jpg")

    # 1. Save to local disk cache for immediate static serving
    try:
        with open(cache_path, "wb") as f:
            f.write(image_bytes)
    except Exception as e:
        print(f"[UsersAPI] Warning: could not write local profile cache: {e}")

    # 2. Save permanently in MongoDB Atlas 'profile_media' collection (guaranteed persistence across restarts)
    b64_str = base64.b64encode(image_bytes).decode("utf-8")
    now = datetime.now(timezone.utc)
    v_tag = int(now.timestamp())
    canonical_url = f"/api/users/{user_id}/profile-image?v={v_tag}"

    await mongodb.db.profile_media.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "firebase_uid": user_doc.get("firebase_uid"),
            "user_obj_id": user_doc["_id"],
            "filename": filename or f"{safe_file_id}.jpg",
            "content_type": content_type,
            "data_base64": b64_str,
            "size_bytes": len(image_bytes),
            "updated_at": now
        }},
        upsert=True
    )

    # 3. Update User document with canonical URL
    await mongodb.db.users.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {
            "profile_image_url": canonical_url,
            "avatar_url": canonical_url,
            "profile_image": canonical_url,
            "profile_image_storage_path": cache_path,
            "profile_image_updated_at": now,
            "updated_at": now
        }}
    )

    updated = await mongodb.db.users.find_one({"_id": user_doc["_id"]})
    return UserModel.format_for_response(updated or user_doc)


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Fetch the authenticated user's profile."""
    return UserModel.format_for_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    req: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update the authenticated user's profile fields."""
    update_fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_fields:
        return UserModel.format_for_response(current_user)
    update_fields["updated_at"] = datetime.now(timezone.utc)
    await mongodb.db.users.update_one({"_id": current_user["_id"]}, {"$set": update_fields})
    updated = await mongodb.db.users.find_one({"_id": current_user["_id"]})
    return UserModel.format_for_response(updated or current_user)


@router.patch("/me", response_model=UserResponse)
async def patch_my_profile(
    req: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Partial update of the authenticated user's profile fields."""
    return await update_my_profile(req, current_user)


@router.post("/me/profile-image", response_model=UserResponse)
async def upload_my_profile_image(
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Permanently upload profile photo for the authenticated user via multipart/form-data.
    Stores image in MongoDB Atlas profile_media + disk cache.
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No image file provided in multipart 'file' field")
    image_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"
    filename = file.filename or "profile.jpg"
    return await _save_user_profile_media(current_user, image_bytes, content_type, filename)


@router.post("/me/profile-image/base64", response_model=UserResponse)
async def upload_my_profile_image_base64(
    payload: ProfileImageBase64Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Permanently upload profile photo via JSON base64 string.
    """
    clean_b64 = payload.image_base64
    if "base64," in clean_b64:
        clean_b64 = clean_b64.split("base64,")[1]
    try:
        image_bytes = base64.b64decode(clean_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")
    content_type = payload.content_type or "image/jpeg"
    filename = payload.filename or "profile.jpg"
    return await _save_user_profile_media(current_user, image_bytes, content_type, filename)


@router.delete("/me/profile-image", response_model=UserResponse)
async def delete_my_profile_image(current_user: dict = Depends(get_current_user)):
    """Delete authenticated user's custom profile image and restore default avatar."""
    user_id = str(current_user.get("firebase_uid") or current_user.get("_id", ""))
    await mongodb.db.profile_media.delete_many({"$or": [{"user_id": user_id}, {"firebase_uid": user_id}]})
    now = datetime.now(timezone.utc)
    await mongodb.db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "profile_image_url": None,
            "avatar_url": None,
            "profile_image": None,
            "profile_image_updated_at": now,
            "updated_at": now
        }}
    )
    updated = await mongodb.db.users.find_one({"_id": current_user["_id"]})
    return UserModel.format_for_response(updated or current_user)


@router.get("/{user_id}/profile-image")
async def stream_user_profile_image(user_id: str):
    """
    Stream user profile image with HTTP caching headers.
    Retrieves from MongoDB Atlas profile_media collection or disk cache.
    """
    media_doc = await mongodb.db.profile_media.find_one({
        "$or": [{"user_id": user_id}, {"firebase_uid": user_id}]
    })

    if media_doc and media_doc.get("data_base64"):
        try:
            img_bytes = base64.b64decode(media_doc["data_base64"])
            c_type = media_doc.get("content_type", "image/jpeg")
            return Response(
                content=img_bytes,
                media_type=c_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Disposition": f"inline; filename={media_doc.get('filename', 'profile.jpg')}"
                }
            )
        except Exception:
            pass

    # Fallback to disk cache
    safe_file_id = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)
    cache_path = os.path.join(UPLOADS_PROFILE_DIR, f"{safe_file_id}.jpg")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                img_bytes = f.read()
            return Response(
                content=img_bytes,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except Exception:
            pass

    # If no custom photo exists, return 404 so UI displays its theme-adaptive initials/placeholder
    raise HTTPException(status_code=404, detail="No custom profile image found for this user")


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_by_id(
    user_id: str,
    req: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update a user's profile (allowed for the user themselves or an administrator)."""
    user = await _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
    is_admin = str(current_user.get("role", "")).lower() == "admin"
    curr_uid = current_user.get("firebase_uid") or str(current_user.get("_id", ""))
    target_uid = user.get("firebase_uid") or str(user.get("_id", ""))
    if not is_admin and curr_uid != target_uid:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")
    update_fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await mongodb.db.users.update_one({"_id": user["_id"]}, {"$set": update_fields})
    updated = await mongodb.db.users.find_one({"_id": user["_id"]})
    return UserModel.format_for_response(updated or user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    user = await _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
        
    return UserModel.format_for_response(user)

@router.put("/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can authorize accounts")
        
    user = await _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
        
    now = datetime.now(timezone.utc)
    
    await mongodb.db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "status": "active",
            "verification_status": "VERIFIED",
            "permanent_ban": False,
            "suspension_reason": None,
            "rejection_reason": None,
            "approved_by": "Food-Bridge System Admin",
            "approved_at": now,
            "updated_at": now
        }}
    )

    # Admin Draw-Back: Remove phone & email from permanent ban registry if previously banned
    user_email = str(user.get("email") or "").strip().lower()
    user_digits = re.sub(r'\D', '', str(user.get("phone") or ""))
    last10 = user_digits[-10:] if len(user_digits) >= 10 else user_digits
    unban_or = []
    if user_email:
        unban_or.append({"email": user_email})
    if last10:
        unban_or.append({"phone_key": last10})
    if unban_or:
        await mongodb.db.banned_credentials.delete_many({"$or": unban_or})
    
    # Audit Log
    await mongodb.db.audit_logs.insert_one({
        "action": "APPROVE_USER",
        "user_id": str(user.get("_id", user.get("firebase_uid", ""))),
        "user_name": user.get("name"),
        "role": user.get("role"),
        "admin_id": current_user.get("firebase_uid", "admin"),
        "timestamp": now,
        "details": f"Admin authorized organization {user.get('name')} for full network participation"
    })

    # Notify User
    await mongodb.db.notifications.insert_one({
        "user_id": user.get("firebase_uid") or str(user.get("_id")),
        "title": "🎉 Application Approved!",
        "body": "Your organization application has been authorized by Food-Bridge Admin. You now have full platform access.",
        "type": "ACCOUNT_VERIFIED",
        "read": False,
        "created_at": now
    })
    
    updated_user = await mongodb.db.users.find_one({"_id": user["_id"]})
    return UserModel.format_for_response(updated_user)



from pydantic import BaseModel
class RejectRequest(BaseModel):
    reason: Optional[str] = "Application declined or account suspended by administrator"
    status: Optional[str] = "SUSPENDED"
    permanent_ban: Optional[bool] = True
    phone: Optional[str] = None
    email: Optional[str] = None

@router.put("/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: str,
    req: Optional[RejectRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can reject or suspend accounts")
        
    user = await _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
        
    reason = req.reason if req and req.reason else "Suspended by administrator"
    verif_status = (req.status if req and req.status else "SUSPENDED").upper()
    now = datetime.now(timezone.utc)
    
    await mongodb.db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "status": "suspended",
            "verification_status": verif_status,
            "rejection_reason": reason,
            "suspension_reason": reason,
            "permanent_ban": True,
            "rejected_by": "Food-Bridge System Admin",
            "rejected_at": now,
            "updated_at": now
        }}
    )

    # Permanently ban phone & email so they cannot re-register or access FoodBridge again
    u_email = str((req.email if req and req.email else None) or user.get("email") or "").strip().lower()
    u_phone = str((req.phone if req and req.phone else None) or user.get("phone") or "").strip()
    u_digits = re.sub(r'\D', '', u_phone)
    last10 = u_digits[-10:] if len(u_digits) >= 10 else u_digits
    if u_email or last10:
        await mongodb.db.banned_credentials.update_one(
            {"$or": [c for c in [{"email": u_email} if u_email else None, {"phone_key": last10} if last10 else None] if c]},
            {"$set": {
                "email": u_email,
                "phone": u_phone,
                "phone_key": last10,
                "user_name": user.get("name"),
                "reason": reason,
                "banned_at": now,
                "banned_by": current_user.get("firebase_uid", "admin"),
            }},
            upsert=True,
        )
    
    await mongodb.db.audit_logs.insert_one({
        "action": "SUSPEND_AND_BAN_USER",
        "user_id": str(user.get("_id", user.get("firebase_uid", ""))),
        "user_name": user.get("name"),
        "role": user.get("role"),
        "admin_id": current_user.get("firebase_uid", "admin"),
        "timestamp": now,
        "details": f"Permanently suspended & banned {user.get('name')} ({u_phone} / {u_email}): {reason}"
    })
    
    await mongodb.db.notifications.insert_one({
        "user_id": user.get("firebase_uid") or str(user.get("_id")),
        "title": "🚫 Account Permanently Suspended",
        "body": f"Your FoodBridge account has been suspended & your phone/email restricted. Reason: {reason}. Contact 24/7 Helpline for Admin review.",
        "type": "ACCOUNT_SUSPENDED",
        "read": False,
        "created_at": now
    })
    
    updated_user = await mongodb.db.users.find_one({"_id": user["_id"]})
    return UserModel.format_for_response(updated_user)

from pydantic import BaseModel
class VerificationRequest(BaseModel):
    status: str
    reason: Optional[str] = None

@router.put("/{user_id}/verify", response_model=UserResponse)
async def update_verification_status(
    user_id: str,
    req: VerificationRequest,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update verification status")
        
    valid_statuses = ["PENDING", "UNDER_REVIEW", "VERIFIED", "REJECTED", "SUSPENDED"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {valid_statuses}")
        
    user = None
    try:
        user = await mongodb.db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        pass
        
    if not user:
        user = await mongodb.db.users.find_one({"firebase_uid": user_id})
    if not user:
        user = await mongodb.db.users.find_one({"email": user_id.lower().strip()})
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    now = datetime.now(timezone.utc)
    update_data = {
        "verification_status": req.status,
        "updated_at": now
    }
    
    if req.status == "VERIFIED":
        update_data["status"] = "active"
    elif req.status in ["REJECTED", "SUSPENDED"]:
        update_data["status"] = "inactive"
        
    await mongodb.db.users.update_one({"_id": user["_id"]}, {"$set": update_data})
    
    await mongodb.db.audit_logs.insert_one({
        "action": f"UPDATE_VERIFICATION_{req.status}",
        "user_id": str(user.get("_id", user.get("firebase_uid", ""))),
        "admin_id": current_user.get("firebase_uid"),
        "timestamp": now,
        "details": req.reason or f"Admin changed verification status to {req.status}"
    })
    
    updated_user = await mongodb.db.users.find_one({"_id": user["_id"]})
    return UserModel.format_for_response(updated_user)

# ==================== DELETE ACCOUNT (Item 18 & Item 10 RLS) ====================
async def _execute_account_deletion(user_doc: dict, actor_id: str):
    """Safely delete/anonymize an account and clean up active links."""
    now = datetime.now(timezone.utc)
    uid = user_doc.get("firebase_uid") or str(user_doc["_id"])
    
    # 1. Cancel any active donations posted by this user
    await mongodb.db.donations.update_many(
        {"donor_id": uid, "status": {"$in": ["AVAILABLE", "PENDING", "MATCHING"]}},
        {"$set": {"status": "CANCELLED", "cancel_reason": "Account closed by user", "updated_at": now}}
    )

    # 2. Anonymize completed donations to maintain food stats
    await mongodb.db.donations.update_many(
        {"donor_id": uid},
        {"$set": {"donor_name": "Former Community Donor"}}
    )

    # 3. Release any active volunteer deliveries
    await mongodb.db.assignments.update_many(
        {"volunteer_id": uid, "status": {"$in": ["ASSIGNED", "ACCEPTED", "IN_TRANSIT"]}},
        {"$set": {"status": "RE_ROUTED", "volunteer_id": None, "updated_at": now}}
    )

    # 4. Permanently delete user document from database as required by administrative control
    await mongodb.db.users.delete_one({"_id": user_doc["_id"]})
    # Also clean up any lingering sessions/notifications for this user
    await mongodb.db.notifications.delete_many({"user_id": uid})

    # 5. Audit Log
    await mongodb.db.audit_logs.insert_one({
        "action": "DELETE_ACCOUNT",
        "user_id": uid,
        "actor_id": actor_id,
        "timestamp": now,
        "details": f"Account {uid} permanently deleted and personal data anonymized under GDPR/Data Protection guidelines."
    })

@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(current_user: dict = Depends(get_current_user)):
    """Delete currently authenticated user's account."""
    uid = current_user.get("firebase_uid") or str(current_user.get("_id", ""))
    await _execute_account_deletion(current_user, actor_id=uid)
    return {
        "status": "success",
        "message": "Your Food-Bridge account has been permanently deleted and personal information purged."
    }

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete an account. 
    Enforces Row-Level Security: Users can only delete their own account unless they are an Administrator.
    """
    is_admin = str(current_user.get("role", "")).lower() == "admin"
    current_uid = current_user.get("firebase_uid") or str(current_user.get("_id", ""))
    
    target_user = None
    try:
        target_user = await mongodb.db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        pass
        
    if not target_user:
        target_user = await mongodb.db.users.find_one({
            "$or": [{"firebase_uid": user_id}, {"email": user_id.lower().strip()}]
        })
        
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")

    target_uid = target_user.get("firebase_uid") or str(target_user["_id"])
    if not is_admin and target_uid != current_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Row-level security violation: You do not have permission to delete this account."
        )

    await _execute_account_deletion(target_user, actor_id=current_uid)
    return {
        "status": "success",
        "message": f"Account {target_uid} has been successfully deleted."
    }
