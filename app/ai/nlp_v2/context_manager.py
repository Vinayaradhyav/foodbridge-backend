"""
FoodBridge NLP V2 — Dialogue Context & Multi-Turn Session Manager
Maintains conversational state, handles coreferences, partial updates,
and quantity adjustments across multi-turn interactions.
"""

import time
import re
from typing import Dict, Any, Optional, List

class ContextSession:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.intent: Optional[str] = None
        self.primary_category: Optional[str] = None
        self.items: List[Dict[str, Any]] = []
        self.total_quantity: float = 0.0
        self.remaining_quantity: float = 0.0
        self.received_quantity: float = 0.0
        self.beneficiaries: Dict[str, Any] = {}
        self.location: Optional[str] = None
        self.dietary_type: Optional[str] = None
        self.priority: Optional[Dict[str, Any]] = None
        self.status: str = "ACTIVE" # ACTIVE, PENDING_INFO, ALLOCATING, COMPLETED, CANCELLED
        self.history: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "intent": self.intent,
            "primary_category": self.primary_category,
            "items": self.items,
            "total_quantity": self.total_quantity,
            "remaining_quantity": self.remaining_quantity,
            "received_quantity": self.received_quantity,
            "beneficiaries": self.beneficiaries,
            "location": self.location,
            "dietary_type": self.dietary_type,
            "priority": self.priority,
            "status": self.status,
            "turns_count": len(self.history)
        }


class ContextManager:
    """Manages active conversational sessions and performs contextual resolution."""

    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: Dict[str, ContextSession] = {}
        self.ttl_seconds = ttl_seconds

    def get_or_create_session(self, session_id: str) -> ContextSession:
        self._cleanup_expired()
        if session_id not in self._sessions:
            self._sessions[session_id] = ContextSession(session_id)
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[ContextSession]:
        self._cleanup_expired()
        return self._sessions.get(session_id)

    def resolve_context(
        self,
        session_id: Optional[str],
        current_intent: str,
        current_entities: Dict[str, Any],
        raw_text: str
    ) -> Dict[str, Any]:
        """
        Resolves the current utterance against prior session memory.
        Updates running balances (e.g. 'Received 50' or 'Change location to X').
        """
        if not session_id:
            # Standalone stateless analysis
            return {
                "session_id": None,
                "is_continuation": False,
                "resolved_entities": current_entities,
                "context_notes": []
            }

        session = self.get_or_create_session(session_id)
        session.updated_at = time.time()
        lowered = raw_text.lower()
        notes: List[str] = []

        is_continuation = len(session.history) > 0

        # 1. Check for Cancellation Intent
        if current_intent == "DONATION_CANCELLATION" or "cancel" in lowered:
            session.status = "CANCELLED"
            session.history.append({
                "timestamp": time.time(),
                "text": raw_text,
                "action": "CANCEL_SESSION"
            })
            notes.append("Request cancelled by user in conversation.")
            return {
                "session_id": session_id,
                "is_continuation": True,
                "resolved_entities": session.to_dict(),
                "status": "CANCELLED",
                "context_notes": notes
            }

        # 2. Check for Quantity Received / Deductions (e.g. 'Received 50', 'got 30 packets')
        received_match = re.search(r"\b(?:received|got|obtained|delivered|distributed)\s*(\d+)", lowered)
        if received_match and session.total_quantity > 0:
            rec_val = float(received_match.group(1))
            session.received_quantity += rec_val
            session.remaining_quantity = max(0.0, session.remaining_quantity - rec_val)
            notes.append(f"Recorded receipt of {rec_val}. Remaining requirement updated to {session.remaining_quantity}.")

        # 3. Check for Quantity Adjustment (e.g. 'Another 100 will be enough', 'Need 100 more', 'Changed to 300')
        adj_match = re.search(r"\b(?:another|need|make it|changed to|adjust to)\s*(\d+)\s*(?:more|enough)?", lowered)
        if adj_match and is_continuation and not current_entities.get("items"):
            new_val = float(adj_match.group(1))
            if "more" in lowered or "another" in lowered:
                session.remaining_quantity = new_val
                notes.append(f"Remaining requirement adjusted to {new_val}.")
            else:
                session.total_quantity = new_val
                session.remaining_quantity = max(0.0, new_val - session.received_quantity)
                notes.append(f"Total quantity updated to {new_val}. Remaining: {session.remaining_quantity}.")

        # 4. Integrate new items if present
        if current_entities.get("items"):
            if not session.items:
                session.items = current_entities["items"]
                session.total_quantity = current_entities["total_quantity"]
                session.remaining_quantity = current_entities["total_quantity"]
            else:
                # Append or update items
                session.items.extend(current_entities["items"])
                session.total_quantity += current_entities["total_quantity"]
                session.remaining_quantity += current_entities["total_quantity"]
                notes.append("Appended additional items to active session.")

        # 5. Inherit or Update Location
        if current_entities.get("location"):
            session.location = current_entities["location"]
            notes.append(f"Location set to {session.location}.")
        elif not session.location and is_continuation:
            pass  # keep existing if any

        # 6. Inherit or Update Intent
        if not session.intent or (current_intent not in ["UNKNOWN_OR_UNSUPPORTED", "DONATION_UPDATE", "DONATION_CORRECTION"]):
            session.intent = current_intent

        # 7. Inherit or Update Dietary
        if current_entities.get("dietary_type"):
            session.dietary_type = current_entities["dietary_type"]

        # Record turn in history
        session.history.append({
            "timestamp": time.time(),
            "text": raw_text,
            "intent": current_intent,
            "extracted_items_count": len(current_entities.get("items", []))
        })

        return {
            "session_id": session_id,
            "is_continuation": is_continuation,
            "resolved_entities": session.to_dict(),
            "status": session.status,
            "context_notes": notes
        }

    def _cleanup_expired(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.updated_at > self.ttl_seconds]
        for sid in expired:
            del self._sessions[sid]


context_manager = ContextManager()
