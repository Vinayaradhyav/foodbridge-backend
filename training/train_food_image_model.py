import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2  # type: ignore
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout  # type: ignore
from tensorflow.keras.models import Model  # type: ignore
from tensorflow.keras.preprocessing.image import ImageDataGenerator  # type: ignore
from PIL import Image
import json
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix

# Categories
CATEGORIES = ['Rice', 'Curry', 'Bread', 'Vegetables', 'Fruits', 'Cooked Meals', 'Packaged Food', 'Groceries', 'Other']
DATA_DIR = 'data/synthetic_food_images'
MODEL_DIR = 'models/food_image'
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 2

def create_synthetic_dataset():
    """Create a dummy dataset with solid colors so the pipeline can be tested without downloading 10GB of images."""
    print("Creating synthetic image dataset for testing the pipeline...")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Generate 10 images per category
    for i, category in enumerate(CATEGORIES):
        cat_dir = os.path.join(DATA_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        
        # Color based on category index
        color = ( (i*30)%255, (i*50)%255, (i*80)%255 )
        for j in range(10):
            img_path = os.path.join(cat_dir, f"img_{j}.jpg")
            if not os.path.exists(img_path):
                img = Image.new('RGB', IMAGE_SIZE, color=color)
                # Add some random noise
                noise = np.random.randint(0, 50, (224, 224, 3), dtype=np.uint8)
                img = Image.fromarray(np.clip(np.array(img) + noise, 0, 255).astype(np.uint8))
                img.save(img_path)

def build_model(num_classes):
    print("Building Transfer Learning Model (MobileNetV2)...")
    base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
    
    # Freeze base model
    base_model.trainable = False
    
    # Add custom head
    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(128, activation='relu')(x)
    x = Dropout(0.2)(x)
    predictions = Dense(num_classes, activation='softmax')(x)
    
    model = Model(inputs=base_model.input, outputs=predictions)
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    return model

def train_and_export():
    create_synthetic_dataset()
    
    # 1. Dataset Loader & Augmentation
    datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        horizontal_flip=True,
        validation_split=0.2
    )
    
    train_generator = datagen.flow_from_directory(
        DATA_DIR,
        target_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training'
    )
    
    val_generator = datagen.flow_from_directory(
        DATA_DIR,
        target_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation'
    )
    
    class_indices = train_generator.class_indices
    # Save class mapping
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, 'class_indices.json'), 'w') as f:
        json.dump(class_indices, f)
        
    # 2. Build Model
    model = build_model(num_classes=len(CATEGORIES))
    
    # 3. Train
    print("Starting training...")
    history = model.fit(
        train_generator,
        epochs=EPOCHS,
        validation_data=val_generator
    )
    
    # 4. Save Model
    model_path = os.path.join(MODEL_DIR, 'mobilenet_classifier.h5')
    model.save(model_path)
    print(f"Model saved to {model_path}")
    
    # 5. Confusion Matrix (Evaluation on validation data)
    print("Evaluating...")
    val_generator.reset()
    predictions = model.predict(val_generator)
    y_pred = np.argmax(predictions, axis=1)
    y_true = val_generator.classes
    
    print("\nClassification Report:")
    # Using real class names
    labels = list(class_indices.keys())
    print(classification_report(y_true, y_pred, target_names=labels, zero_division=0))

if __name__ == "__main__":
    train_and_export()
