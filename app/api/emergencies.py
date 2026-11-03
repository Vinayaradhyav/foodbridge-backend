from fastapi import APIRouter, HTTPException
from typing import List

from app.models.emergency import EmergencyRequestCreate, EmergencyRequestResponse, EmergencyRequestUpdate
from app.services.emergency_service import EmergencyService

router = APIRouter(prefix="/emergencies", tags=["Emergencies"])

@router.post("/", response_model=EmergencyRequestResponse, status_code=201)
async def create_emergency(request: EmergencyRequestCreate):
    """
    Create a new emergency request. Calculates priority score automatically.
    """
    try:
        return await EmergencyService.create_emergency(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[EmergencyRequestResponse])
async def list_active_emergencies():
    """
    List all active emergency requests, sorted by priority score (highest first).
    """
    return await EmergencyService.get_active_emergencies()

@router.get("/{request_id}", response_model=EmergencyRequestResponse)
async def get_emergency(request_id: str):
    """
    Get details of a specific emergency request.
    """
    emergency = await EmergencyService.get_emergency_by_id(request_id)
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    return emergency

@router.put("/{request_id}", response_model=EmergencyRequestResponse)
async def update_emergency(request_id: str, update_data: EmergencyRequestUpdate):
    """
    Update an emergency request (e.g., status or fulfilled quantity).
    """
    updated = await EmergencyService.update_emergency(request_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    return updated

@router.put("/{request_id}/reject")
async def reject_emergency(request_id: str, reason: str = "Rejected by administrator"):
    """
    Reject an emergency request.
    """
    success = await EmergencyService.reject_emergency(request_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    return {"status": "success", "message": f"Emergency request {request_id} rejected"}

@router.delete("/{request_id}")
async def delete_emergency(request_id: str):
    """
    Permanently delete an emergency request.
    """
    deleted = await EmergencyService.delete_emergency(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    return {"status": "success", "message": f"Emergency request {request_id} deleted"}
