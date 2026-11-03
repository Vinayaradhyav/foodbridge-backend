import os
import joblib
import pandas as pd
import numpy as np

class PriorityPredictor:
    def __init__(self):
        self.model = None
        self.metadata = None
        self.model_version = "v1.0-rulebased"
        self._load_model()

    def _load_model(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        model_path = os.path.join(base_dir, 'models', 'priority_model.joblib')
        metadata_path = os.path.join(base_dir, 'models', 'model_metadata.joblib')

        if os.path.exists(model_path) and os.path.exists(metadata_path):
            try:
                self.model = joblib.load(model_path)
                self.metadata = joblib.load(metadata_path)
                self.model_version = self.metadata.get("model_version", "v1.0-ml")
                print(f"[PriorityPredictor] Successfully loaded ML priority model: {self.model_version}")
            except Exception as e:
                print(f"[PriorityPredictor] Error loading ML model, falling back to rules: {e}")
                self.model = None

    def predict(self, features: dict) -> dict:
        """
        Predicts emergency dispatch priority using ML pipeline with rule-informed constraints.
        Returns both 'priority' and 'priority_level' for multi-client compatibility.
        """
        # Ensure default values for missing inputs
        f = {
            'number_of_people': int(features.get('number_of_people', 50)),
            'requested_quantity': int(features.get('requested_quantity', 100)),
            'emergency_type': str(features.get('emergency_type', 'Relief Operation')),
            'urgency': str(features.get('urgency', 'HIGH')).upper(),
            'shortage': int(features.get('shortage', 50)),
            'deadline_hours': float(features.get('deadline_hours', 12.0)),
            'distance_km': float(features.get('distance_km', 5.0)),
            'available_food': int(features.get('available_food', 20)),
            'available_volunteers': int(features.get('available_volunteers', 5)),
            'available_vehicles': int(features.get('available_vehicles', 2)),
            'is_weather_related': bool(features.get('is_weather_related', False))
        }

        # Weather or disaster scale boost
        if f['is_weather_related'] or f['requested_quantity'] > 1000:
            f['urgency'] = 'CRITICAL'
            f['deadline_hours'] = min(f['deadline_hours'], 4.0)

        if self.model:
            try:
                return self._predict_ml(f)
            except Exception as e:
                print(f"[PriorityPredictor] ML prediction failed, using rules: {e}")
                return self._predict_rules(f)
        else:
            return self._predict_rules(f)

    def _predict_ml(self, f: dict) -> dict:
        expected_columns = self.metadata.get("features", [
            'number_of_people', 'requested_quantity', 'emergency_type', 'urgency',
            'shortage', 'deadline_hours', 'distance_km', 'available_food',
            'available_volunteers', 'available_vehicles'
        ])

        # Create DataFrame with required features
        df_row = {col: f.get(col, 0) for col in expected_columns}
        df = pd.DataFrame([df_row])[expected_columns]

        prediction = str(self.model.predict(df)[0]).upper()

        confidence = 0.90
        if hasattr(self.model, "predict_proba"):
            try:
                proba = self.model.predict_proba(df)[0]
                confidence = float(np.max(proba))
            except Exception:
                pass

        # Compute continuous priority score
        score_map = {"CRITICAL": 0.95, "HIGH": 0.78, "MEDIUM": 0.52, "LOW": 0.25}
        score = score_map.get(prediction, 0.60)

        # Build explanation
        reasons = []
        if f['is_weather_related']:
            reasons.append("Severe weather/disaster condition declared (+critical urgency)")
        if f['requested_quantity'] > 500:
            reasons.append(f"Large-scale relief requirement ({f['requested_quantity']} items)")
        if f['deadline_hours'] < 6:
            reasons.append(f"Urgent operational window (<{f['deadline_hours']}h remaining)")
        if f['number_of_people'] > 100:
            reasons.append(f"High population impact ({f['number_of_people']} people affected)")
        if not reasons:
            reasons.append(f"Standard priority allocation based on {f['emergency_type']} parameters")

        explanation = " | ".join(reasons)

        rec = "Immediate volunteer fleet mobilization advised." if prediction == "CRITICAL" else "Dispatch via standard priority queue."

        return {
            "priority": prediction,
            "priority_level": prediction,
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "explanation": explanation,
            "recommendation": rec,
            "model_version": self.model_version
        }

    def _predict_rules(self, f: dict) -> dict:
        score = 0
        reasons = []

        urgency = f.get('urgency', 'LOW').upper()
        if urgency == 'CRITICAL' or f.get('is_weather_related'):
            score += 45
            reasons.append("Critical urgency / Severe weather")
        elif urgency == 'HIGH':
            score += 30
            reasons.append("High urgency")
        elif urgency == 'MEDIUM':
            score += 15
        else:
            score += 5

        req_qty = f.get('requested_quantity', 1)
        shortage = f.get('shortage', 0)
        shortage_ratio = shortage / req_qty if req_qty > 0 else 0
        score += int(shortage_ratio * 25)

        deadline_hours = f.get('deadline_hours', 72)
        if deadline_hours < 4:
            score += 20
            reasons.append("Imminent deadline (<4 hours)")
        elif deadline_hours < 12:
            score += 15
        elif deadline_hours < 24:
            score += 10

        people = f.get('number_of_people', 10)
        if people > 1000:
            score += 15
            reasons.append("Massive scale (>1000 people)")
        elif people > 100:
            score += 10
            reasons.append("Large group (>100 people)")
        elif people > 50:
            score += 5

        if score >= 70:
            priority = 'CRITICAL'
            normalized_score = 0.95
        elif score >= 50:
            priority = 'HIGH'
            normalized_score = 0.78
        elif score >= 30:
            priority = 'MEDIUM'
            normalized_score = 0.50
        else:
            priority = 'LOW'
            normalized_score = 0.25

        explanation = " | ".join(reasons) if reasons else f"Score {score}/100 based on relief parameters"
        rec = "Rapid emergency mobilization required." if priority == "CRITICAL" else "Schedule for queue matching."

        return {
            "priority": priority,
            "priority_level": priority,
            "score": round(normalized_score, 2),
            "confidence": 0.88,
            "explanation": explanation,
            "recommendation": rec,
            "model_version": "v1.0-rulebased"
        }

predictor = PriorityPredictor()
