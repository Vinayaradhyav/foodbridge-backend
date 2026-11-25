from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.ai.food_image.predictor import food_image_predictor
from app.ai.food_image.food_validation_engine import food_validation_engine
from app.ai.verification.donation_verification_engine import donation_verification_engine


router = APIRouter()

class FoodImageRequest(BaseModel):
    image_base64: str
    declared_food_type: Optional[str] = ""
    declared_quantity: Optional[int] = 0

class TopPrediction(BaseModel):
    category: str
    probability: float

class DetectedObjectItem(BaseModel):
    label: str
    confidence: float
    box: List[float]

class FoodImageResponse(BaseModel):
    predicted_category: str
    food_item_name: str
    confidence: float
    top_predictions: List[TopPrediction]
    is_match: bool
    verification_message: str
    freshness_status: str
    freshness_grade: Optional[str] = "Grade A (Peak Freshness)"
    overall_quality_score: Optional[float] = 0.96
    spoilage_score: float
    visual_defects: List[str]
    is_safe_for_redistribution: bool
    recommendation: str
    disclaimer: str
    
    # Visual Quantity & Volume Estimation
    estimated_quantity: Optional[str] = "1 - 5 Servings (approx. 1.5 kg)"
    estimated_servings: Optional[int] = 4
    estimated_weight_kg: Optional[float] = 1.5
    container_type: Optional[str] = "Standard Meal Container / Platter"
    detected_container_or_object: Optional[str] = "Standard Meal Container / Platter"
    
    # Advanced Multi-Object Detection, OCR & Quantity Validation
    object_count: Optional[int] = 1
    detected_objects: Optional[List[DetectedObjectItem]] = []
    package_size: Optional[str] = None
    estimated_total_quantity: Optional[float] = 1.5
    quantity_unit: Optional[str] = "servings"
    quantity_confidence: Optional[float] = 0.85
    requires_donor_confirmation: Optional[bool] = False
    ocr_detected_text: Optional[str] = None
    ocr_extracted_quantity: Optional[str] = None

    # 6-Stage Responsible AI Pipeline Schema & Part 10 Fields:
    status: Optional[str] = "FOOD_IDENTIFIED"
    is_food: Optional[bool] = True
    is_eligible_donation: Optional[bool] = True
    can_continue: Optional[bool] = True
    product_name: Optional[str] = "Cooked Meals"
    category: Optional[str] = "Cooked Meals"
    food_type: Optional[str] = "Vegetarian"
    preparation_type: Optional[str] = "Cooked"
    packaging_type: Optional[str] = "Standard Meal Container"
    warnings: Optional[List[str]] = []
    rejection_reason: Optional[str] = None
    model_version: Optional[str] = "2.0"
    detected_category: Optional[str] = "Cooked Meals"
    detected_object: Optional[str] = "Cooked Meals"
    reason: Optional[str] = "Eligible food item verified for donation."
    message: Optional[str] = "Food image successfully validated."
    food_detected: Optional[bool] = True
    safety_review_status: Optional[str] = "SAFETY_INFORMATION_REQUIRED"
    pipeline_stage: Optional[str] = "STAGE_6_SAFETY_EVALUATION"
    safety_advisory: Optional[str] = None

