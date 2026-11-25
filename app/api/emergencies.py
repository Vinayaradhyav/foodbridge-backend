from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import base64
import os
import uuid

from app.models.emergency import EmergencyRequestCreate, EmergencyRequestResponse, EmergencyRequestUpdate
from app.services.emergency_service import EmergencyService
from app.core.security import get_current_user, get_optional_current_user
from app.ai.chatbot.indic_nlp_engine import indic_nlp_engine
from app.ai.nlp_v2.pipeline import nlp_donation_pipeline

router = APIRouter(prefix="/emergencies", tags=["Emergencies"])

class VoiceProcessRequest(BaseModel):
    transcript: str
    original_language: Optional[str] = "en"
    target_language: Optional[str] = "en"
    session_id: Optional[str] = None
    audio_id: Optional[str] = None
    audio_url: Optional[str] = None
    audio_duration_seconds: Optional[int] = 0

class VoiceTranslateRequest(BaseModel):
    text: str
    source_language: Optional[str] = "auto"
    target_language: str = "en"

@router.post("/process-voice")
async def process_voice_emergency(
    payload: VoiceProcessRequest,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """
    Processes a completed multi-segment voice SOS transcript without creating or broadcasting an active SOS.
    Returns normalized transcript, multilingual translation, disambiguated entities, and missing fields.
    Saves a 'draft' state in MongoDB for review & confirmation.
    """
    transcript = (payload.transcript or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Voice transcript cannot be empty.")

    # Extract disambiguated entities from complete accumulated transcript
    indic_data = indic_nlp_engine.extract_entities(transcript)
    nlp_v2 = nlp_donation_pipeline.analyze(text=transcript, session_id=payload.session_id)

    src_lang = payload.original_language or indic_data.get("original_language") or "en"
    tgt_lang = payload.target_language or "en"

    # Translate full transcript to requested target language (preserving original transcript)
    tr_res = await indic_nlp_engine.translate_text_async(transcript, source_lang=src_lang, target_lang=tgt_lang)
    translated_text = tr_res.get("translated_text") or indic_data.get("english_translation") or transcript
    translation_status = tr_res.get("translation_status", "completed")

    # If original wasn't English and target wasn't English, also get English normalized text for NLP audit
    english_text = indic_data.get("english_translation") or transcript
    if src_lang not in ("en",) and tgt_lang == "en" and translation_status == "completed":
        english_text = translated_text
        # Re-run extraction on clean English translation as secondary boost for missing fields
        if indic_data.get("missing_fields"):
            boosted = indic_nlp_engine.extract_entities(english_text)
            for k in ["quantity", "food_quantity", "number_of_people", "beneficiaries", "delivery_location", "location", "water_quantity", "delivery_time"]:
                if indic_data.get(k) is None and boosted.get(k) is not None:
                    indic_data[k] = boosted[k]
            if not indic_data.get("packaging_required") and boosted.get("packaging_required"):
                indic_data["packaging_required"] = True
            if not indic_data.get("water_required") and boosted.get("water_required"):
                indic_data["water_required"] = True

    missing = []
    if indic_data.get("quantity") is None and indic_data.get("water_quantity") is None:
        missing.append("quantity")
    if indic_data.get("number_of_people") is None:
        missing.append("number_of_people")
    if not indic_data.get("delivery_location"):
        missing.append("delivery_location")

    session_id = payload.session_id or f"sos_draft_{uuid.uuid4().hex[:10]}"
    response_payload = {
        "session_id": session_id,
        "status": "draft",
        "original_language": src_lang,
        "target_language": tgt_lang,
        "original_transcript": transcript,
        "normalized_transcript": indic_data.get("normalized_transcript", transcript),
        "translated_transcript": translated_text,
        "english_translation": english_text,
        "translation_status": translation_status,
        "food_category": indic_data.get("food_category", "Cooked Meals"),
        "food_name": indic_data.get("food_name", "Cooked Meals"),
        "food_type": indic_data.get("food_type", "cooked_meals"),
        "quantity": indic_data.get("quantity"),
        "food_quantity": indic_data.get("food_quantity"),
        "quantity_unit": indic_data.get("quantity_unit", "meals"),
        "number_of_people": indic_data.get("number_of_people"),
        "beneficiaries": indic_data.get("beneficiaries"),
        "location": indic_data.get("delivery_location"),
        "delivery_location": indic_data.get("delivery_location"),
        "delivery_coordinates": indic_data.get("delivery_coordinates"),
        "urgency": indic_data.get("urgency", "high"),
        "urgency_level": indic_data.get("urgency_level", "HIGH"),
        "packaging_required": indic_data.get("packaging_required", False),
        "water_required": indic_data.get("water_required", False),
        "water_quantity": indic_data.get("water_quantity"),
        "delivery_time": indic_data.get("delivery_time"),
        "storage_requirements": indic_data.get("storage_requirements"),
        "additional_requirements": indic_data.get("additional_requirements"),
        "audio_id": payload.audio_id,
        "audio_url": payload.audio_url,
        "audio_duration_seconds": payload.audio_duration_seconds or 0,
        "missing_fields": missing,
        "is_complete": len(missing) == 0,
        "confidence": indic_data.get("confidence", nlp_v2.get("confidence", 0.92)),
    }

    try:
        from app.database.mongodb import mongodb
        if mongodb.db is not None:
            owner_id = str((current_user or {}).get("firebase_uid") or (current_user or {}).get("id") or "anonymous")
            await mongodb.db.emergency_voice_drafts.update_one(
                {"session_id": session_id},
                {"$set": {
                    **response_payload,
                    "owner_id": owner_id,
                    "updated_at": datetime.now(timezone.utc),
                }},
                upsert=True
            )
    except Exception:
        pass

    return response_payload

@router.post("/translate")
async def translate_voice_transcript(payload: VoiceTranslateRequest):
    """Translate full SOS transcript between English, Kannada, Hindi, etc."""
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    res = await indic_nlp_engine.translate_text_async(
        payload.text,
        source_lang=payload.source_language or "auto",
        target_lang=payload.target_language or "en"
    )
    return {
        "original_text": payload.text,
        "source_language": payload.source_language,
        "target_language": payload.target_language,
        **res
    }

@router.post("/upload-voice-audio")
async def upload_voice_audio(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    duration_seconds: int = Form(0),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """
    Securely stores recorded SOS voice audio (.m4a/.aac/.wav) and returns an authenticated reference ID.
    Keeps audio binary isolated from ordinary emergency documents inside 'emergency_audio_files'.
    """
    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
    if len(raw_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds 15MB limit.")

    audio_id = f"aud_{uuid.uuid4().hex[:12]}"
    ext = os.path.splitext(audio.filename or "sos_voice.m4a")[1] or ".m4a"
    audio_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "emergency_audio")
    os.makedirs(audio_dir, exist_ok=True)
    disk_path = os.path.join(audio_dir, f"{audio_id}{ext}")
    with open(disk_path, "wb") as f:
        f.write(raw_bytes)

    owner_id = str((current_user or {}).get("firebase_uid") or (current_user or {}).get("id") or "anonymous")
    mime_type = audio.content_type or "audio/mp4"

    from app.database.mongodb import mongodb
    if mongodb.db is not None:
        await mongodb.db.emergency_audio_files.insert_one({
            "audio_id": audio_id,
            "session_id": session_id,
            "owner_id": owner_id,
            "filename": f"{audio_id}{ext}",
            "mime_type": mime_type,
            "duration_seconds": duration_seconds,
            "file_size": len(raw_bytes),
            "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
            "created_at": datetime.now(timezone.utc),
        })

    return {
        "audio_id": audio_id,
        "audio_url": f"/api/emergencies/audio/{audio_id}",
        "duration_seconds": duration_seconds,
        "file_size": len(raw_bytes),
        "mime_type": mime_type
    }

@router.get("/audio/{audio_id}")
async def get_voice_audio(
    audio_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Authenticated audio retrieval endpoint. Only authorized users can stream SOS audio.
    """
    from app.database.mongodb import mongodb
    doc = await mongodb.db.emergency_audio_files.find_one({"audio_id": audio_id}) if mongodb.db is not None else None
    if not doc:
        raise HTTPException(status_code=404, detail="Audio recording not found.")

    role = str(current_user.get("role", "")).lower()
    caller_id = str(current_user.get("firebase_uid") or current_user.get("id") or "")
    owner_id = str(doc.get("owner_id") or "")
    if role != "admin" and owner_id != "anonymous" and caller_id != owner_id and role not in ("donor", "volunteer", "food_receiver", "ngo", "relief_hub"):
        raise HTTPException(status_code=403, detail="Not authorized to access this recording.")

    audio_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "emergency_audio")
    disk_path = os.path.join(audio_dir, doc.get("filename", f"{audio_id}.m4a"))
    if os.path.exists(disk_path):
        with open(disk_path, "rb") as f:
            data = f.read()
    elif doc.get("content_base64"):
        data = base64.b64decode(doc["content_base64"])
    else:
        raise HTTPException(status_code=404, detail="Audio bytes unavailable.")

    return Response(content=data, media_type=doc.get("mime_type", "audio/mp4"))

class EmergencyPledgeRequest(BaseModel):
    contributor_name: Optional[str] = "Verified Donor"
    contributor_id: Optional[str] = None
    contributor_phone: Optional[str] = None
    contributed_meals: Optional[int] = None
    assigned_volunteer_id: Optional[str] = None
    handover_otp: Optional[str] = None

class EmergencyCancelPledgeRequest(BaseModel):
    donor_id: str
    reason: str

class EmergencyCompleteRequest(BaseModel):
    otp: Optional[str] = "7392"
    notes: Optional[str] = "Emergency delivery completed and verified by receiver."

@router.post("/", response_model=EmergencyRequestResponse, status_code=201)
async def create_emergency(request: EmergencyRequestCreate):
    """
    Create a new emergency request with dual location coordinates and calculated priority score.
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

@router.put("/{request_id}/pledge", response_model=EmergencyRequestResponse)
async def pledge_emergency(request_id: str, pledge: EmergencyPledgeRequest):
    """
    Phase 7: Atomic Donor Pledge & Reservation.
    Atomically locks the emergency request for the donor using MongoDB conditional update.
    Returns HTTP 409 if already claimed by another donor.
    """
    donor_id = pledge.contributor_id or "donor_live"
    donor_name = pledge.contributor_name or "Verified Donor"
    return await EmergencyService.pledge_emergency(
        request_id=request_id,
        donor_id=donor_id,
        donor_name=donor_name,
        donor_phone=pledge.contributor_phone,
        contributed_meals=pledge.contributed_meals,
        assigned_volunteer_id=pledge.assigned_volunteer_id,
        handover_otp=pledge.handover_otp
    )

@router.put("/{request_id}/cancel-pledge", response_model=EmergencyRequestResponse)
async def cancel_emergency_pledge(request_id: str, cancel_data: EmergencyCancelPledgeRequest):
    """
    Phase 8: Donor Cancellation & Automatic Reassignment.
    Releases assignment, returns status to AVAILABLE/OPEN, logs reason, and broadcasts to other donors.
    """
    return await EmergencyService.cancel_pledge(
        request_id=request_id,
        donor_id=cancel_data.donor_id,
        reason=cancel_data.reason
    )

@router.put("/{request_id}/complete", response_model=EmergencyRequestResponse)
async def complete_emergency(request_id: str, comp: Optional[EmergencyCompleteRequest] = None):
    """
    Confirm delivery handover and mark emergency request as FULFILLED/COMPLETED.
    """
    e = await EmergencyService.get_emergency_by_id(request_id)
    qty = e.quantity if e else 400
    update_data = EmergencyRequestUpdate(
        status="FULFILLED",
        fulfilled_quantity=qty
    )
    updated = await EmergencyService.update_emergency(request_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Emergency request not found")
        
    try:
        from datetime import datetime, timezone
        from app.database.mongodb import mongodb
        now = datetime.now(timezone.utc)
        await mongodb.db.donations.update_many(
            {"$or": [{"emergency_id": request_id}, {"donation_id": f"DON-SOS-{request_id[-6:]}"}]},
            {"$set": {"status": "DELIVERED", "updated_at": now}}
        )
        await mongodb.db.assignments.update_many(
            {"$or": [{"emergency_id": request_id}, {"donation_id": f"DON-SOS-{request_id[-6:]}"}]},
            {"$set": {"status": "DELIVERED", "updated_at": now}}
        )
    except Exception:
        pass
        
    return updated

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
