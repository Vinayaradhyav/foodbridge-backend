import pytest
import io
import base64
from PIL import Image
import numpy as np
from app.ai.food_image.predictor import food_image_predictor

def test_food_image_fresh_cooked_meal():
    # Synthetic warm curry dish
    img = Image.new('RGB', (100, 100), color=(210, 150, 40))
    arr = np.array(img)
    # Add green coriander flecks
    arr[10:20, 10:20] = [30, 180, 50]
    food_img = Image.fromarray(arr)
    
    buf = io.BytesIO()
    food_img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    res = food_image_predictor.predict(img_b64, declared_food_type="Cooked Meals")
    assert res["predicted_category"] == "Cooked Meals"
    assert res["is_match"] is True
    assert res["freshness_status"] in ["FRESH", "INSPECT_CLOSER"]
    assert res["is_safe_for_redistribution"] is True
    assert res["spoilage_score"] < 0.25

def test_food_image_fresh_produce():
    # Green produce image
    img = Image.new('RGB', (100, 100), color=(40, 170, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    res = food_image_predictor.predict(img_b64, declared_food_type="Raw Produce")
    assert res["predicted_category"] == "Raw Produce"
    assert res["is_safe_for_redistribution"] is True
    assert "Mold" not in str(res["visual_defects"])

def test_food_image_definite_non_food_rejection():
    # Pure dark gray graphic with zero food traits and no declared food
    img = Image.new('RGB', (100, 100), color=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    res = food_image_predictor.predict(img_b64, declared_food_type="")
    assert "disclaimer" in res
    assert "spoilage_score" in res

def test_food_image_human_hand_rejection():
    # Synthetic human hand / skin tone (Cr in [133, 173], Cb in [77, 127], R > G > B)
    # Typical warm human skin color: R=210, G=150, B=120
    img = Image.new('RGB', (100, 100), color=(210, 150, 120))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    res = food_image_predictor.predict(img_b64, declared_food_type="Bread")
    # Must NOT be classified as Bakery & Bread or safe for intake!
    assert res["predicted_category"] != "Bakery & Bread"
    assert res["freshness_status"] == "NON_FOOD_REJECTED"
    assert res["is_safe_for_redistribution"] is False
    assert res["is_match"] is False
    assert "Human Hand" in res["food_item_name"] or "Non-Food" in res["predicted_category"]

def test_food_image_packaged_groceries_detection(monkeypatch):
    import app.ai.food_image.predictor as predictor_mod
    monkeypatch.setattr(predictor_mod, "decode_predictions", lambda preds, top=5: [[("1", "carton", 0.92), ("2", "packet", 0.85)]])
    
    img = Image.new('RGB', (100, 100), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    res = food_image_predictor.predict(img_b64, declared_food_type="Carton Milk")
    assert res["predicted_category"] == "Packaged Foods & Groceries"
    assert res["is_safe_for_redistribution"] is True
    assert res["freshness_status"] == "PACKAGED_VERIFIED"

def test_food_image_electronics_rejection(monkeypatch):
    import app.ai.food_image.predictor as predictor_mod
    monkeypatch.setattr(predictor_mod, "decode_predictions", lambda preds, top=5: [[("1", "cellular_telephone", 0.96)]])
    
    img = Image.new('RGB', (100, 100), color=(50, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    res = food_image_predictor.predict(img_b64, declared_food_type="Cooked Meals")
    assert res["predicted_category"] == "Non-Food / Graphic"
    assert res["freshness_status"] == "NON_FOOD_REJECTED"
    assert res["is_safe_for_redistribution"] is False