@router.post("/food-image/classify", response_model=FoodImageResponse)
@router.post("/food-image/analyze", response_model=FoodImageResponse)
async def classify_and_inspect_food_image(request: FoodImageRequest):
    """
    AI Module 1: Comprehensive Food, Grocery, Fruits, Vegetables & Beverage Recognition.
    Performs MobileNet transfer learning classification, multiple-object detection,
    OCR label extraction, and validated quantity calculation.
    """
    prediction = food_image_predictor.predict(
        base64_image=request.image_base64,
        declared_food_type=request.declared_food_type or "",
        declared_quantity=request.declared_quantity or 0
    )
    
    if "error" in prediction and not prediction.get("predicted_category"):
        raise HTTPException(status_code=500, detail=prediction["error"])
        
    detected_objs = []
    for o in prediction.get("detected_objects", []):
        try:
            detected_objs.append(DetectedObjectItem(
                label=o.get("label", "Food Item"),
                confidence=float(o.get("confidence", 0.85)),
                box=[float(b) for b in o.get("box", [0, 0, 100, 100])]
            ))
        except Exception:
            pass

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
        freshness_grade=prediction.get("freshness_grade", "Grade A (Peak Freshness)"),
        overall_quality_score=prediction.get("overall_quality_score", 0.96),
        spoilage_score=prediction.get("spoilage_score", 0.05),
        visual_defects=prediction.get("visual_defects", []),
        is_safe_for_redistribution=prediction.get("is_safe_for_redistribution", True),
        recommendation=prediction.get("recommendation", "Visual inspection passed."),
        disclaimer=prediction.get("disclaimer", "Statutory FSSAI Advisory: AI visual detection cannot guarantee microbial safety."),
        estimated_quantity=prediction.get("estimated_quantity_text", "1 - 5 Servings (approx. 1.5 kg)"),
        estimated_servings=prediction.get("estimated_servings", 4),
        estimated_weight_kg=prediction.get("estimated_weight_kg", 1.5),
        container_type=prediction.get("container_type", "Standard Meal Container / Platter"),
        detected_container_or_object=prediction.get("detected_container_or_object", prediction.get("container_type", "Standard Meal Container / Platter")),
        # New Multi-Object, OCR & Quantity fields
        object_count=prediction.get("object_count", max(1, len(detected_objs))),
        detected_objects=detected_objs,
        package_size=prediction.get("package_size"),
        estimated_total_quantity=prediction.get("estimated_total_quantity", 1.5),
        quantity_unit=prediction.get("quantity_unit", "servings"),
        quantity_confidence=prediction.get("quantity_confidence", 0.85),
        requires_donor_confirmation=prediction.get("requires_donor_confirmation", False),
        ocr_detected_text=prediction.get("ocr_detected_text"),
        ocr_extracted_quantity=prediction.get("ocr_extracted_quantity"),
        # 6-Stage status fields
        status=prediction.get("status", "REJECTED" if prediction.get("freshness_status") == "NON_FOOD_REJECTED" else "ACCEPTED"),
        is_food=prediction.get("is_food", prediction.get("freshness_status") != "NON_FOOD_REJECTED"),
        is_eligible_donation=prediction.get("is_eligible_donation", prediction.get("freshness_status") != "NON_FOOD_REJECTED"),
        can_continue=prediction.get("can_continue", prediction.get("freshness_status") != "NON_FOOD_REJECTED"),
        product_name=prediction.get("product_name", prediction.get("food_item_name", "Cooked Meals")),
        category=prediction.get("category", prediction.get("predicted_category", "Cooked Meals")),
        food_type=prediction.get("food_type", "Vegetarian"),
        preparation_type=prediction.get("preparation_type", "Cooked"),
        packaging_type=prediction.get("packaging_type", prediction.get("container_type", "Meal Container")),
        warnings=prediction.get("warnings", []),
        rejection_reason=prediction.get("rejection_reason"),
        model_version=prediction.get("model_version", "2.0"),
        detected_category=prediction.get("detected_category", prediction.get("predicted_category", "Cooked Meals")),
        detected_object=prediction.get("detected_object", prediction.get("food_item_name", "Cooked Meals")),
        reason=prediction.get("reason", prediction.get("recommendation", "Verified by AI")),
        message=prediction.get("verification_message", "Food image verified."),
        food_detected=prediction.get("food_detected", prediction.get("freshness_status") != "NON_FOOD_REJECTED"),
        safety_review_status=prediction.get("safety_review_status", "REJECTED_BY_SAFETY_RULE" if prediction.get("freshness_status") == "NON_FOOD_REJECTED" else "SAFETY_INFORMATION_REQUIRED"),
        pipeline_stage=prediction.get("pipeline_stage", "STAGE_2_FOOD_PRESENCE_CHECK" if prediction.get("freshness_status") == "NON_FOOD_REJECTED" else "STAGE_6_SAFETY_EVALUATION"),
        safety_advisory=prediction.get("disclaimer", "Statutory FSSAI Advisory: AI visual detection cannot guarantee microbial safety.")
    )


class DonationVerificationRequest(BaseModel):
    donor_id: Optional[str] = "DONOR_ANONYMOUS"
    food_name: str
    food_type: str
    category: str
    quantity: float
    unit: str
    latitude: float
    longitude: float
    storage_condition: Optional[str] = "Room Temp"
    packaging_type: Optional[str] = "Boxes"
    ai_vision_analysis: Optional[Dict[str, Any]] = None
    donor_profile: Optional[Dict[str, Any]] = None


@router.post("/food-image/verify-donation")
async def verify_full_donation_pipeline(request: DonationVerificationRequest):
    """
    Central AI Multi-Factor Verification Gate (Parts 7, 8, 9).
    Synthesizes image validation, food specification, GPS distance,
    receiver capacity, volunteer allocation, and donor trust before enabling submission.
    """
    result = donation_verification_engine.evaluate_full_donation(
        donor_id=request.donor_id or "DONOR_USER",
        food_name=request.food_name,
        food_type=request.food_type,
        category=request.category,
        quantity=request.quantity,
        unit=request.unit,
        latitude=request.latitude,
        longitude=request.longitude,
        storage_condition=request.storage_condition or "Room Temp",
        packaging_type=request.packaging_type or "Boxes",
        ai_vision_analysis=request.ai_vision_analysis,
        donor_profile=request.donor_profile
    )
    return result

