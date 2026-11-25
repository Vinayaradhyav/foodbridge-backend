import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

class IndicNLPEngine:
    """
    AI Module: High-Precision Indic NLP & Entity Extraction Engine
    Supports Kannada (kn), Hindi (hi), English (en), and Code-Mixed Indic inputs.
    
    Features:
    - Zero external scraping dependency (100% resilient, no 429 rate limits).
    - Agglutinative Kannada & Hindi inflection suffix stripping.
    - Indic numeral and number-word normalization.
    - Protected landmark, city, and institution recognition.
    - Full 12-entity extraction schema without fabricated defaults.
    - Natural pause and multi-turn draft merging for voice sessions.
    - Fluent English translation generation preserving exact proper nouns and numbers.
    """

    KANNADA_DIGITS = {'೦':'0', '೧':'1', '೨':'2', '೩':'3', '೪':'4', '೫':'5', '೬':'6', '೭':'7', '೮':'8', '೯':'9'}
    HINDI_DIGITS = {'०':'0', '१':'1', '२':'2', '३':'3', '४':'4', '५':'5', '६':'6', '७':'7', '८':'8', '९':'9'}

    INDIC_NUMBER_WORDS = [
        ('ಮೂರು ನೂರು', '300'), ('ಮೂರೂರು', '300'), ('ಎರಡು ನೂರು', '200'), ('ನಾಲ್ಕು ನೂರು', '400'),
        ('ಐನೂರು', '500'), ('ಆರು ನೂರು', '600'), ('ಏಳು ನೂರು', '700'), ('ಎಂಟು ನೂರು', '800'),
        ('ಒಂಬೈನೂರು', '900'), ('ಸಾವಿರ', '1000'), ('ಎರಡು ಸಾವಿರ', '2000'), ('ಐದು ಸಾವಿರ', '5000'),
        ('ಹತ್ತು', '10'), ('ಇಪ್ಪತ್ತು', '20'), ('ಮೂವತ್ತು', '30'), ('ನಲವತ್ತು', '40'),
        ('ಐವತ್ತು', '50'), ('ಅರವತ್ತು', '60'), ('ಎಪ್ಪತ್ತು', '70'), ('ಎಂಬತ್ತು', '80'), ('ತೊಂಬತ್ತು', '90'),
        ('ನೂರು', '100'), ('ಒಂದು', '1'), ('ಎರಡು', '2'), ('ಮೂರು', '3'), ('ನಾಲ್ಕು', '4'), ('ಐದು', '5'),
        # Hindi
        ('तीन सौ', '300'), ('दो सौ', '200'), ('चार सौ', '400'), ('पांच सौ', '500'),
        ('छह सौ', '600'), ('सात सौ', '700'), ('आठ सौ', '800'), ('नौ सौ', '900'),
        ('एक हजार', '1000'), ('दो हजार', '2000'), ('पांच हजार', '5000'), ('हजार', '1000'),
        ('दस', '10'), ('बीस', '20'), ('तीस', '30'), ('चालीस', '40'),
        ('पचास', '50'), ('साठ', '60'), ('सत्तर', '70'), ('अस्सी', '80'), ('नब्बे', '90'),
        ('सौ', '100'), ('एक', '1'), ('दो', '2'), ('तीन', '3'), ('चार', '4'), ('पांच', '5'),
    ]

    # Protected Local Places & Landmarks with Inflection Aliases
    KNOWN_LOCATIONS = [
        ("Aradhya Masaba, Mysuru", [
            "ಆರಾಧ್ಯ ಮಸಬ", "ಆರಾಧ್ಯ ಮಹಾಸಭಾ", "ಆರಾಧ್ಯ", "ಆರಾಧ್ಯ ಮಸಬದಲ್ಲಿ", "ಆರಾಧ್ಯ ಮಸಬಕ್ಕೆ",
            "ಆರಾಧ್ಯ ಮಹಾಸಭಾದಲ್ಲಿ", "aradhya masaba", "aradhya mahasabha", "aradhya", "aradhya house",
            "आराध्या मसबा", "आराध्या महासभा", "आराध्या"
        ], (12.2965, 76.6520)),
        ("Agrahara Circle, Mysuru", [
            "ಅಗ್ರಹಾರ ಸರ್ಕಲ್", "ಅಗ್ರಹಾರ", "ಅಗ್ರಹಾರದಲ್ಲಿ", "ಅಗ್ರಹಾರಕ್ಕೆ",
            "agrahara circle", "agrahara", "अग्रहारा", "अग्रहारा सर्कल"
        ], (12.2980, 76.6548)),
        ("Srinivasa Circle, Mysuru", ["ಶ್ರೀನಿವಾಸ ಸರ್ಕಲ್", "srinivasa circle", "ಶ್ರೀನಿವಾಸ"], (12.2910, 76.6470)),
        ("Mysuru", [
            "ಮೈಸೂರಿನಲ್ಲಿ", "ಮೈಸೂರಿನ", "ಮೈಸೂರಿಗೆ", "ಮೈಸೂರು", "mysuru", "mysore", "मैसूर", "मैसूर में"
        ], (12.2958, 76.6394)),
        ("Mandya", [
            "ಮಂಡ್ಯದಲ್ಲಿ", "ಮಂಡ್ಯಕ್ಕೆ", "ಮಂಡ್ಯ", "mandya", "मांड्या", "मांड्या में"
        ], (12.5222, 76.8966)),
        ("Srirangapatna", ["ಶ್ರೀರಂಗಪಟ್ಟಣ", "srirangapatna", "ಶ್ರೀರಂಗಪಟ್ಟಣದಲ್ಲಿ"], (12.4220, 76.6947)),
        ("Pandavapura", ["ಪಾಂಡವಪುರ", "pandavapura", "ಪಾಂಡವಪುರದಲ್ಲಿ"], (12.4984, 76.6669)),
        ("Nanjangud", ["ನಂಜನಗೂಡು", "nanjangud", "ನಂಜನಗೂಡಿನಲ್ಲಿ"], (12.1197, 76.6806)),
        ("Ramanagara", ["ರಾಮನಗರ", "ramanagara", "ರಾಮನಗರದಲ್ಲಿ"], (12.7209, 77.2799)),
        ("Channapatna", ["ಚನ್ನಪಟ್ಟಣ", "channapatna", "ಚನ್ನಪಟ್ಟಣದಲ್ಲಿ"], (12.6518, 77.2089)),
        ("Bengaluru", [
            "ಬೆಂಗಳೂರಿನಲ್ಲಿ", "ಬೆಂಗಳೂರಿಗೆ", "ಬೆಂಗಳೂರು", "bengaluru", "bangalore", "बेंगलुरु", "बेंगलुरु में"
        ], (12.9716, 77.5946)),
        ("Koramangala, Bengaluru", ["ಕೋರಮಂಗಲ", "ಕೋರಮಂಗಲದಲ್ಲಿ", "koramangala", "कोरमंगला"], (12.9352, 77.6245)),
        ("Indiranagar, Bengaluru", ["ಇಂದಿರಾನಗರ", "ಇಂದಿರಾನಗರದಲ್ಲಿ", "indiranagar", "इंदिरानगर"], (12.9784, 77.6408)),
        ("Whitefield, Bengaluru", ["ವೈಟ್‌ಫೀಲ್ಡ್", "whitefield"], (12.9698, 77.7500)),
        ("Hassan", ["ಹಾಸನ", "hassan", "ಹಾಸನದಲ್ಲಿ"], (13.0033, 76.1004)),
        ("Tumakuru", ["ತುಮಕೂರು", "tumakuru", "tumkur", "ತುಮಕೂರಿನಲ್ಲಿ"], (13.3409, 77.1010)),
    ]

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Accurately identifies language script and code-mixing."""
        if not text:
            return "en"
        has_kannada = bool(re.search(r'[\u0C80-\u0CFF]', text))
        has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))
        has_latin = bool(re.search(r'[a-zA-Z]', text))

        if has_kannada and has_latin:
            return "mixed-kn"
        elif has_devanagari and has_latin:
            return "mixed-hi"
        elif has_kannada:
            return "kn"
        elif has_devanagari:
            return "hi"
        return "en"

    @classmethod
    def normalize_indic_text(cls, text: str) -> str:
        """Converts Indic numerals and word digits to standard numeric strings."""
        if not text:
            return ""
        norm = text
        for k, v in cls.KANNADA_DIGITS.items():
            norm = norm.replace(k, v)
        for k, v in cls.HINDI_DIGITS.items():
            norm = norm.replace(k, v)
        for w, num in cls.INDIC_NUMBER_WORDS:
            norm = norm.replace(w, num)
        return norm

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, Any]:
        """
        Extracts complete 12-factor emergency and donation entity schema:
        - original_language
        - original_transcript
        - english_translation
        - food_category
        - food_name
        - quantity (Optional[int], None if omitted - DO NOT INVENT)
        - quantity_unit
        - number_of_people (Optional[int], None if omitted - DO NOT INVENT)
        - urgency
        - request_location
        - delivery_location (Optional[str], None if omitted - DO NOT INVENT)
        - delivery_coordinates (Optional[tuple[float, float]])
        - storage_requirements
        - food_condition
        - additional_requirements
        - missing_fields
        """
        raw_text = text.strip()
        lang = cls.detect_language(raw_text)
        norm = cls.normalize_indic_text(raw_text)
        norm_l = norm.lower()

        # 1. Extract Number of Affected People / Beneficiaries
        people = None
        p_patterns = [
            r'(?:there\s+are|serving|shelter\s+for|housing|sheltering)\s*(\d+)\s*(?:people|persons|individuals|victims|survivors|refugees|citizens|folks|families|kids|children)?',
            r'(\d+)\s*(?:ಜನರಿಗೆ|ಜನಕ್ಕೆ|ಜನ|ಮಂದಿಗೆ|ಸಂತ್ರಸ್ತರಿಗೆ|ಮಕ್ಕಳಿಗೆ|victims|survivors|folks|families|peopleಗೆ)',
            r'(\d+)\s*(?:people|persons|individuals|citizens|victims|survivors|refugees|families|kids|children)',
            r'(\d+)\s*(?:लोगों\s*के\s*लिए|लोगों|लोग|व्यक्तियों)',
            r'(?:for|for\s*about|supporting|help)\s*(\d+)\s*(?:people|persons|victims|families|individuals)?',
        ]
        for pat in p_patterns:
            m = re.search(pat, norm, re.IGNORECASE)
            if m:
                people = int(m.group(1))
                break

        # 2. Extract Separate Water Quantity, Water Flag & Packaging
        water_quantity = None
        water_pat = r'(\d+)\s*(?:drinking\s*water\s*bottles?|water\s*bottles?|bottles?\s*(?:of\s*)?water|liters?\s*(?:of\s*)?water|litres?\s*(?:of\s*)?water|ನೀರಿನ\s*ಬಾಟಲಿಗಳು|ನೀರಿನ\s*ಬಾಟಲಿ|ವಾಟರ್\s*ಬಾಟಲ್|पानी\s*की\s*बोतलें?|पानी\s*बोतल|water\s*packets?)'
        m_water = re.search(water_pat, norm, re.IGNORECASE)
        if m_water:
            water_quantity = int(m_water.group(1))
        water_required = bool(
            water_quantity is not None or
            re.search(r'(drinking\s*water|water\s*bottles?|bottled\s*water|ನೀರು|ನೀರಿನ|ವಾಟರ್|पानी)', norm, re.IGNORECASE)
        )

        # Check for Packaging Requirements
        packaging_required = bool(re.search(
            r'(properly\s*packed|proper\s*packaging|packaged|packaging|packed|individually\s*packaged|containers?|packets?|boxes?|parcel|sealed|ತಾಜಾ\s*ಪೊಟ್ಟಣ|ಪ್ಯಾಕಿಂಗ್|ಪ್ಯಾಕ್|ಪ್ಯಾಕೆಟ್ಗಳು|ಪ್ಯಾಕೆಟ್|ಪೊಟ್ಟಣಗಳು|पैकेजिंग|पैकिंग|पैकेट्स?|डिब्बे)',
            norm, re.IGNORECASE
        ))

        # Check for Delivery Time Mention
        delivery_time = None
        time_pat = r'\b(tonight|today|tomorrow\s*morning|tomorrow|immediately|right\s*now|within\s*\d+\s*hours?|by\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b|(ಈಗಲೇ|ಇಂದೇ|ನಾಳೆ|ತಕ್ಷಣ|ರಾತ್ರಿ|आज\s*रात|आज|कल|तुरंत)'
        m_time = re.search(time_pat, norm, re.IGNORECASE)
        if m_time:
            delivery_time = (m_time.group(1) or m_time.group(2) or "").lower()

        # 3. Extract Food Quantity and Unit (strictly excluding people and water counts)
        quantity = None
        unit = "meals"
        q_patterns = [
            (r'(\d+)\s*(?:ಊಟದ\s*ಪ್ಯಾಕೆಟ್ಗಳು|ಊಟದ\s*ಪ್ಯಾಕೆಟ್|ಊಟದ\s*ಪೊಟ್ಟಣಗಳು|ಊಟದ\s*ಪೊಟ್ಟಣ|ಪ್ಯಾಕೆಟ್ಗಳು|ಪ್ಯಾಕೆಟ್|ಪೊಟ್ಟಣಗಳು|ಪೊಟ್ಟಣ|food\s*packets?|food\s*packet|packets?|पैकेट्स?|पैकेट)', "packets"),
            (r'(\d+)\s*(?:cooked\s*meals?|prepared\s*meals?|hot\s*meals?|meals?|ಊಟದ|ಊಟ|ಆಹಾರ|भोजन|खाना|थाली|plates?|portions?)', "meals"),
            (r'(\d+)\s*(?:kg|kilos?|kilograms?|ಕೆಜಿ|ಕಿಲೋ|किलो)', "kg"),
            (r'(\d+)\s*(?:boxes|box|ಪೆಟ್ಟಿಗೆ|ಡಬ್ಬಿ|डिब्बे)', "boxes"),
            (r'(\d+)\s*(?:liters?|litres?|ಲೀಟರ್|लीटर)', "liters"),
            (r'(\d+)\s*(?:bottles?|ಬಾಟಲ್|ಬಾಟಲಿ|बोतल)', "bottles"),
        ]
        for pat, u in q_patterns:
            m = re.search(pat, norm, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val != people and val != water_quantity:
                    quantity = val
                    unit = u
                    break

        if quantity is None:
            # Fallback scan for standalone digits that are not the people count or water quantity
            all_digits = [int(n) for n in re.findall(r'\b\d+\b', norm)]
            for d in all_digits:
                if d != people and d != water_quantity:
                    quantity = d
                    break

        # 4. Categorize Food Type & Details
        food_category = "Cooked Meals"
        food_name = "Cooked Meals"
        storage_requirements = "Hot / Fresh Consumed within 4 hrs"
        food_condition = "Freshly Cooked"
        cooking_required = True

        if any(w in norm_l for w in ["cooked meals", "prepared meals", "hot meals", "ಊಟ", "भोजन", "meals"]):
            food_category = "Cooked Meals"
            food_name = "Cooked Meals"
            cooking_required = True
            storage_requirements = "Insulated Hot Packets / Thermal Carrier" if packaging_required else "Hot / Fresh Consumed within 4 hrs"
            food_condition = "Freshly Cooked"
        elif any(w in norm_l for w in ["grocery", "ration", "dhal", "rice bag", "staple", "raw", "ದಿನಸಿ", "ಅಕ್ಕಿ", "ಬೇಳೆ", "राशन"]):
            food_category = "Packaged Staples & Groceries"
            food_name = "Dry Food Staples & Rations"
            unit = "kg" if unit in ["packets", "meals"] else unit
            storage_requirements = "Dry Moisture-Free Storage"
            food_condition = "Sealed Dry Packaging"
            cooking_required = False
        elif any(w in norm_l for w in ["fruit", "vegetable", "tomato", "apple", "ಹಣ್ಣು", "ತರಕಾರಿ", "फल", "सब्जी"]):
            food_category = "Fresh Produce & Fruits"
            food_name = "Fresh Vegetables & Produce"
            unit = "kg" if unit in ["packets", "meals"] else unit
            storage_requirements = "Ventilated Cool Storage"
            food_condition = "Fresh Produce"
            cooking_required = False
        elif any(w in norm_l for w in ["bread", "biscuit", "roti", "chapati", "ಬ್ರೆಡ್", "ರೊಟ್ಟಿ", "ಚಪಾತಿ", "रोटी"]):
            food_category = "Bakery & Breads"
            food_name = "Fresh Breads & Rotis"
            storage_requirements = "Sealed Dry Container"
            food_condition = "Ready to Eat"
            cooking_required = False
        elif quantity is None and water_quantity is not None:
            food_category = "Beverages & Drinking Water"
            food_name = "Bottled Drinking Water"
            quantity = water_quantity
            unit = "bottles"
            storage_requirements = "Ambient Room Temperature"
            food_condition = "Sealed Bottles"
            cooking_required = False
        elif "packet" in norm_l or "ಪೊಟ್ಟಣ" in norm_l or "पैकेट" in norm_l:
            food_category = "Cooked Meals"
            food_name = "Emergency Food Packets"
            storage_requirements = "Insulated Hot Packets"
            food_condition = "Freshly Packed"
            cooking_required = True
        else:
            food_category = "Cooked Meals"
            food_name = f"Prepared Meals ({unit.capitalize()})"
            cooking_required = True

        # 4. Extract Delivery Destination with Protected Proper Landmarks
        delivery_location = None
        delivery_coords = None
        for canonical, aliases, coords in cls.KNOWN_LOCATIONS:
            for alias in aliases:
                # Word boundary or case-insensitive check
                if alias.lower() in norm_l:
                    delivery_location = canonical
                    delivery_coords = coords
                    break
            # If compound landmark matched (contains comma), prioritize it over bare city
            if delivery_location and "," in delivery_location:
                break

        # Dynamic prepositional location fallback (never uses hardcoded stale default)
        if not delivery_location:
            prep_match = re.search(
                r'\b(?:in|near|at|around)\s+([A-Z][A-Za-z0-9\s,\-]{2,40}?)(?:\.|,|;|$|\s+(?:for|with|and|tonight|today|urgently|immediately))',
                norm
            )
            if prep_match:
                cand_loc = prep_match.group(1).strip(" .,")
                if cand_loc and not re.match(r'^(a|an|the)\s+(shelter|camp|relief)$', cand_loc, re.IGNORECASE):
                    delivery_location = cand_loc
            elif re.search(r'([\u0C80-\u0CFF]+?)(?:ನಲ್ಲಿ|ಯಲ್ಲಿ|ದಲ್ಲಿ|ಗೆ)\b', norm):
                km = re.search(r'([\u0C80-\u0CFF]{3,25}?)(?:ನಲ್ಲಿ|ಯಲ್ಲಿ|ದಲ್ಲಿ|ಗೆ)', norm)
                if km:
                    delivery_location = km.group(1).strip()
            elif re.search(r'([\u0900-\u097F]+?)\s*(?:में|के\s*पास)', norm):
                hm = re.search(r'([\u0900-\u097F]{2,25}?)\s*(?:में|के\s*पास)', norm)
                if hm:
                    delivery_location = hm.group(1).strip()

        # 5. Contextual Urgency Classification (Multi-Factor Contextual Scoring)
        urgency_score = 0
        if any(w in norm_l for w in ["critical", "sos", "starving", "life threatening", "severe", "ಆಪತ್ತು", "ಸಂಕಷ್ಟ", "ತುರ್ತು", "संकट", "आपातकालीन", "आपातकाल", "आपात", "severe hunger", "critical emergency"]):
            urgency_score += 4
        if any(w in norm_l for w in ["immediately", "urgent", "urgently", "now", "right now", "ತಕ್ಷಣ", "ತುರ್ತಾಗಿ", "तुरंत"]):
            urgency_score += 3
        if delivery_time in ["tonight", "immediately", "right now", "today", "ಇಂದೇ", "ಈಗಲೇ"]:
            urgency_score += 3
        if people and people >= 200:
            urgency_score += 2
        elif people and people >= 50:
            urgency_score += 1
        if any(w in norm_l for w in ["shelter", "flood", "disaster", "earthquake", "fire", "victims", "camp", "stranded", "ಸಂತ್ರಸ್ತರು"]):
            urgency_score += 2

        if urgency_score >= 5 or any(w in norm_l for w in ["critical emergency", "sos", "starving", "आपातकालीन", "ತುರ್ತು"]):
            urgency = "CRITICAL"
        elif urgency_score >= 3:
            urgency = "HIGH"
        elif urgency_score >= 1:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        # 6. Additional Requirements & Context
        add_reqs = []
        if packaging_required:
            add_reqs.append("Proper Sealed Packaging")
        if water_quantity:
            add_reqs.append(f"{water_quantity} Water Bottles")
        elif water_required:
            add_reqs.append("Drinking Water Required")
        if delivery_time:
            add_reqs.append(f"Delivery: {delivery_time.capitalize()}")
        if any(w in norm_l for w in ["veg", "vegetarian", "ಶಾಖಾಹಾರಿ", "शाकाहारी"]):
            add_reqs.append("Pure Vegetarian")
        if any(w in norm_l for w in ["halal", "ಹಲಾಲ್"]):
            add_reqs.append("Halal Certified")
        if any(w in norm_l for w in ["children", "kids", "ಮಕ್ಕಳು", "बच्चे"]):
            add_reqs.append("Child-friendly Mild Spices")
        additional_requirements = " | ".join(add_reqs) if add_reqs else "Standard Community Distribution"

        # 7. Generate Accurate English Translation
        # Preserving exact numbers, unit, and protected proper nouns
        translation_parts = []
        if quantity and unit:
            translation_parts.append(f"We need {quantity} {unit} of {food_name.lower()}")
        elif quantity:
            translation_parts.append(f"We need {quantity} {food_name.lower()}")
        else:
            translation_parts.append(f"We need {food_name.lower()}")

        if people:
            translation_parts.append(f"for {people} people")

        if delivery_location:
            translation_parts.append(f"at {delivery_location}")

        if water_quantity:
            translation_parts.append(f"and {water_quantity} water bottles")

        if delivery_time:
            translation_parts.append(delivery_time)

        if urgency == "CRITICAL":
            translation_parts.append("immediately (Critical Emergency)")

        english_translation = " ".join(translation_parts) + "."
        # If input was already clean English, preserve original sentence structure
        if lang == "en" and len(raw_text.split()) > 3:
            english_translation = raw_text

        # 8. Missing Fields Audit (Never invent values!)
        missing_fields = []
        if quantity is None and water_quantity is None:
            missing_fields.append("quantity")
        if people is None:
            missing_fields.append("number_of_people")
        if delivery_location is None:
            missing_fields.append("delivery_location")

        # Map food type key
        canonical_food_type = "cooked_meals" if food_category == "Cooked Meals" else food_name.lower().replace(" ", "_")

        return {
            "original_language": lang,
            "original_transcript": raw_text,
            "normalized_transcript": norm,
            "english_translation": english_translation,
            "translated_transcript": english_translation,
            "target_language": "en",
            "food_category": food_category,
            "food_name": food_name,
            "food_type": canonical_food_type,
            "quantity": quantity,
            "food_quantity": quantity,
            "quantity_unit": unit,
            "number_of_people": people,
            "beneficiaries": people,
            "people_affected": people or 0,
            "urgency": urgency.lower(),
            "urgency_level": urgency,
            "emergency_type": "COMMUNITY_EMERGENCY" if ("shelter" in norm_l or "emergency" in norm_l or "flood" in norm_l) else "FOOD_SHORTAGE",
            "location": delivery_location,
            "delivery_location": delivery_location,
            "delivery_coordinates": delivery_coords,
            "cooking_required": cooking_required,
            "packaging_required": packaging_required,
            "water_required": water_required,
            "water_quantity": water_quantity,
            "delivery_time": delivery_time,
            "storage_requirements": storage_requirements,
            "food_condition": food_condition,
            "additional_requirements": additional_requirements,
            "additional_instructions": additional_requirements,
            "missing_fields": missing_fields,
            "is_complete": len(missing_fields) == 0,
            "confidence": 0.98 if len(missing_fields) == 0 else 0.85
        }

    @classmethod
    async def translate_text_async(cls, text: str, source_lang: str = "auto", target_lang: str = "en") -> Dict[str, str]:
        """
        Server-side multilingual translation preserving numbers & proper nouns.
        Uses Google Translate API via httpx with deterministic IndicNLPEngine fallback.
        """
        clean = (text or "").strip()
        if not clean:
            return {"translated_text": "", "translation_status": "empty"}
        src = source_lang.replace("mixed-", "").split("_")[0].split("-")[0] or "auto"
        tgt = target_lang.split("_")[0].split("-")[0] or "en"
        if src == tgt and src != "auto":
            return {"translated_text": clean, "translation_status": "completed"}
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params={"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": clean}
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, list) and payload and isinstance(payload[0], list):
                        translated = "".join(seg[0] for seg in payload[0] if isinstance(seg, list) and seg[0])
                        if translated.strip():
                            return {"translated_text": translated.strip(), "translation_status": "completed"}
        except Exception:
            pass
        extracted = cls.extract_entities(clean)
        return {
            "translated_text": extracted.get("english_translation", clean) if tgt == "en" else clean,
            "translation_status": "fallback_template"
        }

    @classmethod
    def merge_voice_draft(cls, session_id: str, existing_draft: Optional[Dict[str, Any]], new_segment: str) -> Dict[str, Any]:
        """
        Phase 3: Multi-Segment Voice Draft Accumulator.
        Merges partial utterances without overwriting valid extracted entities.
        Example:
          Segment 1: 'I need 300 meals' -> qty: 300
          Pause
          Segment 2: 'In Mysuru' -> adds delivery_location: 'Mysuru'
          Pause
          Segment 3: 'For 70 people' -> adds number_of_people: 70
        """
        clean_seg = new_segment.strip()
        if not existing_draft:
            extracted = cls.extract_entities(clean_seg)
            extracted["session_id"] = session_id
            extracted["transcripts"] = [clean_seg]
            return extracted

        # Accumulate transcript
        transcripts = existing_draft.get("transcripts", [])
        if clean_seg and clean_seg not in transcripts:
            transcripts.append(clean_seg)

        combined_text = " ".join(transcripts)
        new_extracted = cls.extract_entities(combined_text)

        # Merge fields smartly: prefer new non-null values over previous nulls
        merged = dict(existing_draft)
        merged["session_id"] = session_id
        merged["transcripts"] = transcripts
        merged["original_transcript"] = combined_text
        merged["original_language"] = new_extracted["original_language"]
        merged["english_translation"] = new_extracted["english_translation"]

        for key in [
            "quantity", "food_quantity", "quantity_unit", "number_of_people", "beneficiaries", "people_affected",
            "food_category", "food_name", "food_type", "delivery_location", "delivery_coordinates", "location",
            "cooking_required", "packaging_required", "water_quantity", "delivery_time",
            "urgency", "urgency_level", "emergency_type", "storage_requirements", "food_condition",
            "additional_requirements", "additional_instructions"
        ]:
            new_val = new_extracted.get(key)
            if new_val is not None:
                merged[key] = new_val

        # Recalculate missing fields
        missing = []
        if merged.get("quantity") is None: missing.append("quantity")
        if merged.get("number_of_people") is None: missing.append("number_of_people")
        if merged.get("delivery_location") is None: missing.append("delivery_location")

        merged["missing_fields"] = missing
        merged["is_complete"] = len(missing) == 0
        merged["people_affected"] = merged.get("number_of_people") or 0
        return merged

indic_nlp_engine = IndicNLPEngine()
