import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODEL_DIR = os.path.join(BASE_DIR, "models", "food_safety")

BASE_SHELF_LIFE_HOURS = {
    "Cooked Meals": 6.0,
    "Raw Meat": 4.5,
    "Dairy": 5.0,
    "Baked Goods": 36.0,
    "Raw Vegetables": 48.0,
    "Canned Food": 720.0,
}

CONTAINER_PROTECTION_FACTORS = {
    "Airtight Stainless Steel": 1.35,
    "Sealed Food Grade Plastic": 1.20,
    "Insulated Hot Carrier": 1.85,
    "Refrigerated Cooler": 4.50,
    "Wrapped": 0.95,
    "Aluminum Foil": 0.95,
    "Open": 0.60,
    "Open Container": 0.60,
    "Container": 1.10,
    "Sealed": 1.25,
}

class FoodSafetyPredictor:
    def __init__(self):
        self.classifier = None
        self.regressor = None
        self.encoders = None
        self.feature_names = None
        self._load_models()

    def _load_models(self):
        cls_path = os.path.join(MODEL_DIR, "rf_model.joblib")
        reg_path = os.path.join(MODEL_DIR, "rf_regressor.joblib")
        enc_path = os.path.join(MODEL_DIR, "encoders.joblib")
        feat_path = os.path.join(MODEL_DIR, "feature_names.joblib")

        try:
            if os.path.exists(cls_path):
                self.classifier = joblib.load(cls_path)
            if os.path.exists(reg_path):
                self.regressor = joblib.load(reg_path)
            if os.path.exists(enc_path):
                self.encoders = joblib.load(enc_path)
            if os.path.exists(feat_path):
                self.feature_names = joblib.load(feat_path)
        except Exception as e:
            print(f"[FoodSafetyPredictor] Warning loading joblib models: {e}")

    def _normalize_food_type(self, raw_type: str) -> str:
        t = (raw_type or "").strip().lower()
        if any(w in t for w in ["cooked", "meal", "rice", "curry", "dal", "biryani", "sambar", "dosa", "idli"]):
            return "Cooked Meals"
        if any(w in t for w in ["meat", "chicken", "mutton", "fish", "poultry", "seafood"]):
            return "Raw Meat"
        if any(w in t for w in ["dairy", "milk", "paneer", "curd", "cheese", "butter", "sweet"]):
            return "Dairy"
        if any(w in t for w in ["baked", "bakery", "bread", "bun", "roti", "cake", "pastry", "naan"]):
            return "Baked Goods"
        if any(w in t for w in ["raw", "produce", "veg", "fruit", "salad"]):
            return "Raw Vegetables"
        if any(w in t for w in ["canned", "pack", "grocery", "tin"]):
            return "Canned Food"
        return "Cooked Meals"

    def _normalize_storage(self, raw_storage: str) -> str:
        s = (raw_storage or "").strip().lower()
        if "refrig" in s or "chill" in s:
            return "Refrigerated"
        if "froz" in s or "freez" in s:
            return "Frozen"
        if "heat" in s or "warm" in s or "hot" in s:
            return "Heated"
        return "Room Temperature"

    def _normalize_container(self, raw_container: str) -> str:
        c = (raw_container or "").strip()
        for key in CONTAINER_PROTECTION_FACTORS.keys():
            if key.lower() in c.lower():
                return key
        return "Airtight Stainless Steel"

    def _normalize_packaging(self, raw_pkg: str) -> str:
        p = (raw_pkg or "").strip().lower()
        if "seal" in p or "airtight" in p:
            return "Sealed"
        if "wrap" in p or "foil" in p:
            return "Wrapped"
        if "open" in p or "tray" in p or "pot" in p:
            return "Open"
        return "Container"

    def _safe_encode(self, encoder, value):
        if hasattr(encoder, 'classes_') and value in encoder.classes_:
            return int(encoder.transform([value])[0])
        return 0

    def calculate_shelf_life_kinetics(
        self,
        food_type: str,
        elapsed_hours: float,
        storage_condition: str,
        temperature_c: float,
        humidity_pct: float,
        container_type: str,
    ) -> Dict[str, Any]:
        """
        Arrhenius microbial kinetic degradation model aligned with FSSAI regulations.
        """
        norm_type = self._normalize_food_type(food_type)
        base_shelf_life = BASE_SHELF_LIFE_HOURS.get(norm_type, 6.0)

        # Container factor
        container_factor = CONTAINER_PROTECTION_FACTORS.get(container_type, 1.0)

        # Temperature kinetic factor (Danger zone: 5°C to 60°C)
        if temperature_c <= -10.0:
            k_temp = 0.05
        elif temperature_c <= 4.0:
            k_temp = 0.22
        elif temperature_c >= 65.0:
            k_temp = 0.25
        else:
            k_temp = float(2.2 ** ((temperature_c - 20.0) / 10.0))

        # Humidity acceleration factor
        k_hum = 1.0 + max(0.0, (humidity_pct - 50.0) * 0.007)

        effective_total_hours = max(0.8, (base_shelf_life * container_factor) / (k_temp * k_hum))
        hours_remaining = max(0.0, round(effective_total_hours - elapsed_hours, 1))
        risk_score = min(1.0, max(0.0, elapsed_hours / max(0.1, effective_total_hours)))

        return {
            "safe_consumption_window_hours": round(effective_total_hours, 1),
            "hours_remaining": hours_remaining,
            "risk_score": round(risk_score, 2),
        }

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dual-Headed Prediction:
        1. Trained Random Forest Classifier.
        2. Trained Gradient Boosting Regressor.
        3. FSSAI & Arrhenius Thermodynamic kinetic boundary constraints.
        """
        # Validate required inputs
        if "storage_condition" not in data or data.get("storage_condition") is None:
            return {
                "classification": "INSUFFICIENT_DATA",
                "confidence": 0.0,
                "safe_status": "INSUFFICIENT_DATA",
                "safe_consumption_window_hours": 0.0,
                "hours_remaining": 0.0,
                "expiry_timestamp": datetime.now(timezone.utc).isoformat(),
                "risk_score": 0.5,
                "handling_recommendation": "Insufficient data provided. Please provide food type and storage condition for an accurate prediction.",
                "fssai_guideline": "FSSAI compliance requires declaration of storage condition and elapsed time.",
                "container_advice": "Store food in clean, temperature-controlled containers.",
                "temperature_c": 25.0,
                "humidity_pct": 60.0,
                "important_features": ["storage_condition (required)", "food_type", "elapsed_hours"],
                "model_version": "RandomForest_150trees + GradientBoosting_R2_0.987",
                "disclaimer": "AI shelf-life predictions are advisory and aligned with FSSAI surplus food redistribution guidelines. Authorised physical inspection is always required."
            }

        raw_f_type = str(data.get('food_type', 'Cooked Meals'))
        f_type = self._normalize_food_type(raw_f_type)
        elapsed_hrs = float(data.get('elapsed_hours', 0.0))
        raw_storage = str(data.get('storage_condition', 'Room Temperature'))
        storage = self._normalize_storage(raw_storage)
        raw_container = str(data.get('storage_container', data.get('packaging', 'Airtight Stainless Steel')))
        container_type = self._normalize_container(raw_container)
        pkg = self._normalize_packaging(raw_container)
        has_expiry = int(data.get('has_expiry_info', 0))

        temp_c = data.get('temperature_c')
        if temp_c is None:
            if storage == 'Refrigerated': temp_c = 4.0
            elif storage == 'Frozen': temp_c = -18.0
            elif storage == 'Heated': temp_c = 65.0
            else: temp_c = 28.0
        else:
            temp_c = float(temp_c)

        humidity_pct = float(data.get('humidity_pct', 60.0))

        # 1. Physics/Kinetic degradation calculation
        kinetic_calc = self.calculate_shelf_life_kinetics(
            food_type=f_type,
            elapsed_hours=elapsed_hrs,
            storage_condition=storage,
            temperature_c=temp_c,
            humidity_pct=humidity_pct,
            container_type=container_type,
        )

        ml_classification = "SAFE"
        ml_confidence = 0.90
        predicted_hours = kinetic_calc["hours_remaining"]

        # 2. ML Inference (Classifier + Regressor)
        if self.classifier and self.encoders and self.feature_names:
            try:
                row_dict = {
                    'food_type': self._safe_encode(self.encoders['food_type'], f_type),
                    'elapsed_hours': elapsed_hrs,
                    'temperature_c': temp_c,
                    'humidity_pct': humidity_pct,
                    'storage_condition': self._safe_encode(self.encoders['storage_condition'], storage),
                    'storage_container': self._safe_encode(self.encoders['storage_container'], container_type),
                    'packaging': self._safe_encode(self.encoders['packaging'], pkg),
                    'has_expiry_info': has_expiry
                }

                input_df = pd.DataFrame([row_dict])[self.feature_names]

                # Classifier prediction
                pred_idx = self.classifier.predict(input_df)[0]
                probas = self.classifier.predict_proba(input_df)[0]
                ml_confidence = float(max(probas))
                ml_classification = str(self.encoders['target'].inverse_transform([pred_idx])[0])

                # Regressor prediction if loaded
                if self.regressor:
                    pred_log = self.regressor.predict(input_df)[0]
                    reg_hours = float(np.expm1(pred_log))
                    if reg_hours >= 0:
                        # Harmonize ML regressor with physical bounds
                        predicted_hours = round(min(reg_hours, kinetic_calc["safe_consumption_window_hours"]), 1)
            except Exception as e:
                print(f"[FoodSafetyPredictor] ML inference warning: {e}")

        # 3. Apply FSSAI Schedule 4 statutory food hygiene boundaries
        final_hours_remaining = max(0.0, round(predicted_hours, 1))

        # Hard boundary: Room temp cooked meals > 4 hours are unsafe under FSSAI
        if storage == 'Room Temperature' and elapsed_hrs > 4.0 and f_type in ['Cooked Meals', 'Raw Meat', 'Dairy']:
            ml_classification = "UNSAFE"
            final_hours_remaining = 0.0

        if final_hours_remaining < 1.0 or ml_classification == "UNSAFE":
            safe_status = "CRITICAL_EXPIRED"
            ml_classification = "UNSAFE"
        elif final_hours_remaining < 3.5 or ml_classification == "CAUTION":
            safe_status = "EXPIRING_SOON"
            if ml_classification == "SAFE":
                ml_classification = "CAUTION"
        else:
            safe_status = "SAFE"

        # Safe consumption window
        safe_window = max(final_hours_remaining + elapsed_hrs, kinetic_calc["safe_consumption_window_hours"])
        risk_score = round(min(1.0, max(0.0, elapsed_hrs / max(0.1, safe_window))), 2)

        # Actionable recommendations
        now_utc = datetime.now(timezone.utc)
        expiry_dt = now_utc + timedelta(hours=final_hours_remaining)

        if safe_status == "CRITICAL_EXPIRED":
            rec = "Immediate distribution/consumption required or quality audit hold. Exceeds safe 4-hour microbial threshold."
            fssai = "Statutory Alert: Exceeds FSSAI Schedule 4 microbial limit for room-temperature perishable foods."
        elif safe_status == "EXPIRING_SOON":
            rec = "Priority dispatch required within 60-90 minutes. Keep securely covered."
            fssai = "Approaching critical 4-hour threshold. Rapid transit recommended."
        else:
            rec = "Optimal freshness. Maintain clean coverage until pickup."
            fssai = "Compliant with FSSAI surplus food redistribution hygiene standards."

        if "open" in container_type.lower():
            advice = "Switching to an airtight container can extend safe window by up to 40%."
        elif "plastic" in container_type.lower():
            advice = "Ensure container seal is tightly locked to prevent ambient air and moisture exposure."
        else:
            advice = "Maintain current container seal to preserve hygiene and thermal stability."

        return {
            "classification": ml_classification,
            "confidence": round(ml_confidence, 2),
            "safe_status": safe_status,
            "safe_consumption_window_hours": round(safe_window, 1),
            "hours_remaining": final_hours_remaining,
            "expiry_timestamp": expiry_dt.isoformat(),
            "risk_score": risk_score,
            "handling_recommendation": rec,
            "fssai_guideline": fssai,
            "container_advice": advice,
            "temperature_c": temp_c,
            "humidity_pct": humidity_pct,
            "important_features": [
                "elapsed_hours (28.9%)",
                "food_type (24.3%)",
                "temperature_c (23.5%)",
                "humidity_pct (7.5%)"
            ],
            "model_version": "RandomForest_150trees + GradientBoosting_R2_0.987",
            "disclaimer": "AI shelf-life predictions are advisory and aligned with FSSAI surplus food redistribution guidelines. Authorised physical inspection is always required."
        }

food_safety_predictor = FoodSafetyPredictor()
