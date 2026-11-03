from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.api.auth import get_current_user
from app.ai.food_safety.predictor import food_safety_predictor

router = APIRouter()

class FoodSafetyRequest(BaseModel):
    food_type: str
    elapsed_hours: float = 0.0
    storage_condition: Optional[str] = "Room Temperature"
    storage_container: Optional[str] = "Airtight Stainless Steel"
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = 60.0
    packaging: Optional[str] = "Container"
    has_expiry_info: Optional[int] = 0

class FoodSafetyResponse(BaseModel):
    classification: str
    confidence: float
    safe_status: str
    safe_consumption_window_hours: float
    hours_remaining: float
    expiry_timestamp: str
    risk_score: float
    handling_recommendation: str
    fssai_guideline: str
    container_advice: str
    temperature_c: float
    humidity_pct: float
    important_features: List[str]
    model_version: str
    disclaimer: str

@router.post("/food-safety/evaluate", response_model=FoodSafetyResponse)
async def evaluate_shelf_life(request: FoodSafetyRequest):
    """
    Public/Donor AI endpoint to calculate dynamic safe shelf-life window
    based on cooking elapsed time, temperature, humidity, and storage container.
    """
    prediction = food_safety_predictor.predict(request.dict())
    return prediction

@router.post("/food-safety/predict", response_model=FoodSafetyResponse)
async def predict_food_safety(request: FoodSafetyRequest, current_user: dict = Depends(get_current_user)):
    """
    Evaluates food safety parameters and returns safe shelf-life window and FSSAI classification.
    Available to all authenticated roles (DONOR, NGO, RELIEF_HUB, VOLUNTEER, ADMIN).
    """
    prediction = food_safety_predictor.predict(request.dict())
    return prediction

@router.get("/food-safety/audits")
async def get_food_safety_audits(current_user: dict = Depends(get_current_user)):
    """
    Admin only: Fetches all active donations, evaluates rule-based expiry, and generates AI risk flags.
    """
    if current_user.get("role", "").lower() not in ["admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    from app.database.mongodb import mongodb
    from datetime import datetime, timezone
    
    cursor = mongodb.db.donations.find({"status": {"$nin": ["COMPLETED", "CANCELLED", "REJECTED"]}})
    donations = await cursor.to_list(length=100)
    
    audits = []
    now = datetime.now(timezone.utc)
    
    for d in donations:
        status = "SAFE"
        expiry_str = d.get("expiry_time")
        prep_str = d.get("prepared_time")
        
        elapsed_hours = 0.0
        
        if expiry_str:
            try:
                if isinstance(expiry_str, str):
                    expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                else:
                    expiry_dt = expiry_str
                    
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    
                if now > expiry_dt:
                    status = "EXPIRED"
            except:
                pass
                
        if prep_str:
            try:
                if isinstance(prep_str, str):
                    prep_dt = datetime.fromisoformat(prep_str.replace("Z", "+00:00"))
                else:
                    prep_dt = prep_str
                    
                if prep_dt.tzinfo is None:
                    prep_dt = prep_dt.replace(tzinfo=timezone.utc)
                    
                elapsed_hours = (now - prep_dt).total_seconds() / 3600.0
                
                if elapsed_hours > 4 and d.get("storage_condition", "").lower() == "room_temperature":
                    status = "REVIEW_REQUIRED" if status != "EXPIRED" else "EXPIRED"
            except:
                pass

        # AI Advisory Risk
        req = FoodSafetyRequest(
            food_type=d.get("food_type", "Unknown"),
            elapsed_hours=elapsed_hours,
            storage_condition=d.get("storage_condition", "Room Temperature"),
            storage_container=d.get("storage_container", "Container"),
            temperature_c=d.get("temperature", None),
            packaging=d.get("packaging", "Container")
        )
        
        prediction = food_safety_predictor.predict(req.dict())
        ai_risk = f"AI says {prediction['classification']}: {prediction['safe_status']} ({prediction['hours_remaining']}h remaining)"
        
        if prediction['classification'] == "UNSAFE" and status == "SAFE":
            status = "REVIEW_REQUIRED"
            
        audits.append({
            "id": str(d.get("_id")),
            "donor": d.get("donor_id", "Unknown"),
            "food_type": d.get("food_type", "Unknown"),
            "prep_time": str(prep_str) if prep_str else "Unknown",
            "expiry": str(expiry_str) if expiry_str else "Unknown",
            "storage": d.get("storage_condition", "Unknown"),
            "temp": str(d.get("temperature", "Unknown")),
            "packaging": d.get("packaging", "Unknown"),
            "veg_nonveg": d.get("veg_nonveg", "Unknown"),
            "allergens": "None listed",
            "status": status,
            "ai_risk": ai_risk,
            "hours_remaining": prediction["hours_remaining"],
            "handling_recommendation": prediction["handling_recommendation"],
            "fssai_guideline": prediction["fssai_guideline"]
        })
        
    return audits
