"""
FoodBridge NLP V2 API Router
Exposes production-grade NLP endpoints for natural language donation analysis,
emergency priority calculation, multi-donor matching, and model diagnostics.
"""

import os
import json
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.ai.nlp_v2.pipeline import nlp_donation_pipeline
from app.ai.nlp_v2.nlp_monitor import nlp_monitor
from app.ai.nlp_v2.multi_donor_allocator import multi_donor_allocator

router = APIRouter(prefix="/nlp", tags=["NLP Donation Intelligence"])

# ----------------- PYDANTIC SCHEMAS -----------------
class NLPAnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Natural language donation or request message")
    session_id: Optional[str] = Field(None, description="Optional dialogue session identifier")
    user_location: Optional[str] = Field(None, description="Optional user geographical location or address")
    user_role: Optional[str] = Field(None, description="Role of the caller: donor, receiver, volunteer, admin")

class MultiDonorMatchRequest(BaseModel):
    requirement: Dict[str, Any] = Field(..., description="Requirement details including category, quantity, location")
    max_radius_km: Optional[float] = Field(25.0, description="Maximum search radius in kilometers")


# ----------------- ENDPOINTS -----------------

@router.post("/analyze-request")
async def analyze_request(payload: NLPAnalyzeRequest, request: Request):
    """
    Main unified NLP Donation Request Intelligence endpoint.
    Performs intent classification, multi-item entity extraction, priority calculation,
    completeness verification, and context resolution in a single high-speed call.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Input message text cannot be empty.")

    client_ip = request.client.host if request.client else "unknown"

    result = nlp_donation_pipeline.analyze(
        text=payload.message,
        session_id=payload.session_id,
        user_role=payload.user_role,
        user_location=payload.user_location
    )

    # Telemetry logging
    await nlp_monitor.log_inference(result, client_ip=client_ip)

    return result


@router.post("/donations/parse-request")
async def parse_donation_request(payload: NLPAnalyzeRequest, request: Request):
    """
    Specialized intake endpoint for donation offers.
    Extracts food items, quantity, perishability, and pickup details.
    """
    return await analyze_request(payload, request)


@router.post("/emergency/analyze")
async def analyze_emergency_intake(payload: NLPAnalyzeRequest, request: Request):
    """
    Specialized intake endpoint for crisis / emergency hunger relief requests.
    Calculates 0-100 score, evidence breakdown, and sets verification flag.
    """
    return await analyze_request(payload, request)


@router.post("/donations/match-multi")
async def match_multi_donor(payload: MultiDonorMatchRequest):
    """
    Multi-Donor Combinatorial Allocation Engine.
    Queries MongoDB for available donor inventory and creates an atomic allocation plan.
    """
    req_data = payload.requirement
    radius = payload.max_radius_km or 25.0

    # Query active donations from MongoDB
    available_donations = []
    try:
        from app.database import mongodb
        if mongodb.db is not None:
            cursor = mongodb.db.donations.find({
                "status": {"$in": ["AVAILABLE", "ACTIVE", "VERIFIED", "FRESH", "Approved"]}
            })
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                available_donations.append(doc)
    except Exception as e:
        print(f"[Match Multi] Database query warning: {e}")

    # Compute combinatorial allocation plan
    allocation_plan = multi_donor_allocator.compute_allocation_plan(
        requirement=req_data,
        available_donations=available_donations,
        max_search_radius_km=radius
    )

    return allocation_plan


@router.get("/model-status")
async def get_model_status():
    """
    Returns diagnostic health and loaded state of the NLP V2 model.
    """
    model_loaded = nlp_donation_pipeline.model is not None
    classes_count = len(nlp_donation_pipeline.model.classes_) if model_loaded else 0
    classes = list(nlp_donation_pipeline.model.classes_) if model_loaded else []

    file_size_bytes = 0
    if os.path.exists(nlp_donation_pipeline.model_path):
        file_size_bytes = os.path.getsize(nlp_donation_pipeline.model_path)

    return {
        "status": "healthy" if model_loaded else "degraded",
        "model_version": "v2.0-sgd-calibrated-multilingual",
        "model_path": nlp_donation_pipeline.model_path,
        "model_file_size_kb": round(file_size_bytes / 1024, 2),
        "is_loaded": model_loaded,
        "classes_count": classes_count,
        "supported_intents": classes
    }


@router.get("/model-metrics")
async def get_model_metrics():
    """
    Returns independent evaluation metrics and confusion matrix from training artifacts.
    """
    base_models_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "backend", "models", "nlp_v2"
    )
    metrics_path = os.path.join(base_models_dir, "evaluation_metrics.json")
    cm_path = os.path.join(base_models_dir, "confusion_matrix.json")

    metrics_data = {}
    cm_data = {}

    if os.path.exists(metrics_path):
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)

    if os.path.exists(cm_path):
        with open(cm_path, "r", encoding="utf-8") as f:
            cm_data = json.load(f)

    return {
        "evaluation_metrics": metrics_data,
        "confusion_matrix": cm_data
    }


@router.get("/telemetry")
async def get_telemetry():
    """
    Returns real-time inference latency distribution and intent frequency.
    """
    return nlp_monitor.get_summary_metrics()
