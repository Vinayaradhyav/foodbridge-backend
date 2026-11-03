from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re
from datetime import datetime, timezone, timedelta

from app.models.emergency import EmergencyRequestCreate, EmergencyRequestResponse, Urgency
from app.services.emergency_service import EmergencyService
from app.services.notification_service import create_notification
from app.schemas.notification import NotificationCreate
from app.database.mongodb import get_database

router = APIRouter(prefix="/ai-emergency", tags=["AI Emergency"])

class AIParsingRequest(BaseModel):
    message: str
    ngo_id: str

class AIParsingResponse(BaseModel):
    parsed_data: dict
    emergency: EmergencyRequestResponse

@router.post("/", response_model=AIParsingResponse, status_code=201)
async def process_emergency_message(request: AIParsingRequest):
    """
    Mock AI NLP Parser.
    Extracts quantity, people, and urgency from unstructured text.
    Creates an emergency request and calculates priority.
    """
    msg = request.message.lower()
    
    # 1. AI Multilingual NLP Extraction
    from app.ai.chatbot.multilingual_nlp import multilingual_nlp_engine
    extracted = multilingual_nlp_engine.extract_entities(request.message)

    quantity = extracted.get("quantity", 100)
    people = extracted.get("number_of_people", 50)
    food_type = extracted.get("food_type", "Assorted Meals")
    extracted_urgency = extracted.get("urgency", "MEDIUM")

    if extracted_urgency == "CRITICAL":
        urgency = Urgency.CRITICAL
    elif extracted_urgency == "HIGH":
        urgency = Urgency.HIGH
    else:
        urgency = Urgency.MEDIUM
        
    # Deadline estimation based on urgency
    deadline = datetime.now(timezone.utc)
    if urgency == Urgency.CRITICAL:
        deadline += timedelta(hours=3)
    elif urgency == Urgency.HIGH:
        deadline += timedelta(hours=12)
    else:
        deadline += timedelta(days=1)
        
    if quantity == 0:
        quantity = 100 # Fallback default
    if people == 0:
        people = 50 # Fallback default

    # 2. Structure the data
    create_payload = EmergencyRequestCreate(
        ngo_id=request.ngo_id,
        emergency_type="Relief Operation",
        food_type=food_type,
        quantity=quantity,
        unit="meals" if "meal" in food_type.lower() else "items",
        number_of_people=people,
        urgency=urgency,
        deadline=deadline,
        location={"lat": 12.9716, "lng": 77.5946}, # Defaulting to Bangalore
        special_instructions=request.message
    )
    
    # 3. Process via Priority Engine
    try:
        emergency = await EmergencyService.create_emergency(create_payload)
        
        # 4. Notify Donors via Push (Mock)
        # Find all donors in DB
        db = get_database()
        donors = await db.users.find({"role": "DONOR"}).to_list(length=100)
        
        for donor in donors:
            await create_notification(NotificationCreate(
                user_id=str(donor["_id"]),
                title=f"URGENT: {urgency.name} Priority",
                message=f"Need {quantity} {food_type} for {people} people.",
                type="EMERGENCY_BROADCAST",
                related_entity_id=emergency.request_id
            ))
            
        return AIParsingResponse(
            parsed_data={
                "quantity": quantity,
                "people": people,
                "food_type": food_type,
                "urgency": urgency.name
            },
            emergency=emergency
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
