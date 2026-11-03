from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional, Dict, Any
from app.core.security import get_current_user, get_optional_current_user
from app.schemas.message import MessageCreate, MessageResponse, ConversationResponse, MarkReadRequest, ReportMessageRequest
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["Messages"])

def extract_uid(current_user: Optional[dict], fallback: str = "donor_user") -> str:
    if not current_user:
        return fallback
    return str(current_user.get("firebase_uid") or current_user.get("id") or current_user.get("email") or fallback)

def extract_name(current_user: Optional[dict], fallback: str = "User") -> str:
    if not current_user:
        return fallback
    return str(current_user.get("name") or current_user.get("email") or fallback)

@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: MessageCreate,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    sender_id = payload.sender_id or extract_uid(current_user, fallback="donor_user")
    sender_name = payload.sender_name or extract_name(current_user, fallback="Food Donor")
    
    msg = await MessageService.send_message(
        sender_id=sender_id,
        sender_name=sender_name,
        payload=payload
    )
    return msg

@router.get("/history")
async def get_message_history(
    other_user_id: str = Query(..., description="ID or role of other party (e.g. admin, donor_user)"),
    user_id: Optional[str] = Query(None, description="Current user ID (defaults to sender or donor_user)"),
    limit: int = Query(50, ge=1, le=500),
    current_user: Optional[dict] = Depends(get_optional_current_user)
) -> List[Dict[str, Any]]:
    uid = user_id or extract_uid(current_user, fallback="donor_user")
    return await MessageService.get_history(user_a=uid, user_b=other_user_id, limit=limit)

@router.get("/sync")
async def sync_all_messages(
    limit: int = Query(100, ge=1, le=500)
) -> List[Dict[str, Any]]:
    return await MessageService.get_all_recent(limit=limit)

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    user_id = extract_uid(current_user, fallback="admin")
    is_admin = current_user and str(current_user.get("role", "")).upper() == "ADMIN"
    return await MessageService.get_conversations(user_id=user_id, is_admin=bool(is_admin or user_id == "admin"))

@router.get("/conversation/{conversation_id}", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    user_id = extract_uid(current_user, fallback="admin")
    is_admin = current_user and str(current_user.get("role", "")).upper() == "ADMIN"
    return await MessageService.get_messages(
        conversation_id=conversation_id,
        current_user_id=user_id,
        is_admin=bool(is_admin or user_id == "admin"),
        limit=limit
    )

@router.post("/mark-read")
@router.post("/read")
async def mark_conversation_read(
    payload: MarkReadRequest,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    if not payload.conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")
        
    user_id = extract_uid(current_user, fallback="admin")
    modified = await MessageService.mark_read(payload.conversation_id, user_id)
    return {"status": "success", "modified_count": modified}

@router.post("/report")
async def report_message(
    payload: ReportMessageRequest,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    user_id = extract_uid(current_user, fallback="user")
    report = await MessageService.report_message(
        reporter_id=user_id,
        message_id=payload.message_id,
        reason=payload.reason,
        details=payload.details
    )
    return {"status": "reported", "report_id": report["report_id"]}
