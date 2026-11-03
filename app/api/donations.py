from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.schemas.donation import DonationCreate, DonationUpdate, DonationResponse
from app.services import donation_service
from app.services.workflow_service import WorkflowService
from app.core.security import get_current_user, require_role

router = APIRouter(prefix="/donations", tags=["Donations"])

@router.post("", response_model=DonationResponse)
async def create_donation(
    donation: DonationCreate,
    current_user: dict = Depends(require_role(["donor", "admin"]))
):
    """Create a new donation. Only donors can create donations."""
    return await donation_service.create_donation(current_user["firebase_uid"], donation)

@router.get("", response_model=List[DonationResponse])
async def get_all_donations(
    status: Optional[str] = None,
    donor_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """Get all public donations (Available to anyone, even unauthenticated)."""
    return await donation_service.get_donations(status=status, donor_id=donor_id, skip=skip, limit=limit)

@router.get("/me", response_model=List[DonationResponse])
async def get_my_donations(current_user: dict = Depends(require_role(["donor", "admin"]))):
    """Get all donations created by the currently authenticated donor."""
    return await donation_service.get_donations_by_donor(current_user["firebase_uid"])

RECEIVER_ROLES = ["ngo", "food_receiver", "receiver", "relief_hub", "admin"]

@router.get("/ngo/available", response_model=List[DonationResponse])
async def get_ngo_available_donations(
    skip: int = 0, limit: int = 100,
    current_user: dict = Depends(require_role(RECEIVER_ROLES))
):
    """Get available donations for an NGO/Receiver (excluding those they rejected)."""
    return await donation_service.get_available_for_ngo(current_user["firebase_uid"], skip=skip, limit=limit)

@router.get("/ngo/history", response_model=List[DonationResponse])
async def get_ngo_donation_history(
    skip: int = 0, limit: int = 100,
    current_user: dict = Depends(require_role(RECEIVER_ROLES))
):
    """Get history of donations accepted by this NGO/Receiver."""
    return await donation_service.get_ngo_history(current_user["firebase_uid"], skip=skip, limit=limit)

@router.get("/{donation_id}", response_model=DonationResponse)
async def get_donation(donation_id: str):
    """Get a specific donation by ID."""
    donation = await donation_service.get_donation_by_id(donation_id)
    if not donation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donation not found")
    return donation

@router.post("/{donation_id}/accept", response_model=DonationResponse)
async def accept_donation(
    donation_id: str,
    current_user: dict = Depends(require_role(RECEIVER_ROLES))
):
    """Accept a donation as an NGO or verified Relief Hub / Receiver."""
    return await donation_service.accept_donation(donation_id, current_user["firebase_uid"])

@router.put("/{donation_id}/reject", response_model=DonationResponse)
async def reject_donation(
    donation_id: str,
    current_user: dict = Depends(require_role(RECEIVER_ROLES))
):
    """Reject an available donation."""
    return await donation_service.reject_donation(donation_id, current_user["firebase_uid"])

@router.put("/{donation_id}/confirm-receipt", response_model=DonationResponse)
async def confirm_receipt(
    donation_id: str,
    current_user: dict = Depends(require_role(RECEIVER_ROLES))
):
    """NGO/Receiver confirms receipt of a donation delivery."""
    return await WorkflowService.ngo_confirm_receipt(donation_id, current_user["firebase_uid"])

from pydantic import BaseModel

class HandoverCompletionPayload(BaseModel):
    otp: str
    proof_image: Optional[str] = None
    signature_base64: Optional[str] = None
    signer_name: Optional[str] = None
    quantity_confirmed: Optional[bool] = True
    condition_good: Optional[bool] = True

class OtpVerificationPayload(BaseModel):
    otp: str

@router.post("/{donation_id}/verify-pickup-otp")
async def verify_donor_pickup_otp(
    donation_id: str,
    payload: OtpVerificationPayload,
    current_user: dict = Depends(require_role(["volunteer", "admin"]))
):
    """
    Validates the Donor's 4-digit Pickup OTP when the volunteer arrives at pickup.
    Transitions donation to PICKED_UP / IN_TRANSIT.
    """
    doc = await donation_service.get_donation_by_id(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
        
    stored_otp = str(doc.get("pickup_otp", "")).strip()
    provided_otp = str(payload.otp).strip()
    if stored_otp and provided_otp != stored_otp:
        raise HTTPException(status_code=400, detail="Invalid Donor Pickup OTP. Please check with donor.")
        
    from app.database.mongodb import mongodb
    from datetime import datetime, timezone
    from bson import ObjectId
    now = datetime.now(timezone.utc)
    try:
        f = {"_id": ObjectId(doc["id"])}
    except Exception:
        f = {"$or": [{"donation_id": donation_id}, {"id": donation_id}]}
    await mongodb.db.donations.update_one(f, {"$set": {"status": "IN_TRANSIT", "picked_up_at": now, "updated_at": now}})
    return {
        "message": "Pickup OTP verified successfully. Food donation is now IN_TRANSIT.",
        "status": "IN_TRANSIT",
        "food_order_id": doc.get("food_order_id") or doc.get("donation_id")
    }

@router.post("/{donation_id}/verify-delivery-otp")
async def verify_receiver_delivery_otp(
    donation_id: str,
    payload: OtpVerificationPayload,
    current_user: dict = Depends(require_role(["volunteer", "admin", "ngo", "food_receiver", "receiver"]))
):
    """
    Validates the Receiver's 4-digit Delivery OTP when the volunteer hands over food.
    Transitions donation to COMPLETED.
    """
    doc = await donation_service.get_donation_by_id(donation_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Donation not found")
        
    stored_otp = str(doc.get("delivery_otp") or doc.get("handover_otp") or "").strip()
    provided_otp = str(payload.otp).strip()
    if stored_otp and provided_otp != stored_otp:
        raise HTTPException(status_code=400, detail="Invalid Receiver Delivery OTP. Please verify with receiver.")
        
    from app.database.mongodb import mongodb
    from datetime import datetime, timezone
    from bson import ObjectId
    now = datetime.now(timezone.utc)
    try:
        f = {"_id": ObjectId(doc["id"])}
    except Exception:
        f = {"$or": [{"donation_id": donation_id}, {"id": donation_id}]}
    await mongodb.db.donations.update_one(f, {"$set": {"status": "COMPLETED", "completed_at": now, "updated_at": now}})
    return {
        "message": "Delivery OTP verified successfully! Food donation completed.",
        "status": "COMPLETED",
        "food_order_id": doc.get("food_order_id") or doc.get("donation_id")
    }

@router.post("/{donation_id}/complete-handover")
async def complete_handover(
    donation_id: str,
    payload: HandoverCompletionPayload,
    current_user: dict = Depends(require_role(["volunteer", "ngo", "food_receiver", "receiver", "relief_hub", "admin"]))
):
    """
    Direct authoritative completion of a donation handover.
    Validates the 4-digit OTP, updates MongoDB with photo proof and signature,
    sets status to COMPLETED, and stores evidence in MongoDB.
    """
    return await WorkflowService.complete_donation_handover(
        donation_id=donation_id,
        user_id=current_user["firebase_uid"],
        otp=payload.otp,
        proof_image=payload.proof_image,
        signature_base64=payload.signature_base64,
        signer_name=payload.signer_name,
        quantity_confirmed=payload.quantity_confirmed if payload.quantity_confirmed is not None else True,
        condition_good=payload.condition_good if payload.condition_good is not None else True
    )

@router.put("/{donation_id}", response_model=DonationResponse)
async def update_donation(
    donation_id: str,
    donation_update: DonationUpdate,
    current_user: dict = Depends(require_role(["donor", "admin"]))
):
    """Update a donation. Enforces that only the owner can modify it."""
    return await donation_service.update_donation(
        donation_id=donation_id,
        donor_id=current_user["firebase_uid"],
        update_data=donation_update
    )

@router.delete("/{donation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_donation(
    donation_id: str,
    current_user: dict = Depends(require_role(["donor", "admin"]))
):
    """Delete a donation. Enforces that only the owner can delete it."""
    await donation_service.delete_donation(
        donation_id=donation_id,
        donor_id=current_user["firebase_uid"]
    )
    return None
