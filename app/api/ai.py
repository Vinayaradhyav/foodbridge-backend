from fastapi import APIRouter, HTTPException
from app.models.nlp import NLPRequest, NLPEmergencyResponse
from app.nlp.factory import ExtractorFactory

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/nlp/extract", response_model=NLPEmergencyResponse)
async def extract_emergency_info(request: NLPRequest):
    """
    Extract structured data from a natural language emergency request.
    Uses the configured NLP extractor (defaults to rule-based baseline).
    """
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
        
    try:
        extractor = ExtractorFactory.get_extractor("ml")
        extracted_data = extractor.extract(request.text)
        return NLPEmergencyResponse(**extracted_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NLP extraction failed: {str(e)}")
