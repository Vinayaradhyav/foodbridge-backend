import pytest
from app.nlp.rule_extractor import RuleBasedEmergencyExtractor
from app.models.emergency import EmergencyType, Urgency

def test_rule_based_extractor():
    extractor = RuleBasedEmergencyExtractor()
    
    sentences = [
        # 1. Complete sentence
        {
            "text": "Need 500 vegetarian meals for 200 people at a flood relief camp in Mysuru by 8 PM.",
            "expected": {
                "quantity": 500,
                "food_type": "vegetarian meals",
                "number_of_people": 200,
                "emergency_type": EmergencyType.FLOOD.value,
                "urgency": Urgency.HIGH.value, # Default if not specified explicitly
                "location": "A Flood Relief Camp In Mysuru"
            }
        },
        # 2. Incomplete/terse
        {
            "text": "Urgent! 50 water bottles in Chennai.",
            "expected": {
                "quantity": 50,
                "food_type": "water bottles",
                "urgency": Urgency.CRITICAL.value,
                "location": "Chennai"
            }
        },
        # 3. Earthquake, different wording
        {
            "text": "Send 1000 food packets for 500 survivors at the earthquake zone immediately.",
            "expected": {
                "quantity": 1000,
                "food_type": "food packets",
                "number_of_people": 500,
                "emergency_type": EmergencyType.EARTHQUAKE.value,
                "urgency": Urgency.CRITICAL.value,
                "location": "The Earthquake Zone"
            }
        },
        # 4. Fire
        {
            "text": "Fire in warehouse, need 200 meals ASAP",
            "expected": {
                "quantity": 200,
                "food_type": "meals",
                "emergency_type": EmergencyType.FIRE.value,
                "urgency": Urgency.HIGH.value,
                "location": "Warehouse"
            }
        },
        # 5. Cyclone with time
        {
            "text": "Cyclone hit coast. Need 300 groceries for 100 families by 10 AM.",
            "expected": {
                "quantity": 300,
                "food_type": "groceries",
                "number_of_people": 100,
                "emergency_type": EmergencyType.CYCLONE.value,
            }
        },
        # 6. Accident
        {
            "text": "Major train accident near station. 50 medical kits urgently.",
            "expected": {
                "quantity": 50,
                "food_type": "medical kits",
                "emergency_type": EmergencyType.ACCIDENT.value,
                "urgency": Urgency.CRITICAL.value,
                "location": "Station"
            }
        },
        # 7. No numbers
        {
            "text": "Flood warning at coastal village. Send help soon.",
            "expected": {
                "emergency_type": EmergencyType.FLOOD.value,
                "location": "Coastal Village",
                "urgency": Urgency.MEDIUM.value
            }
        },
        # 8. Large numbers
        {
            "text": "Tsunami warning. We need 50000 rations for 25000 people.",
            "expected": {
                "quantity": 50000,
                "food_type": "rations",
                "number_of_people": 25000,
                "emergency_type": EmergencyType.DISASTER.value
            }
        },
        # 9. Simple request
        {
            "text": "Need 10 boxes of food in Bangalore.",
            "expected": {
                "quantity": 10,
                "food_type": "boxes",
                "location": "Bangalore"
            }
        },
        # 10. Weird spacing
        {
            "text": "  earthquake   urgent   100 meals   for 50 people  ",
            "expected": {
                "quantity": 100,
                "food_type": "meals",
                "number_of_people": 50,
                "emergency_type": EmergencyType.EARTHQUAKE.value,
                "urgency": Urgency.CRITICAL.value
            }
        },
        # 11. Time in hours
        {
            "text": "Need 500 meals in 2 hours for flood victims.",
            "expected": {
                "quantity": 500,
                "food_type": "meals",
                "emergency_type": EmergencyType.FLOOD.value
            }
        },
        # 12. Only people
        {
            "text": "1000 people displaced by fire.",
            "expected": {
                "number_of_people": 1000,
                "emergency_type": EmergencyType.FIRE.value
            }
        },
        # 13. General disaster
        {
            "text": "Disaster at factory, need 100 food packets.",
            "expected": {
                "quantity": 100,
                "food_type": "food packets",
                "emergency_type": EmergencyType.DISASTER.value,
                "location": "Factory"
            }
        },
        # 14. Location with "at"
        {
            "text": "Stranded at airport, need 200 meals.",
            "expected": {
                "quantity": 200,
                "food_type": "meals",
                "location": "Airport"
            }
        },
        # 15. Location with "in"
        {
            "text": "Trapped in building fire. Need 50 water bottles.",
            "expected": {
                "quantity": 50,
                "food_type": "water bottles",
                "emergency_type": EmergencyType.FIRE.value,
                "location": "Building Fire"
            }
        },
        # 16. Fallback quantity
        {
            "text": "We need 500 for the flood camp.",
            "expected": {
                "quantity": 500,
                "emergency_type": EmergencyType.FLOOD.value
            }
        },
        # 17. Case insensitivity
        {
            "text": "EARTHQUAKE URGENT 500 MEALS IN DELHI",
            "expected": {
                "quantity": 500,
                "food_type": "meals",
                "emergency_type": EmergencyType.EARTHQUAKE.value,
                "urgency": Urgency.CRITICAL.value,
                "location": "Delhi"
            }
        },
        # 18. Plural and singular
        {
            "text": "1 person needs 1 meal urgently.",
            "expected": {
                "quantity": 1,
                "food_type": "meal",
                "number_of_people": 1,
                "urgency": Urgency.CRITICAL.value
            }
        },
        # 19. Missing everything but text
        {
            "text": "Please help us.",
            "expected": {
                "urgency": Urgency.HIGH.value # Default
            }
        },
        # 20. Another standard
        {
            "text": "Need 500 groceries near river bank.",
            "expected": {
                "quantity": 500,
                "food_type": "groceries",
                "location": "River Bank"
            }
        }
    ]
    
    for case in sentences:
        extracted = extractor.extract(case["text"])
        
        # Check all expected keys exist and match
        for key, expected_val in case["expected"].items():
            assert key in extracted, f"Key {key} missing in {extracted} for text: {case['text']}"
            # For food_type it might capture extra words, so we use 'in' check for simplicity
            if key == 'food_type':
                assert expected_val in extracted[key], f"Expected {expected_val} in {extracted[key]}"
            else:
                assert extracted[key] == expected_val, f"Expected {expected_val} but got {extracted[key]} for {key} in text: {case['text']}"
                
        # Assert confidence is calculated
        assert 'confidence' in extracted
        assert 0.0 <= extracted['confidence'] <= 1.0

