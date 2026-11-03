from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.ai.food_image.predictor import food_image_predictor

router = APIRouter()

class FoodImageRequest(BaseModel):
    image_base64: str
    declared_food_type: Optional[str] = ""
    declared_quantity: Optional[int] = 0

class TopPrediction(BaseModel):
    category: str
    probability: float

class FoodImageResponse(BaseModel):
    predicted_category: str
    food_item_name: str
    confidence: float
    top_predictions: List[TopPrediction]
    is_match: bool
    verification_message: str
    freshness_status: str
    spoilage_score: float
    visual_defects: List[str]
    is_safe_for_redistribution: bool
    recommendation: str
    disclaimer: str
    # 6-Stage Responsible AI Pipeline Schema:
    status: Optional[str] = "FOOD_IDENTIFIED"
    food_detected: Optional[bool] = True
    safety_review_status: Optional[str] = "SAFETY_INFORMATION_REQUIRED"
    pipeline_stage: Optional[str] = "STAGE_6_SAFETY_EVALUATION"
    safety_advisory: Optional[str] = None

@router.post("/food-image/classify", response_model=FoodImageResponse)
@router.post("/food-image/analyze", response_model=FoodImageResponse)
async def classify_and_inspect_food_image(request: FoodImageRequest):
    """
    AI Module 1: Computer Vision - Food Category & Spoilage / Visual Defect Screening.
    Identifies food category (Cooked Meals, Raw Produce, Bakery, Dairy, Packaged Groceries)
    and analyzes visible defects (mold clusters, severe discoloration, oxidation).
    """
    prediction = food_image_predictor.predict(
        base64_image=request.image_base64,
        declared_food_type=request.declared_food_type or "",
        declared_quantity=request.declared_quantity or 0
    )
    
    if "error" in prediction and not prediction.get("predicted_category"):
        raise HTTPException(status_code=500, detail=prediction["error"])
        
    return FoodImageResponse(
        predicted_category=prediction.get("predicted_category", "Cooked Meals"),
        food_item_name=prediction.get("food_item_name", "Cooked Meals"),
        confidence=prediction.get("confidence", 0.85),
        top_predictions=[
            TopPrediction(category=p["category"], probability=p["probability"]) 
            for p in prediction.get("top_predictions", [])
        ],
        is_match=prediction.get("is_match", True),
        verification_message=prediction.get("verification_message", "Verified by AI vision model."),
        freshness_status=prediction.get("freshness_status", "FRESH"),
        spoilage_score=prediction.get("spoilage_score", 0.05),
        visual_defects=prediction.get("visual_defects", []),
        is_safe_for_redistribution=prediction.get("is_safe_for_redistribution", True),
        recommendation=prediction.get("recommendation", "Visual inspection passed."),
        disclaimer=prediction.get("disclaimer", "Statutory FSSAI Advisory: AI visual detection cannot guarantee microbial safety."),
        status=prediction.get("status", "NO_FOOD_DETECTED" if prediction.get("freshness_status") == "NON_FOOD_REJECTED" else "FOOD_IDENTIFIED"),
        food_detected=prediction.get("food_detected", prediction.get("freshness_status") != "NON_FOOD_REJECTED"),
        safety_review_status=prediction.get("safety_review_status", "REJECTED_BY_SAFETY_RULE" if prediction.get("freshness_status") == "NON_FOOD_REJECTED" else "SAFETY_INFORMATION_REQUIRED"),
        pipeline_stage=prediction.get("pipeline_stage", "STAGE_2_FOOD_PRESENCE_CHECK" if prediction.get("freshness_status") == "NON_FOOD_REJECTED" else "STAGE_6_SAFETY_EVALUATION"),
        safety_advisory=prediction.get("disclaimer", "Statutory FSSAI Advisory: AI visual detection cannot guarantee microbial safety.")
    )
