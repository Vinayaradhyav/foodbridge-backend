"""
FoodBridge NLP V2 — Comprehensive Food, Grocery, Dairy & Beverage Ontology
Provides structured category mappings, item normalization, and non-food filtering.
"""
from typing import Dict, List, Set, Optional, Tuple

# Comprehensive Food Categories & Item Vocabularies
FOOD_ONTOLOGY: Dict[str, Dict[str, List[str]]] = {
    "COOKED_FOOD": {
        "Cooked Rice": ["rice", "steamed rice", "white rice", "boiled rice", "anna", "chawal", "bhat", "curd rice", "jeera rice", "fried rice", "lemon rice", "ghee rice"],
        "Biryani": ["biryani", "veg biryani", "chicken biryani", "mutton biryani", "dum biryani", "hyderabadi biryani", "pulao", "pulav"],
        "Roti & Chapati": ["roti", "chapati", "chapatis", "rotis", "phulka", "paratha", "parotta", "naan", "tandoori roti", "kulcha", "puri", "poori", "bhature"],
        "Dal & Sambar": ["dal", "sambar", "rasam", "saaru", "paruppu", "tadka dal", "dal makhani", "kootu", "curry", "gravy", "kurma"],
        "Vegetable Curry": ["sabzi", "sabji", "subji", "vegetable curry", "palya", "poriyal", "bhaji", "mixed veg curry", "paneer butter masala", "chole", "rajma"],
        "South Indian Breakfast": ["idli", "dosa", "vada", "upma", "pongal", "khichdi", "kesari bath", "rava idli", "masala dosa"],
        "Prepared Meals": ["meals", "full meals", "thali", "veg thali", "lunch plates", "dinner plates", "food packets", "cooked food", "packed lunch", "packed dinner", "bhojana", "khana", "oota"]
    },
    "GROCERIES": {
        "Rice Grains": ["rice bag", "raw rice", "sona masoori", "basmati rice", "boiled rice grain", "broken rice", "akki"],
        "Wheat & Flour": ["wheat", "wheat flour", "atta", "godhi hudi", "maida", "sooji", "rava", "semolina", "besan", "gram flour"],
        "Pulses & Lentils": ["dal", "toor dal", "moong dal", "urad dal", "chana dal", "masoor dal", "bengal gram", "lentils", "bele", "dal bag"],
        "Cooking Oil": ["oil", "cooking oil", "sunflower oil", "refined oil", "groundnut oil", "mustard oil", "vegetable oil", "edible oil", "oil packet", "oil can", "enne"],
        "Sugar & Salt": ["sugar", "jaggery", "salt", "table salt", "iodized salt", "bella", "sakkarai", "cheeni"],
        "Spices & Condiments": ["turmeric", "chilli powder", "coriander powder", "garam masala", "mustard seeds", "cumin seeds", "jeera", "pepper", "spices"],
        "Grocery Kit": ["grocery kit", "ration kit", "relief grocery kit", "dry ration", "essential ration", "food grain kit", "dry grocery pack", "ration bag"]
    },
    "WATER": {
        "Drinking Water Bottles": ["water bottle", "water bottles", "mineral water", "packaged water", "packaged drinking water", "bisleri", "aquafina", "kinley"],
        "Drinking Water Cans": ["water can", "water cans", "20l water can", "water jar", "drinking water can", "bubble top can"],
        "Water Packets": ["water packet", "water packets", "drinking water sachet", "water pouch", "water pouches"]
    },
    "PACKAGED_FOOD": {
        "Biscuits & Cookies": ["biscuits", "biscuit packets", "cookies", "marie gold", "glucose biscuits", "parle-g", "cream biscuits", "rusk"],
        "Bread & Bakery": ["bread", "bread loaf", "buns", "pav", "bakery buns", "sandwich bread", "toast"],
        "Ready-to-Eat Snacks": ["ready to eat", "instant noodles", "maggi", "poha", "cereals", "cornflakes", "snacks", "dry snacks", "namkeen"]
    },
    "DAIRY": {
        "Fresh Milk": ["milk", "milk packet", "pasteurized milk", "dairy milk", "cow milk", "buffalo milk", "haalu", "doodh"],
        "Curd & Yogurt": ["curd", "yogurt", "dahi", "buttermilk", "mosaru", "chaas", "lassi"],
        "Paneer & Butter": ["paneer", "cottage cheese", "butter", "cheese", "ghee", "clarified butter", "venne", "makhan"]
    },
    "FRUITS": {
        "Fresh Fruits": ["apple", "apples", "banana", "bananas", "orange", "oranges", "mango", "mangoes", "grapes", "papaya", "watermelon", "guava", "pomegranate", "fresh fruits", "fruit basket"]
    },
    "VEGETABLES": {
        "Fresh Vegetables": ["potato", "potatoes", "onion", "onions", "tomato", "tomatoes", "carrot", "carrots", "cabbage", "cauliflower", "beans", "green beans", "capsicum", "green chillies", "ginger", "garlic", "spinach", "leafy vegetables", "fresh vegetables", "tarkari"]
    },
    "BABY_FOOD": {
        "Infant Nutrition": ["baby food", "infant formula", "cerelac", "baby milk powder", "lactogen", "nestum", "weaning food"]
    }
}

