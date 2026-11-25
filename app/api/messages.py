from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict, Any, Set
from app.core.security import get_current_user, get_optional_current_user
from app.schemas.message import MessageCreate, MessageResponse, ConversationResponse, MarkReadRequest, ReportMessageRequest
from app.services.message_service import MessageService

router = APIRouter(prefix="/messages", tags=["Messages"])

class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        key = client_id.strip().lower()
        if key not in self.active_connections:
            self.active_connections[key] = set()
        self.active_connections[key].add(websocket)

    def disconnect(self, websocket: WebSocket, client_id: str):
        key = client_id.strip().lower()
        if key in self.active_connections:
            self.active_connections[key].discard(websocket)
            if not self.active_connections[key]:
                del self.active_connections[key]

    async def broadcast_message(self, message: dict, sender_id: str, recipient_id: str):
        target_keys = {
            sender_id.strip().lower(),
            recipient_id.strip().lower(),
            "admin",
            "admin_broadcast"
        }
        for k in target_keys:
            if k in self.active_connections:
                stale = []
                for ws in self.active_connections[k]:
                    try:
                        await ws.send_json(message)
                    except Exception:
                        stale.append(ws)
                for s in stale:
                    self.active_connections[k].discard(s)

ws_manager = WebSocketConnectionManager()

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
    # Broadcast in real-time to active WebSocket clients
    try:
        await ws_manager.broadcast_message(msg, sender_id, payload.recipient_id)
    except Exception:
        pass
    return msg

@router.websocket("/ws/{client_id}")
async def websocket_messaging_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            if isinstance(data, dict) and "text" in data and "recipient_id" in data:
                payload = MessageCreate(
                    recipient_id=data["recipient_id"],
                    text=data["text"],
                    sender_id=client_id,
                    sender_name=data.get("sender_name", client_id),
                    recipient_name=data.get("recipient_name"),
                    context_type=data.get("context_type", "GENERAL"),
                    context_id=data.get("context_id"),
                    conversation_id=data.get("conversation_id"),
                )
                msg = await MessageService.send_message(
                    sender_id=client_id,
                    sender_name=data.get("sender_name", client_id),
                    payload=payload
                )
                await ws_manager.broadcast_message(msg, client_id, data["recipient_id"])
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)
    except Exception:
        ws_manager.disconnect(websocket, client_id)

@router.get("/history")
async def get_message_history(
    other_user_id: str = Query(..., description="ID or role of other party (e.g. admin, donor_user)"),
    user_id: Optional[str] = Query(None, description="Current user ID (defaults to sender or donor_user)"),
    context_id: Optional[str] = Query(None, description="Optional donation or emergency ID to scope private thread"),
    limit: int = Query(50, ge=1, le=500),
    current_user: Optional[dict] = Depends(get_optional_current_user)
) -> List[Dict[str, Any]]:
    uid = user_id or extract_uid(current_user, fallback="donor_user")
    return await MessageService.get_history(user_a=uid, user_b=other_user_id, limit=limit, context_id=context_id)

@router.get("/donation/{donation_id}")
async def get_donation_private_messages(
    donation_id: str,
    user_id: Optional[str] = Query(None),
    other_user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: Optional[dict] = Depends(get_optional_current_user)
) -> List[Dict[str, Any]]:
    """Fetch private 1-on-1 messages scoped specifically to a single donation."""
    uid = user_id or extract_uid(current_user, fallback="donor_user")
    return await MessageService.get_donation_messages(donation_id=donation_id, current_user_id=uid, other_user_id=other_user_id, limit=limit)

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
