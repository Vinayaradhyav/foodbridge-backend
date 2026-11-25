from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from app.models.emergency import Urgency, EmergencyType
from app.ai.nlp_v2.pipeline import nlp_donation_pipeline
from app.ai.chatbot.indic_nlp_engine import indic_nlp_engine
from app.services.emergency_service import EmergencyService

router = APIRouter(prefix="/ai-emergency", tags=["AI Emergency"])

class AIParsingRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    existing_draft: Optional[Dict[str, Any]] = None

class AIParsingResponse(BaseModel):
    parsed_data: Dict[str, Any]
    priority: Dict[str, Any]
    is_complete: bool
    missing_fields: list

@router.post("/parse", response_model=AIParsingResponse)
@router.post("/", response_model=AIParsingResponse)
async def parse_emergency_message(request: AIParsingRequest):
    """
    Parses natural language emergency input using FoodBridge NLP V2.
    Does NOT auto-submit to database. Returns structured preview for user verification.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Run NLP V2 pipeline
    analysis = nlp_donation_pipeline.analyze(
        text=request.message,
        session_id=request.session_id
    )

    entities = analysis.get("entities", {})
    completeness = analysis.get("completeness", {})
    priority_v2 = analysis.get("priority", {})

    # Run Indic NLP Engine for high-precision 12-factor extraction
    indic_data = indic_nlp_engine.extract_entities(request.message)

    # Map entities to expected emergency fields
    items = entities.get("items", [])
    primary_food = indic_data.get("food_type") or entities.get("primary_item_name", "Prepared Meals")
    total_quantity = indic_data.get("food_quantity") or entities.get("total_quantity", 0)
    beneficiary_count = indic_data.get("beneficiaries") or entities.get("beneficiary_count") or (total_quantity if total_quantity > 0 else 50)
    location = indic_data.get("delivery_location") or entities.get("location") or "Mysuru"
    urgency_val = indic_data.get("urgency_level") or priority_v2.get("priority_level", "HIGH")

    parsed_data = {
        "food_type": primary_food,
        "quantity": total_quantity,
        "food_quantity": total_quantity,
        "unit": indic_data.get("quantity_unit") or (items[0].get("unit", "meals") if items else "meals"),
        "number_of_people": beneficiary_count,
        "beneficiaries": beneficiary_count,
        "location": location,
        "cooking_required": indic_data.get("cooking_required", True),
        "packaging_required": indic_data.get("packaging_required", False),
        "water_quantity": indic_data.get("water_quantity"),
        "delivery_time": indic_data.get("delivery_time"),
        "urgency": urgency_val.lower(),
        "urgency_level": urgency_val.upper(),
        "storage_requirements": indic_data.get("storage_requirements"),
        "additional_instructions": indic_data.get("additional_instructions"),
        "dietary_type": entities.get("dietary_type", "Vegetarian"),
        "raw_text": request.message,
        "items": items,
        "intent": analysis.get("intent"),
        "confidence": analysis.get("confidence"),
        "clarification_question": completeness.get("clarification_question")
    }

    # Map priority response
    priority_level = urgency_val.upper()
    urgency_enum = Urgency.CRITICAL if priority_level == "CRITICAL" else (Urgency.HIGH if priority_level == "HIGH" else Urgency.MEDIUM)
    deadline = datetime.now(timezone.utc) + timedelta(hours=3 if priority_level == "CRITICAL" else 12)

    priority_data = {
        "score": priority_v2.get("score", 65),
        "urgency": priority_level,
        "deadline": deadline.isoformat(),
        "reasons": priority_v2.get("reasons", []),
        "evidence_breakdown": priority_v2.get("evidence_breakdown", {}),
        "human_verification_required": priority_v2.get("human_verification_required", True)
    }

    return AIParsingResponse(
        parsed_data=parsed_data,
        priority=priority_data,
        is_complete=completeness.get("is_complete", False),
        missing_fields=completeness.get("missing_fields", [])
    )
