from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.services.ngo_service import ngo_service
from app.core.security import get_current_user, require_role
from app.database.mongodb import get_database
from bson import ObjectId

router = APIRouter(prefix="/ngos", tags=["ngos"])

class NgoVerificationDecision(BaseModel):
    status: str = Field(..., pattern="^(VERIFIED|REJECTED|UNDER_REVIEW)$")
    rejection_reason: Optional[str] = None
    reviewer_notes: Optional[str] = "24-hour verification check complete"

class NgoDocumentUpload(BaseModel):
    document_type: str = Field(..., description="80G_CERTIFICATE, 12A_REGISTRATION, FCRA, TRUST_DEED, PAN_CARD")
    document_url: str
    document_number: Optional[str] = None
    issued_date: Optional[str] = None

class NgoProfileCreate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the NGO or representative")
    organization_name: Optional[str] = Field(None, description="Full registered legal NGO name")
    registration_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    capacity_meals: Optional[int] = 100

class BulkClaimRequest(BaseModel):
    donation_ids: List[str]
    pickup_window: Optional[str] = "Within 4 hours"
    intended_beneficiaries: int = 150

@router.post("/")
async def register_ngo(ngo_input: NgoProfileCreate, current_user: dict = Depends(get_current_user)):
    """Registers a new NGO profile associated with the authenticated user."""
    ngo_data = ngo_input.model_dump()
    ngo_data["user_id"] = current_user.get("firebase_uid") or str(current_user.get("_id", ""))
    ngo_data["verification_status"] = "PENDING"
    ngo_data["created_at"] = datetime.now(timezone.utc)
    
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database service temporarily unavailable")
    
    ngo_id = await ngo_service.create_ngo(ngo_data)
    if not ngo_id:
        raise HTTPException(status_code=500, detail="Failed to create NGO profile")
    return {"id": ngo_id, "message": "NGO profile submitted for 24-hour verification"}

@router.get("/")
async def list_ngos(
    verification_status: Optional[str] = Query(None, description="PENDING, VERIFIED, REJECTED"),
    current_user: dict = Depends(get_current_user)
):
    """Lists registered NGOs, with optional verification filter."""
    db = get_database()
    query = {}
    if verification_status:
        query["verification_status"] = verification_status.upper()
        
    cursor = db.ngos.find(query).limit(100)
    ngos = await cursor.to_list(length=100)
    for n in ngos:
        n["id"] = str(n.pop("_id"))
    return ngos

@router.get("/{ngo_id}")
async def get_ngo(ngo_id: str, current_user: dict = Depends(get_current_user)):
    """Fetches a specific NGO profile."""
    ngo = await ngo_service.get_ngo(ngo_id)
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")
    return ngo

@router.post("/{ngo_id}/documents")
async def upload_verification_document(
    ngo_id: str,
    doc: NgoDocumentUpload,
    current_user: dict = Depends(get_current_user)
):
    """
    Submits 80G tax exemption, 12A registration, or Trust certificate
    for administrative review and 24-hour verification.
    """
    db = get_database()
    doc_entry = {
        "document_type": doc.document_type,
        "document_url": doc.document_url,
        "document_number": doc.document_number,
        "issued_date": doc.issued_date,
        "uploaded_at": datetime.now(timezone.utc)
    }

    try:
        await db.ngos.update_one(
            {"_id": ObjectId(ngo_id)},
            {
                "$push": {"verification_documents": doc_entry},
                "$set": {"verification_status": "UNDER_REVIEW", "updated_at": datetime.now(timezone.utc)}
            }
        )
    except Exception:
        raise HTTPException(status_code=404, detail="NGO not found")

    return {
        "status": "SUCCESS",
        "message": f"{doc.document_type} uploaded successfully. Pending 24-hour review.",
        "document": doc_entry
    }

@router.put("/{ngo_id}/verify")
async def verify_ngo(
    ngo_id: str,
    decision: NgoVerificationDecision,
    current_user: dict = Depends(require_role(["ADMIN"]))
):
    """
    Administrator endpoint: Approve or reject an NGO verification application
    after reviewing 80G and legal registration certificates.
    """
    db = get_database()
    admin_uid = current_user.get("firebase_uid", "admin")

    try:
        update_res = await db.ngos.update_one(
            {"_id": ObjectId(ngo_id)},
            {"$set": {
                "verification_status": decision.status,
                "is_verified": decision.status == "VERIFIED",
                "rejection_reason": decision.rejection_reason if decision.status == "REJECTED" else None,
                "reviewed_by": admin_uid,
                "reviewed_at": datetime.now(timezone.utc),
                "reviewer_notes": decision.reviewer_notes
            }}
        )
        if update_res.matched_count == 0:
            raise HTTPException(status_code=404, detail="NGO not found")
            
        # Log to immutable audit log
        from app.models.audit_log import AuditLogModel
        await db.audit_logs.insert_one(AuditLogModel.create_new_log({
            "entity_type": "NGO",
            "entity_id": ngo_id,
            "action": f"NGO_VERIFICATION_{decision.status}",
            "old_status": "PENDING",
            "new_status": decision.status,
            "user_id": admin_uid,
            "reason": decision.rejection_reason or decision.reviewer_notes
        }))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "SUCCESS",
        "ngo_id": ngo_id,
        "verification_status": decision.status,
        "message": f"NGO has been marked as {decision.status}"
    }

@router.post("/{ngo_id}/bulk-claim")
async def bulk_claim_donations(
    ngo_id: str,
    claim: BulkClaimRequest,
    current_user: dict = Depends(require_role(["NGO", "ADMIN"]))
):
    """
    Allows a verified NGO / charity to claim multiple surplus food donations in bulk
    for large community distribution.
    """
    db = get_database()
    ngo = await ngo_service.get_ngo(ngo_id)
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    if not ngo.get("is_verified", False) and current_user.get("role", "").upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified NGOs with validated 80G credentials can claim bulk food donations."
        )

    claimed_count = 0
    for d_id in claim.donation_ids:
        try:
            res = await db.donations.update_one(
                {"_id": ObjectId(d_id), "status": {"$in": ["AVAILABLE", "POSTED", "SUBMITTED"]}},
                {"$set": {
                    "status": "ACCEPTED",
                    "accepted_by": ngo_id,
                    "accepted_at": datetime.now(timezone.utc)
                }}
            )
            if res.modified_count > 0:
                claimed_count += 1
        except Exception:
            continue

    return {
        "status": "SUCCESS",
        "ngo_id": ngo_id,
        "requested_donations_count": len(claim.donation_ids),
        "successfully_claimed_count": claimed_count,
        "beneficiaries_served": claim.intended_beneficiaries
    }
