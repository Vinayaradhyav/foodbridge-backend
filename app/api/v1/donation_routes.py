from fastapi import APIRouter, Depends, HTTPException
from app.services.donation_service import donation_service
from app.api.v1.auth_routes import get_current_user

router = APIRouter(prefix="/donations", tags=["donations"])

@router.post("/")
async def create_donation(donation_data: dict, current_user: dict = Depends(get_current_user)):
    """Creates a new donation (defaults to NEW_DONATION status)."""
    donation_id = await donation_service.create_donation(donation_data)
    if not donation_id:
        raise HTTPException(status_code=500, detail="Failed to create donation")
    return {"id": donation_id, "message": "Donation created successfully"}

@router.get("/active")
async def get_active_donations(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Fetches all active donations for matching and logistics."""
    donations = await donation_service.get_active_donations(limit=limit)
    return donations

@router.put("/{donation_id}/status")
async def update_status(donation_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    """Updates the state machine status of a donation."""
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")
        
    success = await donation_service.update_donation_status(donation_id, new_status)
    if not success:
        raise HTTPException(status_code=404, detail="Donation not found or failed to update")
    return {"message": f"Donation status updated to {new_status}"}
