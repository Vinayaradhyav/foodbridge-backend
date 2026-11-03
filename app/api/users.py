from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.database.mongodb import mongodb
from app.core.security import get_current_user, require_role, revoke_token
from app.models.user import UserModel
from app.schemas.user import UserResponse
from bson import ObjectId
from datetime import datetime, timezone
import os
import re

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("", response_model=List[UserResponse])
async def get_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    query = {"status": {"$ne": "deleted"}}
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
        
    users = await mongodb.db.users.find(query).skip(skip).limit(limit).to_list(length=limit)
    return [UserModel.format_for_response(u) for u in users if u]

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
    search = [
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
    query = {
        "$or": [
            {"verification_status": {"$in": ["PENDING", "UNDER_REVIEW"]}},
            {"status": {"$in": ["pending", "pending_approval"]}}
        ],
        "role": {"$ne": "admin"}
    }
    users = await mongodb.db.users.find(query).to_list(length=500)
    return [UserModel.format_for_response(u) for u in users if u]

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
            "approved_by": "Food-Bridge System Admin",
            "approved_at": now,
            "updated_at": now
        }}
    )
    
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
    reason: Optional[str] = "Application declined by administrator"
    status: Optional[str] = "REJECTED"

@router.put("/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: str,
    req: Optional[RejectRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can reject accounts")
        
    user = await _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
        
    reason = req.reason if req and req.reason else "Application declined by administrator"
    now = datetime.now(timezone.utc)
    
    await mongodb.db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "status": "suspended",
            "verification_status": "REJECTED",
            "rejection_reason": reason,
            "rejected_by": "Food-Bridge System Admin",
            "rejected_at": now,
            "updated_at": now
        }}
    )
    
    await mongodb.db.audit_logs.insert_one({
        "action": "REJECT_USER",
        "user_id": str(user.get("_id", user.get("firebase_uid", ""))),
        "user_name": user.get("name"),
        "role": user.get("role"),
        "admin_id": current_user.get("firebase_uid", "admin"),
        "timestamp": now,
        "details": f"Admin rejected organization {user.get('name')}: {reason}"
    })
    
    await mongodb.db.notifications.insert_one({
        "user_id": user.get("firebase_uid") or str(user.get("_id")),
        "title": "Application Update",
        "body": f"Your organization application review was not approved: {reason}",
        "type": "ACCOUNT_REJECTED",
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
