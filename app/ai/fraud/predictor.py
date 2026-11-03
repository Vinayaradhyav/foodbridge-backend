import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODEL_DIR = os.path.join(BASE_DIR, "models", "fraud")

DEFAULT_FEATURES = [
    'daily_donations',
    'avg_quantity',
    'max_quantity',
    'cancellations',
    'cancel_ratio',
    'distance_variance',
    'duplicate_ips',
    'image_reject_count',
    'account_age_days'
]

class FraudPredictor:
    def __init__(self):
        self.iso_model = None
        self.rf_classifier = None
        self.scaler = None
        self.features = DEFAULT_FEATURES
        self.model_version = "v2.0-ensemble-iforest-rf"
        self._load_models()

    def _load_models(self):
        iso_path = os.path.join(MODEL_DIR, "isolation_forest.joblib")
        rf_path = os.path.join(MODEL_DIR, "rf_fraud_classifier.joblib")
        scaler_path = os.path.join(MODEL_DIR, "fraud_scaler.joblib")
        feat_path = os.path.join(MODEL_DIR, "fraud_features.joblib")

        try:
            if os.path.exists(iso_path):
                self.iso_model = joblib.load(iso_path)
            if os.path.exists(rf_path):
                self.rf_classifier = joblib.load(rf_path)
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
            if os.path.exists(feat_path):
                self.features = joblib.load(feat_path)
            print("[FraudPredictor] AI Module 4 models successfully loaded.")
        except Exception as e:
            print(f"[FraudPredictor] Notice: Model loading warning ({e}). Running hybrid rule engine.")

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI Module 4: Fraud & Abuse Anomaly Analysis.
        Combines Unsupervised Outlier Detection (Isolation Forest),
        Supervised Calibrated Classifier (Random Forest), and Hard Rule Guards.
        """
        reasons: List[str] = []
        rule_risk = 0

        # Extract features with safe numeric normalization
        daily_donations = int(data.get('daily_donations', 1))
        avg_quantity = float(data.get('avg_quantity', 45.0))
        max_quantity = float(data.get('max_quantity', max(avg_quantity, float(data.get('quantity', 45.0)))))
        cancellations = int(data.get('cancellations', 0))
        cancel_ratio = float(data.get('cancel_ratio', 0.0))
        if cancellations > 0 and cancel_ratio == 0.0:
            cancel_ratio = min(1.0, cancellations / max(1, daily_donations + cancellations))

        distance_variance = float(data.get('distance_variance', 1.0))
        duplicate_ips = int(data.get('duplicate_ips', 0))
        image_reject_count = int(data.get('image_reject_count', 0))
        account_age_days = float(data.get('account_age_days', 30.0))

        # 1. Deterministic Expert Rule Constraints
        if max_quantity > 5000:
            reasons.append("Extremely high quantity per donation (>5000 items).")
            rule_risk += 40
        elif avg_quantity > 2000 and account_age_days < 7:
            reasons.append("Abnormally large listing quantity (>2000) on a brand new account.")
            rule_risk += 35

        if cancellations > 3 or cancel_ratio > 0.40:
            reasons.append(f"High cancellation frequency ({cancellations} cancels, {round(cancel_ratio * 100)}% ratio).")
            rule_risk += 30

        if duplicate_ips > 1:
            reasons.append(f"Multiple accounts detected operating on the same IP ({duplicate_ips} accounts).")
            rule_risk += 30

        if distance_variance > 20.0:
            reasons.append("Unusual geographic velocity variance / location hopping.")
            rule_risk += 25

        if daily_donations > 10:
            reasons.append("Abnormal spike in daily donation transaction volume.")
            rule_risk += 20

        if image_reject_count >= 2:
            reasons.append(f"Repeated image inspection rejections ({image_reject_count} failed uploads).")
            rule_risk += 20

        # 2. Machine Learning Anomaly Detection
        ml_risk = 0
        ml_confidence = 0.85
        is_outlier = False

        if self.rf_classifier and self.scaler and self.iso_model:
            try:
                row_dict = {
                    'daily_donations': daily_donations,
                    'avg_quantity': avg_quantity,
                    'max_quantity': max_quantity,
                    'cancellations': cancellations,
                    'cancel_ratio': cancel_ratio,
                    'distance_variance': distance_variance,
                    'duplicate_ips': duplicate_ips,
                    'image_reject_count': image_reject_count,
                    'account_age_days': account_age_days
                }

                input_df = pd.DataFrame([row_dict])[self.features]
                scaled_df = self.scaler.transform(input_df)

                # Isolation Forest Outlier Check (-1 = outlier, 1 = inlier)
                iso_pred = self.iso_model.predict(scaled_df)[0]
                if iso_pred == -1:
                    is_outlier = True
                    reasons.append("Unsupervised AI (Isolation Forest) flagged transaction telemetry as an outlier.")
                    ml_risk += 35

                # Random Forest Supervised Classifier
                rf_proba = self.rf_classifier.predict_proba(input_df)[0]
                fraud_prob = float(rf_proba[1])
                ml_confidence = float(np.max(rf_proba))
                ml_risk += int(fraud_prob * 65)

            except Exception as ex:
                print(f"[FraudPredictor] ML inference warning: {ex}")
                ml_risk = rule_risk

        # 3. Ensemble Synthesis
        # Harmonize rule risk and ML risk
        if self.rf_classifier:
            final_risk = int(min(100, max(rule_risk, ml_risk)))
        else:
            final_risk = int(min(100, rule_risk))

        # Classification mapping
        if final_risk >= 70:
            classification = "HIGH_RISK"
            action = "SUSPEND_OR_MANUAL_AUDIT"
        elif final_risk >= 30:
            classification = "SUSPICIOUS"
            action = "WARN_AND_VERIFY"
        else:
            classification = "NORMAL"
            action = "ALLOW"

        return {
            "classification": classification,
            "risk_score": final_risk,
            "confidence": round(ml_confidence, 2),
            "is_outlier": is_outlier,
            "reasons": reasons,
            "action_recommended": action,
            "model_version": self.model_version,
            "feature_summary": {
                "daily_donations": daily_donations,
                "avg_quantity": round(avg_quantity, 1),
                "cancellations": cancellations,
                "cancel_ratio_pct": round(cancel_ratio * 100, 1),
                "distance_variance_km": round(distance_variance, 1),
                "duplicate_ips": duplicate_ips
            }
        }

    def evaluate_donation(self, donation: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Real-time risk assessment for an individual donation listing.
        Flags phantom listings, suspicious spikes, or fake food posts.
        """
        user_p = user_profile or {}
        qty = float(donation.get("quantity", 10.0))
        food_type = str(donation.get("food_type", "Cooked Meals"))
        donor_donations = int(user_p.get("total_donations", 1))
        cancellations = int(user_p.get("cancellations", 0))

        risk_score = 5
        reasons = []

        if qty > 5000:
            risk_score += 75
            reasons.append(f"Unusually large donation ({int(qty)} meals). Exceeds typical institutional capacity.")
        elif qty > 1000 and donor_donations < 2:
            risk_score += 50
            reasons.append("First-time donor posting over 1,000 meals without verified organizational credentials.")

        if cancellations >= 3:
            risk_score += 25
            reasons.append(f"Donor has {cancellations} recent unfulfilled cancellations.")

        if "suspicious" in str(donation.get("special_instructions", "")).lower():
            risk_score += 20
            reasons.append("Special instructions contain flagged keywords.")

        risk_score = min(100, risk_score)

        if risk_score >= 70:
            level = "HIGH_RISK"
            flagged = True
        elif risk_score >= 35:
            level = "SUSPICIOUS"
            flagged = True
        else:
            level = "NORMAL"
            flagged = False

        return {
            "is_flagged": flagged,
            "risk_level": level,
            "risk_score": risk_score,
            "reasons": reasons,
            "requires_admin_review": risk_score >= 50,
            "model_version": self.model_version
        }

fraud_predictor = FraudPredictor()
