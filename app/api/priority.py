from fastapi import APIRouter, HTTPException
from app.models.priority import PriorityPredictionRequest, PriorityPredictionResponse
from app.ai.priority.predictor import predictor

router = APIRouter(tags=["AI Priority"])

@router.post("/ai/priority/predict", response_model=PriorityPredictionResponse)
@router.post("/priority/predict", response_model=PriorityPredictionResponse)
async def predict_priority(request: PriorityPredictionRequest):
    """
    Predict the operational priority of an emergency using situational features.
    Uses ML Random Forest model if available, otherwise falls back to Rule-based baseline.
    Accessible via both /api/ai/priority/predict and /api/priority/predict.
    """
    try:
        features = request.model_dump()
        result = predictor.predict(features)
        return PriorityPredictionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Priority prediction failed: {str(e)}")
