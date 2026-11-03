import pandas as pd
import numpy as np
import os
import json
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    confusion_matrix,
    r2_score,
    mean_absolute_error,
    mean_squared_error
)

def train_enhanced_models():
    data_path = "data/food_safety_synthetic.csv"
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found.")
        return
        
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} records from {data_path}")

    # Feature columns
    feature_cols = [
        'food_type',
        'elapsed_hours',
        'temperature_c',
        'humidity_pct',
        'storage_condition',
        'storage_container',
        'packaging',
        'has_expiry_info'
    ]
    
    X = df[feature_cols].copy()
    y_class = df['safety_status'].copy()
    y_reg = df['safe_hours_remaining'].copy()

    # Encode categorical variables
    categorical_cols = ['food_type', 'storage_condition', 'storage_container', 'packaging']
    encoders = {}
    
    for col in categorical_cols:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        encoders[col] = le

    # Encode classification target
    le_target = LabelEncoder()
    y_class_encoded = le_target.fit_transform(y_class)
    encoders['target'] = le_target
    
    # 80/20 Train Test Split (20,000 train, 5,000 test)
    X_train, X_test, y_train_cls, y_test_cls, y_train_reg, y_test_reg = train_test_split(
        X, y_class_encoded, y_reg, test_size=0.20, random_state=42, stratify=y_class_encoded
    )
    
    print(f"\n--- Training Phase ---")
    print(f"Train samples: {len(X_train)}, Test samples: {len(X_test)}")

    # 1. Train Random Forest Classifier
    print("\n[1/2] Training Random Forest Classifier (150 trees, max_depth=16)...")
    rf_classifier = RandomForestClassifier(
        n_estimators=150,
        max_depth=16,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1
    )
    rf_classifier.fit(X_train, y_train_cls)
    cls_preds = rf_classifier.predict(X_test)
    
    cls_acc = float(accuracy_score(y_test_cls, cls_preds))
    cls_report = classification_report(y_test_cls, cls_preds, target_names=le_target.classes_, output_dict=True)
    conf_mat = confusion_matrix(y_test_cls, cls_preds).tolist()
    
    print(f"Classifier Accuracy: {cls_acc * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test_cls, cls_preds, target_names=le_target.classes_))
    print("Confusion Matrix:")
    print(np.array(conf_mat))

    # 2. Train Gradient Boosting Regressor for Continuous Hours Remaining
    print("\n[2/2] Training Gradient Boosting Regressor for Shelf-Life Hours...")
    # Cap log-scaled targets to normalize variance for packaged foods vs cooked foods
    y_train_log = np.log1p(y_train_reg)
    y_test_log = np.log1p(y_test_reg)
    
    gb_regressor = GradientBoostingRegressor(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.08,
        random_state=42
    )
    gb_regressor.fit(X_train, y_train_log)
    reg_preds_log = gb_regressor.predict(X_test)
    reg_preds = np.expm1(reg_preds_log)
    reg_preds = np.clip(reg_preds, 0.0, None)
    
    r2 = float(r2_score(y_test_reg, reg_preds))
    r2_log = float(r2_score(y_test_log, reg_preds_log))
    mae = float(mean_absolute_error(y_test_reg, reg_preds))
    rmse = float(np.sqrt(mean_squared_error(y_test_reg, reg_preds)))
    
    print(f"Regressor R^2 Score (Log-normalized): {r2_log:.4f}")
    print(f"Regressor R^2 Score: {r2:.4f}")
    print(f"Regressor Mean Absolute Error (MAE): {mae:.2f} hours")
    print(f"Regressor Root Mean Squared Error (RMSE): {rmse:.2f} hours")

    # Feature Importance
    feature_importances = dict(zip(feature_cols, [float(x) for x in rf_classifier.feature_importances_]))
    print("\nClassifier Feature Importances:")
    for k, v in sorted(feature_importances.items(), key=lambda x: x[1], reverse=True):
        print(f"  {k:20s}: {v*100:.2f}%")

    # Save artifacts
    model_dir = "models/food_safety"
    os.makedirs(model_dir, exist_ok=True)
    
    joblib.dump(rf_classifier, os.path.join(model_dir, "rf_model.joblib"))
    joblib.dump(gb_regressor, os.path.join(model_dir, "rf_regressor.joblib"))
    joblib.dump(encoders, os.path.join(model_dir, "encoders.joblib"))
    joblib.dump(feature_cols, os.path.join(model_dir, "feature_names.joblib"))

    # Save JSON summary of training & evaluation
    eval_metrics = {
        "dataset_size": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "features": feature_cols,
        "classification": {
            "model_type": "RandomForestClassifier",
            "n_estimators": 150,
            "accuracy": round(cls_acc, 4),
            "confusion_matrix": conf_mat,
            "classes": list(le_target.classes_),
            "report": cls_report
        },
        "regression": {
            "model_type": "GradientBoostingRegressor",
            "n_estimators": 150,
            "r2_score_log": round(r2_log, 4),
            "r2_score": round(r2, 4),
            "mae_hours": round(mae, 2),
            "rmse_hours": round(rmse, 2)
        },
        "feature_importances": feature_importances
    }
    
    metrics_path = os.path.join(model_dir, "model_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(eval_metrics, f, indent=2)

    print(f"\nAll models and metrics successfully saved to {model_dir}/")
    print(f"Metrics JSON report saved to {metrics_path}")

if __name__ == "__main__":
    train_enhanced_models()
