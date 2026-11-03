import re
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai", tags=["AI Caption Checker"])

class CheckCaptionRequest(BaseModel):
    caption: str = Field(..., description="Food title and description entered by the donor")
    food_name: Optional[str] = None
    category: Optional[str] = None

class CheckCaptionResponse(BaseModel):
    quality_score: int
    quality_rating: str  # Excellent, Good, Fair, Needs Improvement
    is_safe: bool
    safety_flags: List[str]
    detected_allergens: List[str]
    detected_dietary_tags: List[str]
    detected_portions: Optional[str]
    detected_freshness: Optional[str]
    missing_elements: List[str]
    suggestions: List[str]
    enhanced_caption: str

ALLERGEN_PATTERNS = {
    "Peanuts / Tree Nuts": [r"\bnuts?\b", r"\bpeanuts?\b", r"\balmonds?\b", r"\bcashews?\b", r"\bwalnuts?\b"],
    "Dairy / Milk": [r"\bmilk\b", r"\bdairy\b", r"\bcheese\b", r"\bpaneer\b", r"\bbutter\b", r"\bcream\b", r"\bghee\b", r"\byogurt\b", r"\bcurd\b"],
    "Gluten / Wheat": [r"\bgluten\b", r"\bwheat\b", r"\bflour\b", r"\bmaida\b", r"\broti\b", r"\bbread\b", r"\bnaan\b"],
    "Eggs": [r"\beggs?\b", r"\bomelette\b", r"\begg\b"],
    "Soy": [r"\bsoya?\b", r"\btofu\b", r"\bedamame\b"],
    "Mustard": [r"\bmustard\b"],
    "Sesame": [r"\bsesame\b", r"\btil\b"]
}

DIETARY_PATTERNS = {
    "Vegetarian": [r"\bveg\b", r"\bvegetarian\b", r"\bpure veg\b"],
    "Vegan": [r"\bvegan\b", r"\bplant[- ]based\b"],
    "Halal": [r"\bhalal\b"],
    "Non-Vegetarian": [r"\bchicken\b", r"\bmeat\b", r"\bfish\b", r"\bmutton\b", r"\bnon[- ]?veg\b", r"\bpork\b", r"\bbeef\b"],
    "Gluten-Free": [r"\bgluten[- ]free\b"]
}

HAZARD_KEYWORDS = [
    "spoiled", "foul smell", "smelling bad", "stale", "sour taste", "expired", 
    "left out all night", "mold", "mould", "insects", "contaminated", "slimy"
]

@router.post("/check-caption", response_model=CheckCaptionResponse)
async def check_caption(req: CheckCaptionRequest):
    """
    Evaluates food donation description / caption using NLP heuristics:
    - Identifies allergen warnings & dietary classifications
    - Verifies food safety hazards & shelf-life hints
    - Scores caption completeness & generates structured recommendations
    """
    raw_text = req.caption.strip()
    if req.food_name and req.food_name.strip() not in raw_text:
        text_to_analyze = f"{req.food_name.strip()} - {raw_text}"
    else:
        text_to_analyze = raw_text

    text_lower = text_to_analyze.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    word_count = len(words)

    # 1. Hazard detection
    safety_flags = []
    is_safe = True
    for hazard in HAZARD_KEYWORDS:
        if hazard in text_lower:
            safety_flags.append(f"Potential hazard flagged: mentions '{hazard}'. Food must be strictly fresh.")
            is_safe = False

    # 2. Allergens detected
    detected_allergens = []
    for allergen, patterns in ALLERGEN_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                detected_allergens.append(allergen)
                break

    # 3. Dietary tags
    detected_dietary = []
    for tag, patterns in DIETARY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                detected_dietary.append(tag)
                break

    # 4. Portion identification
    portion_match = re.search(r'(\d+[\s-]*(?:portions?|servings?|people|meals?|plates?|boxes?|packets?|kg|liters?|ltrs?))', text_lower)
    detected_portions = portion_match.group(1) if portion_match else None

    # 5. Freshness / timing identification
    freshness_match = re.search(r'((?:prepared|cooked|made|packed|baked)\s+(?:at\s+\d+|[\w\s]+(?:hours?|mins?|ago|today|morning|afternoon|evening)))', text_lower)
    if not freshness_match:
        freshness_match = re.search(r'(\b\d+\s*(?:hours?|hrs?|mins?)\s*(?:ago|old)\b)', text_lower)
    detected_freshness = freshness_match.group(1) if freshness_match else None

    # Storage hints
    has_storage_notes = any(term in text_lower for term in [
        "hot", "cold", "chilled", "refrigerated", "airtight", "sealed", "stainless steel", "keep warm", "room temp"
    ])

    # Missing elements & scoring
    score = 100
    missing = []
    suggestions = []

    if word_count < 5:
        score -= 30
        missing.append("Detailed food description")
        suggestions.append("Add a more descriptive summary of the dishes and preparation style.")
    elif word_count < 10:
        score -= 10

    if not detected_portions:
        score -= 20
        missing.append("Quantity / Number of servings")
        suggestions.append("Specify how many portions, servings, or kilograms are available (e.g., 'approx 25 servings').")
    else:
        suggestions.append(f"Great! Portions identified: '{detected_portions}'.")

    if not detected_freshness:
        score -= 20
        missing.append("Preparation / Cooked time")
        suggestions.append("Mention when the meal was prepared (e.g., 'Cooked at 1:30 PM today').")
    else:
        suggestions.append(f"Freshness timestamp found: '{detected_freshness}'.")

    if not has_storage_notes:
        score -= 10
        missing.append("Storage / Handling recommendations")
        suggestions.append("Mention if items require refrigeration or are in insulated/sealed containers.")

    if not detected_allergens:
        suggestions.append("Tip: If the food contains nuts, dairy, or gluten, explicitly listing them helps recipient shelters distribute safely.")
    else:
        suggestions.append(f"Allergens clearly recognized: {', '.join(detected_allergens)}.")

    if not is_safe:
        score = min(score, 20)

    score = max(5, min(100, score))

    if score >= 85:
        rating = "Excellent"
    elif score >= 65:
        rating = "Good"
    elif score >= 45:
        rating = "Fair"
    else:
        rating = "Needs Improvement"

    # Enhanced Caption builder
    enhanced_parts = []
    enhanced_parts.append(req.food_name or "Fresh surplus food donation")
    if detected_dietary:
        enhanced_parts.append(f"[{', '.join(detected_dietary)}]")
    enhanced_parts.append(f"- {raw_text}")
    if detected_portions and detected_portions not in raw_text.lower():
        enhanced_parts.append(f"Quantity: {detected_portions}.")
    if detected_freshness and detected_freshness not in raw_text.lower():
        enhanced_parts.append(f"Prepared: {detected_freshness}.")
    if detected_allergens:
        enhanced_parts.append(f"Allergen Notice: Contains {', '.join(detected_allergens)}.")
    
    enhanced_caption = " ".join(enhanced_parts)

    return CheckCaptionResponse(
        quality_score=score,
        quality_rating=rating,
        is_safe=is_safe,
        safety_flags=safety_flags,
        detected_allergens=detected_allergens,
        detected_dietary_tags=detected_dietary,
        detected_portions=detected_portions,
        detected_freshness=detected_freshness,
        missing_elements=missing,
        suggestions=suggestions,
        enhanced_caption=enhanced_caption
    )
