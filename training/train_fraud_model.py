import os
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models", "fraud")
DATA_DIR = os.path.join(BASE_DIR, "data")

FEATURE_COLS = [
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

def generate_synthetic_fraud_dataset(n_samples=10000):
    """
    Generate realistic multi-variable telemetry data for training
    both unsupervised Isolation Forest and supervised fraud scoring.
    """
    np.random.seed(42)
    n_normal = int(n_samples * 0.94)
    n_fraud = n_samples - n_normal

    # 1. Normal Stakeholders (Legitimate restaurants, donors, individuals)
    normal_df = pd.DataFrame({
        'daily_donations': np.random.poisson(1.2, n_normal).clip(1, 6),
        'avg_quantity': np.random.normal(45, 25, n_normal).clip(5, 250),
        'max_quantity': np.random.normal(70, 35, n_normal).clip(10, 350),
        'cancellations': np.random.poisson(0.15, n_normal).clip(0, 2),
        'cancel_ratio': np.random.beta(1, 20, n_normal).clip(0.0, 0.25),
        'distance_variance': np.random.exponential(1.2, n_normal).clip(0.1, 15.0),
        'duplicate_ips': np.random.choice([0, 1], n_normal, p=[0.92, 0.08]),
        'image_reject_count': np.random.choice([0, 1], n_normal, p=[0.95, 0.05]),
        'account_age_days': np.random.uniform(10, 730, n_normal),
        'is_fraud': 0
    })

    # 2. Anomalous / Fraudulent Profiles
    # Subtype A: Phantom high-quantity food listings on new accounts
    n_a = int(n_fraud * 0.40)
    df_a = pd.DataFrame({
        'daily_donations': np.random.poisson(5, n_a).clip(2, 15),
        'avg_quantity': np.random.normal(3500, 1000, n_a).clip(800, 12000),
        'max_quantity': np.random.normal(6000, 1500, n_a).clip(1500, 15000),
        'cancellations': np.random.poisson(4, n_a).clip(2, 10),
        'cancel_ratio': np.random.uniform(0.40, 0.95, n_a),
        'distance_variance': np.random.exponential(25.0, n_a).clip(10.0, 120.0),
        'duplicate_ips': np.random.poisson(3, n_a).clip(1, 8),
        'image_reject_count': np.random.poisson(3, n_a).clip(1, 8),
        'account_age_days': np.random.uniform(0.1, 14.0, n_a),
        'is_fraud': 1
    })

    # Subtype B: Sybil bot ring / Account farming
    n_b = int(n_fraud * 0.35)
    df_b = pd.DataFrame({
        'daily_donations': np.random.poisson(12, n_b).clip(6, 35),
        'avg_quantity': np.random.normal(80, 40, n_b).clip(20, 400),
        'max_quantity': np.random.normal(150, 60, n_b).clip(50, 600),
        'cancellations': np.random.poisson(6, n_b).clip(3, 15),
        'cancel_ratio': np.random.uniform(0.35, 0.85, n_b),
        'distance_variance': np.random.exponential(45.0, n_b).clip(20.0, 200.0),
        'duplicate_ips': np.random.poisson(6, n_b).clip(3, 14),
        'image_reject_count': np.random.poisson(2, n_b).clip(0, 6),
        'account_age_days': np.random.uniform(0.5, 30.0, n_b),
        'is_fraud': 1
    })

    # Subtype C: Repeated fake claims / Diversion attempts
    n_c = n_fraud - n_a - n_b
    df_c = pd.DataFrame({
        'daily_donations': np.random.poisson(2, n_c).clip(0, 6),
        'avg_quantity': np.random.normal(500, 200, n_c).clip(100, 2000),
        'max_quantity': np.random.normal(900, 300, n_c).clip(200, 3000),
        'cancellations': np.random.poisson(8, n_c).clip(4, 20),
        'cancel_ratio': np.random.uniform(0.60, 1.0, n_c),
        'distance_variance': np.random.exponential(30.0, n_c).clip(15.0, 150.0),
        'duplicate_ips': np.random.poisson(2, n_c).clip(0, 5),
        'image_reject_count': np.random.poisson(4, n_c).clip(2, 10),
        'account_age_days': np.random.uniform(1.0, 60.0, n_c),
        'is_fraud': 1
    })

    full_df = pd.concat([normal_df, df_a, df_b, df_c]).sample(frac=1.0, random_state=42).reset_index(drop=True)
    return full_df

def train_and_export_fraud_models():
    print("=" * 60)
    print("Training AI Module 4: Fraud & Abuse Anomaly Detector")
    print("=" * 60)

    df = generate_synthetic_fraud_dataset(n_samples=10000)
    os.makedirs(DATA_DIR, exist_ok=True)
    csv_path = os.path.join(DATA_DIR, "fraud_synthetic_telemetry.csv")
    df.to_csv(csv_path, index=False)
    print(f"Generated {len(df)} telemetry records -> {csv_path}")

    X = df[FEATURE_COLS].copy()
    y = df['is_fraud'].copy()

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)

    # 1. Standard Scaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 2. Train Unsupervised Isolation Forest (Trained on inliers)
    print("\n[1/2] Training Isolation Forest for Outlier Detection...")
    normal_train = X_train_scaled[y_train == 0]
    iso_forest = IsolationForest(
        n_estimators=150,
        contamination=0.06,
        max_samples=256,
        random_state=42,
        n_jobs=-1
    )
    iso_forest.fit(normal_train)

    # Test outlier detection
    iso_preds = iso_forest.predict(X_test_scaled)
    # Map -1 (outlier) -> 1 (fraud), 1 (inlier) -> 0 (normal)
    iso_binary = np.where(iso_preds == -1, 1, 0)
    iso_acc = accuracy_score(y_test, iso_binary)
    print(f"Isolation Forest Outlier Alignment: {iso_acc * 100:.2f}%")

    # 3. Train Supervised Random Forest Classifier for Calibrated Risk Scoring
    print("\n[2/2] Training Random Forest Risk Classifier (150 trees)...")
    rf_fraud = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1
    )
    rf_fraud.fit(X_train, y_train)

    rf_preds = rf_fraud.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_preds)
    report = classification_report(y_test, rf_preds, target_names=["NORMAL", "FRAUD_ANOMALOUS"], output_dict=True)

    print(f"Random Forest Accuracy: {rf_acc * 100:.2f}%")
    print(classification_report(y_test, rf_preds, target_names=["NORMAL", "FRAUD_ANOMALOUS"]))

    # Feature Importance
    importances = dict(zip(FEATURE_COLS, [float(x) for x in rf_fraud.feature_importances_]))
    print("\nFeature Importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: x[1], reverse=True):
        print(f"  {feat:20s}: {imp * 100:.2f}%")

    # 4. Save Models & Artifacts
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(iso_forest, os.path.join(MODEL_DIR, "isolation_forest.joblib"))
    joblib.dump(rf_fraud, os.path.join(MODEL_DIR, "rf_fraud_classifier.joblib"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "fraud_scaler.joblib"))
    joblib.dump(FEATURE_COLS, os.path.join(MODEL_DIR, "fraud_features.joblib"))

    # Save metrics JSON
    metrics = {
        "model_version": "v2.0-ensemble-iforest-rf",
        "dataset_size": len(df),
        "test_size": len(X_test),
        "accuracy": round(float(rf_acc), 4),
        "isolation_forest_alignment": round(float(iso_acc), 4),
        "classification_report": report,
        "feature_importances": importances,
        "features": FEATURE_COLS
    }

    metrics_path = os.path.join(MODEL_DIR, "fraud_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nAll Fraud AI artifacts successfully saved to {MODEL_DIR}")
    print(f"Metrics saved to {metrics_path}")

if __name__ == "__main__":
    train_and_export_fraud_models()
