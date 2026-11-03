from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.api.auth import get_current_user
from app.services.matching_engine import MatchingEngine

router = APIRouter()

@router.post("/donation/{donation_id}", response_model=Dict[str, List[Dict[str, Any]]])
async def match_donation(donation_id: str, current_user: dict = Depends(get_current_user)):
    """
    Returns ranked NGOs and Emergencies for a specific donation.
    Matches donation against active emergencies and registered NGOs based on 
    rules (distance, urgency, compatibility, capacity).
    """
    if current_user["role"] not in ["DONOR", "NGO", "RELIEF_HUB", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    matched_ngos = await MatchingEngine.match_donation_to_ngos(donation_id)
    matched_emergencies = await MatchingEngine.match_donation_to_emergencies(donation_id)

    return {
        "matched_ngos": matched_ngos,
        "matched_emergencies": matched_emergencies
    }

@router.post("/emergency/{request_id}", response_model=Dict[str, List[Dict[str, Any]]])
async def match_emergency(request_id: str, current_user: dict = Depends(get_current_user)):
    """
    Returns ranked Available Donations for a specific emergency.
    This works by fetching the emergency and then scoring all available donations against it.
    """
    if current_user["role"] not in ["NGO", "RELIEF_HUB", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.database.mongodb import mongodb

    try:
        emergency = await mongodb.db.emergencies.find_one({"request_id": request_id})
        if not emergency:
            # Fallback to _id
            from bson import ObjectId
            emergency = await mongodb.db.emergencies.find_one({"_id": ObjectId(request_id)})
            if not emergency:
                raise HTTPException(status_code=404, detail="Emergency not found")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid emergency ID")

    # Fetch all available donations
    donations = await mongodb.db.donations.find({"status": "AVAILABLE"}).to_list(length=100)
    
    matches = []
    for donation in donations:
        score = MatchingEngine._score_emergency_for_donation(emergency, donation)
        if score['total_score'] > 10:
            matches.append({
                "donation_id": str(donation["_id"]),
                "food_name": donation.get("food_name"),
                "food_type": donation.get("food_type"),
                "score": score['total_score'],
                "breakdown": score['breakdown']
            })
            
    # Sort descending
    matches.sort(key=lambda x: x['score'], reverse=True)

    return {
        "matched_donations": matches
    }

@router.post("/emergency/{request_id}/aggregate", response_model=Dict[str, Any])
async def aggregate_emergency(request_id: str, current_user: dict = Depends(get_current_user)):
    """
    Greedy Matching: Aggregates multiple pending donations to fulfill a single large emergency request.
    """
    if current_user["role"] not in ["NGO", "RELIEF_HUB", "ADMIN"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await MatchingEngine.aggregate_donations_for_emergency(request_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
