import os
import sys
import json
import joblib
import pandas as pd
import numpy as np

# Ensure Unicode characters print correctly on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score, f1_score

def train_multilingual_chatbot():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'data', 'multilingual_nlp_dataset.csv')
    models_dir = os.path.join(base_dir, 'models', 'chatbot')
    os.makedirs(models_dir, exist_ok=True)

    print(f"Loading Multilingual NLP Dataset from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} samples across languages: {df['language'].unique().tolist()}")
    print(f"Unique intents: {df['intent'].unique().tolist()}")

    # Fill NaN values
    df['text'] = df['text'].fillna('').astype(str)
    
    # Train/Test Split (80/20)
    X = df['text']
    y = df['intent']
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Training samples: {len(X_train)} | Test samples: {len(X_test)}")

    # High-Performance Multilingual Character-Word N-gram Pipeline
    # Char-WB 2-5 ngrams captures root morphemes across Kannada, Hindi, Tamil, Telugu & English
    vectorizer = TfidfVectorizer(
        analyzer='char_wb',
        ngram_range=(2, 5),
        min_df=2,
        sublinear_tf=True
    )

    base_sgd = SGDClassifier(
        loss='log_loss',
        penalty='elasticnet',
        alpha=1e-5,
        max_iter=1000,
        random_state=42
    )

    pipeline = Pipeline([
        ('vectorizer', vectorizer),
        ('classifier', base_sgd)
    ])

    print("Training Multilingual NLP Intent Classifier...")
    pipeline.fit(X_train, y_train)

    print("Evaluating model performance on held-out test set...")
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)

    acc = accuracy_score(y_test, y_pred)
    weighted_f1 = f1_score(y_test, y_pred, average='weighted')
    report = classification_report(y_test, y_pred, output_dict=True)

    print(f"\n==========================================")
    print(f"AI Module 5 Test Accuracy: {acc * 100:.2f}%")
    print(f"Weighted F1-Score: {weighted_f1:.4f}")
    print(f"==========================================\n")
    print(classification_report(y_test, y_pred))

    # Save Pipeline and Vectorizer
    model_save_path = os.path.join(models_dir, 'nlp_intent_model.joblib')
    vectorizer_save_path = os.path.join(models_dir, 'nlp_vectorizer.joblib')
    metrics_save_path = os.path.join(models_dir, 'model_metrics.json')

    joblib.dump(pipeline, model_save_path)
    joblib.dump(vectorizer, vectorizer_save_path)
    print(f"Saved trained pipeline to: {model_save_path}")
    print(f"Saved vectorizer to: {vectorizer_save_path}")

    # Metrics Export
    metrics = {
        "module": "AI Module 5: Multilingual NLP Emergency & Chatbot Engine",
        "model_architecture": "Calibrated SGD Classifier with Char-WB TF-IDF (2-5 grams)",
        "test_accuracy": float(acc),
        "weighted_f1_score": float(weighted_f1),
        "training_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "supported_languages": ["en", "kn", "hi", "ta", "te"],
        "language_names": {
            "en": "English",
            "kn": "Kannada",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu"
        },
        "per_class_metrics": {k: v for k, v in report.items() if isinstance(v, dict)}
    }

    with open(metrics_save_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"Saved metrics metadata to: {metrics_save_path}")

    # Verify predictions on all 5 languages
    test_phrases = [
        ("ಹೆಚ್ಚುವರಿ ಆಹಾರವನ್ನು ದಾನ ಮಾಡುವುದು ಹೇಗೆ?", "kn"),
        ("खाने की शेल्फ लाइफ और एफएसएसएआई नियम क्या हैं?", "hi"),
        ("அவசரம்! வெள்ளத்தால் பாதிக்கப்பட்ட 100 பேருக்கு உணவு வேண்டும்", "ta"),
        ("వాలంటీర్‌గా ఎలా నమోదు చేసుకోవాలి?", "te"),
        ("Where is my active food donation delivery?", "en")
    ]

    print("\n--- Live Multilingual Validation ---")
    for phrase, lang in test_phrases:
        pred = pipeline.predict([phrase])[0]
        prob = np.max(pipeline.predict_proba([phrase]))
        print(f"[{lang.upper()}] '{phrase}' -> Predicted: {pred} (Confidence: {prob*100:.1f}%)")

if __name__ == '__main__':
    train_multilingual_chatbot()
