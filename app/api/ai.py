from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from app.models.nlp import NLPRequest, NLPEmergencyResponse
from app.nlp.factory import ExtractorFactory
from app.ai.chatbot.indic_nlp_engine import indic_nlp_engine
from app.database.mongodb import mongodb

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/nlp/extract", response_model=NLPEmergencyResponse)
async def extract_emergency_info(request: NLPRequest):
    """
    Extract structured data from a natural language emergency request.
    Supports English, Kannada, Hindi, and Code-Mixed text.
    """
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
        
    try:
        extractor = ExtractorFactory.get_extractor("ml")
        extracted_data = extractor.extract(request.text)
        return NLPEmergencyResponse(**extracted_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NLP extraction failed: {str(e)}")

@router.post("/nlp/draft")
async def accumulate_voice_draft(request: NLPRequest):
    """
    Phase 3: Multi-Segment Voice Draft Accumulator.
    Merges partial utterances with natural pauses into a single consistent draft.
    Saves state in MongoDB Atlas 'request_drafts' collection for recovery.
    """
    session_id = request.session_id or f"sess_{uuid.uuid4().hex[:8]}"
    existing_draft = request.existing_draft

    if not existing_draft and session_id:
        # Try fetching from DB if not provided in payload
        db_draft = await mongodb.db.request_drafts.find_one({"session_id": session_id})
        if db_draft:
            existing_draft = db_draft.get("draft")

    merged = indic_nlp_engine.merge_voice_draft(session_id, existing_draft, request.text)

    # Persist in DB for cross-session recovery
    await mongodb.db.request_drafts.update_one(
        {"session_id": session_id},
        {"$set": {
            "session_id": session_id,
            "draft": merged,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    return {
        "session_id": session_id,
        "draft": merged,
        "is_complete": merged.get("is_complete", False),
        "missing_fields": merged.get("missing_fields", [])
    }

@router.get("/nlp/draft/{session_id}")
async def get_voice_draft(session_id: str):
    """
    Recovers an in-progress draft after application restart or network reconnection.
    """
    db_draft = await mongodb.db.request_drafts.find_one({"session_id": session_id})
    if not db_draft:
        raise HTTPException(status_code=404, detail="Draft session not found")
    return db_draft.get("draft")
