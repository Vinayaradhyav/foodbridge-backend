import os
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score

def train_and_evaluate():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_path = os.path.join(base_dir, 'data', 'synthetic_emergencies.csv')
    models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    # 1. Load Data
    print(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)
    
    # Target and Features
    X = df.drop(columns=['true_priority'])
    y = df['true_priority']
    
    # 2. Preprocessing Pipeline
    categorical_features = ['emergency_type', 'urgency']
    numerical_features = [
        'number_of_people', 'requested_quantity', 'shortage', 
        'deadline_hours', 'distance_km', 'available_food', 
        'available_volunteers', 'available_vehicles'
    ]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numerical_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
        ])
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 3. Define Models
    models = {
        'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
        'HistGradientBoosting': HistGradientBoostingClassifier(random_state=42)
    }
    
    best_model = None
    best_score = 0
    best_name = ""
    best_pipeline = None
    
    print("\n--- Training and Evaluation ---")
    for name, model in models.items():
        pipeline = Pipeline(steps=[('preprocessor', preprocessor),
                                   ('classifier', model)])
        
        print(f"\nTraining {name}...")
        pipeline.fit(X_train, y_train)
        
        y_pred = pipeline.predict(X_test)
        score = f1_score(y_test, y_pred, average='weighted')
        
        print(f"{name} F1 Score: {score:.4f}")
        print(classification_report(y_test, y_pred))
        
        if score > best_score:
            best_score = score
            best_model = pipeline
            best_name = name
            
    print(f"\nBest Model: {best_name} with F1 Score: {best_score:.4f}")
    
    # 4. Save Model
    model_path = os.path.join(models_dir, 'priority_model.joblib')
    joblib.dump(best_model, model_path)
    print(f"Model saved to {model_path}")
    
    # Save a metadata file
    metadata = {
        "model_version": f"v1.0-{best_name.lower().replace(' ', '')}",
        "features": list(X.columns),
        "f1_score": float(best_score)
    }
    joblib.dump(metadata, os.path.join(models_dir, 'model_metadata.joblib'))
    
if __name__ == "__main__":
    train_and_evaluate()
