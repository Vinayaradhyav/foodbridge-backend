from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentResponse
from app.services import assignment_service
from app.services.workflow_service import WorkflowService
from app.core.security import get_current_user, require_role

router = APIRouter(prefix="/assignments", tags=["Assignments"])

@router.post("", response_model=AssignmentResponse)
async def create_assignment(
    assignment: AssignmentCreate,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Create a new assignment. Only admins can assign tasks for now."""
    return await assignment_service.create_assignment(assignment)

@router.get("/active", response_model=List[AssignmentResponse])
async def get_active_assignments(
    current_user: dict = Depends(require_role(["admin", "ADMIN"]))
):
    """Admin endpoint: Get all currently active deliveries for tracking on the map."""
    return await assignment_service.get_active_assignments()

@router.get("/volunteer/available", response_model=List[AssignmentResponse])
async def get_volunteer_available_assignments(
    current_user: dict = Depends(require_role(["volunteer"]))
):
    """Get pending assignments assigned to the currently authenticated volunteer."""
    return await assignment_service.get_available_assignments(current_user["firebase_uid"])

@router.get("/volunteer/history", response_model=List[AssignmentResponse])
async def get_volunteer_history(
    current_user: dict = Depends(require_role(["volunteer"]))
):
    """Get history of completed or cancelled assignments for this volunteer."""
    return await assignment_service.get_volunteer_history(current_user["firebase_uid"])

@router.post("/{assignment_id}/accept", response_model=AssignmentResponse)
async def accept_assignment(
    assignment_id: str,
    current_user: dict = Depends(require_role(["volunteer"]))
):
    """Volunteer accepts an assignment."""
    return await assignment_service.update_assignment_status(assignment_id, current_user["firebase_uid"], "ACCEPTED")

@router.post("/{assignment_id}/reject", response_model=AssignmentResponse)
async def reject_assignment(
    assignment_id: str,
    current_user: dict = Depends(require_role(["volunteer"]))
):
    """Volunteer rejects an assignment (cancels it from their view)."""
    return await assignment_service.update_assignment_status(assignment_id, current_user["firebase_uid"], "CANCELLED")

@router.put("/{assignment_id}/status", response_model=AssignmentResponse)
async def update_assignment_status(
    assignment_id: str,
    status_update: AssignmentUpdate,
    current_user: dict = Depends(require_role(["volunteer"]))
):
    """Update the status of an assignment (e.g. IN_TRANSIT, DELIVERED)."""
    if not status_update.status:
        raise HTTPException(status_code=400, detail="Status must be provided")
    return await assignment_service.update_assignment_status(assignment_id, current_user["firebase_uid"], status_update.status)

from pydantic import BaseModel
class ProofUpload(BaseModel):
    proof_url: str

class OtpVerificationPayload(BaseModel):
    otp: str
    photo_url: str = "https://storage.foodbridge.org/proof/default_pickup.jpg"

class DeliveryHandoverPayload(BaseModel):
    delivery_otp: str
    proof_url: str = "https://storage.foodbridge.org/proof/default_delivery.jpg"

@router.put("/{assignment_id}/upload-proof", response_model=AssignmentResponse)
async def upload_proof(
    assignment_id: str,
    proof: ProofUpload,
    current_user: dict = Depends(require_role(["volunteer"]))
):
    """Volunteer uploads delivery proof."""
    return await WorkflowService.volunteer_upload_proof(assignment_id, current_user["firebase_uid"], proof.proof_url)

@router.post("/{assignment_id}/verify-pickup-otp", response_model=AssignmentResponse)
async def verify_pickup_otp(
    assignment_id: str,
    payload: OtpVerificationPayload,
    current_user: dict = Depends(require_role(["volunteer", "admin"]))
):
    """
    Secure OTP exchange confirmation at donor pickup.
    Transitions task to PICKED_UP and prevents delivery diversion.
    """
    return await WorkflowService.verify_pickup_otp(
        assignment_id=assignment_id,
        volunteer_id=current_user["firebase_uid"],
        otp=payload.otp,
        photo_url=payload.photo_url
    )

@router.post("/{assignment_id}/verify-delivery-otp", response_model=AssignmentResponse)
async def verify_delivery_otp(
    assignment_id: str,
    payload: DeliveryHandoverPayload,
    current_user: dict = Depends(require_role(["volunteer", "admin"]))
):
    """
    Secure OTP exchange confirmation at receiver shelter handover.
    Transitions task to DELIVERED and checks completion.
    """
    return await WorkflowService.verify_delivery_otp(
        assignment_id=assignment_id,
        volunteer_id=current_user["firebase_uid"],
        otp=payload.delivery_otp,
        proof_url=payload.proof_url
    )