# Non-food items blacklist to reject false positives
NON_FOOD_TERMS: Set[str] = {
    "laptop", "computer", "phone", "mobile", "charger", "cable", "electronics",
    "table", "chair", "bed", "furniture", "clothes", "dress", "shirt", "pants",
    "shoes", "slippers", "plastic", "paper", "book", "pen", "pencil", "cardboard",
    "medicine", "tablet", "syrup", "medical kit", "blanket", "tarpaulin", "utensil",
    "vehicle", "bike", "car", "van", "truck", "generator", "money", "cash", "cheque"
}

# Standardized Units Mapping
UNIT_SYNONYMS: Dict[str, str] = {
    "meal": "meals",
    "meals": "meals",
    "plate": "meals",
    "plates": "meals",
    "thali": "meals",
    "thalis": "meals",
    "portion": "meals",
    "portions": "meals",
    "packet": "packets",
    "packets": "packets",
    "pkt": "packets",
    "pkts": "packets",
    "box": "boxes",
    "boxes": "boxes",
    "bag": "bags",
    "bags": "bags",
    "sack": "bags",
    "sacks": "bags",
    "kit": "kits",
    "kits": "kits",
    "can": "cans",
    "cans": "cans",
    "bottle": "bottles",
    "bottles": "bottles",
    "loaf": "loaves",
    "loaves": "loaves",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "kilo": "kg",
    "g": "grams",
    "gm": "grams",
    "gms": "grams",
    "gram": "grams",
    "grams": "grams",
    "l": "litres",
    "lt": "litres",
    "ltr": "litres",
    "ltrs": "litres",
    "liter": "litres",
    "liters": "litres",
    "litre": "litres",
    "litres": "litres",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "person": "people",
    "people": "people",
    "individual": "people",
    "individuals": "people",
    "survivor": "people",
    "survivors": "people",
    "victim": "people",
    "victims": "people",
    "family": "families",
    "families": "families",
}

class FoodOntologyEngine:
    """Provides high-speed lookup and categorization for food, grocery and beverage entities."""

    _lookup_cache: Dict[str, Tuple[str, str]] = {}

    @classmethod
    def _initialize_cache(cls):
        if cls._lookup_cache:
            return
        for category, items_dict in FOOD_ONTOLOGY.items():
            for standard_name, synonyms in items_dict.items():
                cls._lookup_cache[standard_name.lower()] = (category, standard_name)
                for syn in synonyms:
                    cls._lookup_cache[syn.lower()] = (category, standard_name)

    @classmethod
    def lookup_item(cls, term: str) -> Optional[Tuple[str, str]]:
        cls._initialize_cache()
        t = term.lower().strip()
        if t in NON_FOOD_TERMS:
            return None
        if t in cls._lookup_cache:
            return cls._lookup_cache[t]
        # Partial containment check
        for syn, result in cls._lookup_cache.items():
            if syn in t or t in syn:
                return result
        return None

    @classmethod
    def normalize_unit(cls, raw_unit: str) -> str:
        u = raw_unit.lower().strip().rstrip('.,s')
        if raw_unit.lower() in UNIT_SYNONYMS:
            return UNIT_SYNONYMS[raw_unit.lower()]
        return UNIT_SYNONYMS.get(u, raw_unit.lower())

    @classmethod
    def is_non_food(cls, term: str) -> bool:
        t = term.lower().strip()
        return any(nft in t for nft in NON_FOOD_TERMS)

# Top-level helper functions for clean importing
def get_food_category(term: str) -> Optional[Tuple[str, str]]:
    return FoodOntologyEngine.lookup_item(term)

def is_non_food(term: str) -> bool:
    return FoodOntologyEngine.is_non_food(term)

