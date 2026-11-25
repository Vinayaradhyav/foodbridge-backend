"""
FoodBridge NLP V2 — Unified Donation Intelligence & Prediction Pipeline
Integrates TF-IDF + SGD Intent Classification, Multi-Item Entity Extraction,
Context Session Memory, Missing Field Detection, and Explainable Urgency Scoring.
"""

import os
import time
import uuid
import re
from typing import Dict, Any, Optional, List

try:
    import joblib
except ImportError:
    joblib = None

from app.ai.nlp_v2.entity_extractor import entity_extractor
from app.ai.nlp_v2.context_manager import context_manager
from app.ai.nlp_v2.missing_info_detector import missing_info_detector
from app.ai.nlp_v2.priority_engine import priority_engine

# Path to the trained pipeline model
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# app/ai/nlp_v2 -> app/ai -> app -> backend
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
MODEL_PATH = os.path.join(BACKEND_DIR, "models", "nlp_v2", "nlp_v2_pipeline.joblib")


class NLPDonationPipeline:
    """Master production pipeline for FoodBridge NLP donation intelligence."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or MODEL_PATH
        self.model = None
        self._load_model()

    def _load_model(self):
        if joblib is None:
            print("[NLP Pipeline V2] joblib unavailable; running rule+Indic heuristic mode.")
            self.model = None
            return
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                print(f"[NLP Pipeline V2] Loaded model from {self.model_path}")
            else:
                print(f"[NLP Pipeline V2] WARNING: Model file not found at {self.model_path}")
        except Exception as e:
            print(f"[NLP Pipeline V2] ERROR loading model: {e}")
            self.model = None

    def analyze(
        self,
        text: str,
        session_id: Optional[str] = None,
        user_role: Optional[str] = None,
        user_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end multi-stage inference on an incoming natural language message.
        """
        start_time = time.time()
        request_id = f"NLP-{uuid.uuid4().hex[:10].upper()}"

        if not text or not text.strip():
            return {
                "request_id": request_id,
                "error": "Empty input text provided",
                "intent": "UNKNOWN_OR_UNSUPPORTED",
                "confidence": 0.0,
                "processing_time_ms": 0.1
            }

        cleaned_text = text.strip()
        lowered = cleaned_text.lower()

        # 1. Intent Classification
        intent, confidence, top_intents = self._classify_intent(cleaned_text)

        # 2. Entity Extraction
        entities = entity_extractor.extract_all(cleaned_text)

        # Fallback location from user profile if not extracted
        if not entities.get("location") and user_location:
            entities["location"] = user_location

        # 3. Negation & Directional Safeguard
        intent, confidence = self._apply_directional_safeguards(cleaned_text, lowered, intent, confidence, entities)

        # 4. Non-food rejection override
        if entities.get("non_food_detected") and not entities.get("is_valid_food"):
            intent = "UNKNOWN_OR_UNSUPPORTED"
            confidence = 0.99

        # 5. Context Resolution (multi-turn memory)
        context_res = context_manager.resolve_context(
            session_id=session_id,
            current_intent=intent,
            current_entities=entities,
            raw_text=cleaned_text
        )

        # Merge resolved context entities if continuation
        if context_res.get("is_continuation"):
            resolved = context_res.get("resolved_entities", {})
            if resolved.get("location") and not entities.get("location"):
                entities["location"] = resolved["location"]
            if resolved.get("total_quantity") and entities.get("total_quantity", 0) == 0:
                entities["total_quantity"] = resolved["total_quantity"]

        # 6. Missing Information Detection
        completeness = missing_info_detector.evaluate(intent, entities)

        # 7. Priority & Urgency Engine
        priority = priority_engine.calculate_priority(intent, cleaned_text, entities)

        # 8. Action Recommendation
        recommendation = self._determine_action(intent, completeness["is_complete"], priority["priority_level"], entities)

        latency_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "request_id": request_id,
            "text": cleaned_text,
            "intent": intent,
            "confidence": round(confidence, 4),
            "top_intents": top_intents,
            "entities": entities,
            "priority": priority,
            "completeness": completeness,
            "context": context_res,
            "action_recommendation": recommendation,
            "processing_time_ms": latency_ms
        }

    def _classify_intent(self, text: str) -> (str, float, List[Dict[str, Any]]):
        """Classifies text with calibrated probabilities."""
        if not self.model:
            return "UNKNOWN_OR_UNSUPPORTED", 0.5, []

        try:
            probs = self.model.predict_proba([text])[0]
            classes = self.model.classes_

            # Top 3 intents
            sorted_indices = probs.argsort()[::-1]
            top_intent = classes[sorted_indices[0]]
            top_prob = float(probs[sorted_indices[0]])

            top_intents = [
                {"intent": classes[idx], "probability": round(float(probs[idx]), 4)}
                for idx in sorted_indices[:3]
            ]

            return top_intent, top_prob, top_intents
        except Exception as e:
            print(f"[NLP Pipeline V2] Prediction error: {e}")
            return "UNKNOWN_OR_UNSUPPORTED", 0.0, []

    def _apply_directional_safeguards(
        self,
        raw_text: str,
        lowered: str,
        intent: str,
        confidence: float,
        entities: Dict[str, Any]
    ) -> (str, float):
        """
        Enforces linguistic rules preventing false positive donation offers or requests
        on negations ('We don't have food') or explicit offer cues ('We have 100 meals').
        """
        # Explicit Negations
        if any(neg in lowered for neg in ["don't have", "do not have", "cannot donate", "can't donate", "no food available", "nothing left to give"]):
            return "UNKNOWN_OR_UNSUPPORTED", 0.99

        # Strong Offer cues (e.g. 'We have X meals', 'Can donate X packets')
        if any(cue in lowered for cue in ["we have", "i have", "can donate", "ready to donate", "cooked surplus", "extra meals available"]):
            if "water" in lowered and entities.get("primary_category") == "WATER":
                return "WATER_DONATION", max(confidence, 0.92)
            if any(k in lowered for k in ["grocery", "rice bag", "flour", "atta", "oil"]):
                return "GROCERY_DONATION", max(confidence, 0.92)
            return "FOOD_DONATION_OFFER", max(confidence, 0.92)

        # Strong Emergency cues
        if any(em in lowered for em in ["emergency", "urgent need", "immediately", "starving", "flood victims", "sos"]):
            if "water" in lowered and entities.get("primary_category") == "WATER":
                return "WATER_REQUIREMENT", max(confidence, 0.95)
            if "grocery" in lowered or "ration" in lowered:
                return "GROCERY_REQUIREMENT", max(confidence, 0.95)
            return "EMERGENCY_FOOD_REQUEST", max(confidence, 0.95)

        # Shortage statement cues
        if any(s in lowered for s in ["food shortage", "ran out of food", "no meals left", "pantry is empty", "facing severe hunger"]):
            return "FOOD_SHORTAGE", max(confidence, 0.90)

        return intent, confidence

    def _determine_action(
        self,
        intent: str,
        is_complete: bool,
        priority_level: str,
        entities: Dict[str, Any]
    ) -> str:
        """Determines the immediate actionable recommendation for the client/orchestrator."""
        if not entities.get("is_valid_food") and entities.get("non_food_detected"):
            return "REJECT_NON_FOOD_INQUIRY"

        if intent == "UNKNOWN_OR_UNSUPPORTED":
            return "FALLBACK_PROMPT"

        if intent == "DONATION_CANCELLATION":
            return "CANCEL_TRANSACTION"

        if intent == "DONATION_STATUS_QUERY":
            return "LOOKUP_STATUS"

        if not is_complete:
            return "REQUEST_CLARIFICATION"

        if intent in ["EMERGENCY_FOOD_REQUEST", "FOOD_SHORTAGE"]:
            return "DISPATCH_EMERGENCY_RELIEF_MATCHING"

        if intent in ["FOOD_DONATION_OFFER", "GROCERY_DONATION", "WATER_DONATION"]:
            return "PREPARE_DONATION_LISTING"

        if intent in ["FOOD_DONATION_REQUEST", "GROCERY_REQUIREMENT", "WATER_REQUIREMENT"]:
            return "SEARCH_AVAILABLE_SUPPLIES"

        return "CONFIRM_DETAILS"


# Singleton instance
nlp_donation_pipeline = NLPDonationPipeline()
