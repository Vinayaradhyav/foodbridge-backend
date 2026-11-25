"""
FoodBridge NLP V2 — Multi-Item Entity Extractor & Quantity Intelligence
Handles clause segmentation, quantity/unit pairing, food categorization,
beneficiary separation, location extraction, and dietary classification.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from app.ai.nlp_v2.ontology import FOOD_ONTOLOGY, NON_FOOD_TERMS, UNIT_SYNONYMS, get_food_category, is_non_food

# Number word to integer mapping
WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000
}

KNOWN_LOCATIONS = [
    "mysuru", "mysore", "agrahara", "hebbal", "vijayanagar", "kuvempunagar",
    "saraswathipuram", "gokulam", "jp nagar", "vv mohalla", "metagalli",
    "bengaluru", "bangalore", "whitefield", "indiranagar", "koramangala",
    "jayanagar", "electronic city", "harlur", "btm layout", "malleshwaram",
    "shivajinagar", "chamrajpet", "rajajinagar", "hosur", "kengeri", "madahalli"
]

NON_VEG_KEYWORDS = [
    "chicken", "mutton", "fish", "meat", "egg", "eggs", "prawn", "prawns",
    "seafood", "beef", "pork", "biryani chicken", "chicken curry", "fish curry"
]

VEG_KEYWORDS = [
    "veg", "vegetarian", "pure veg", "dal", "sambar", "rice", "curd", "paneer",
    "chapati", "roti", "sabzi", "vegetable", "idli", "dosa"
]


class EntityExtractor:
    """Intelligent entity extractor with multi-item pairing and unit normalization."""

    def __init__(self):
        self.ontology = FOOD_ONTOLOGY
        self.unit_synonyms = UNIT_SYNONYMS

    def extract_all(self, text: str) -> Dict[str, Any]:
        """
        Extracts all structured entities from raw natural text.
        """
        cleaned_text = text.strip()
        lowered = cleaned_text.lower()

        # 1. Non-food rejection check (handles singular and plurals)
        non_food_matches = [term for term in NON_FOOD_TERMS if re.search(rf"\b{term}s?\b", lowered)]

        # 2. Extract beneficiaries (people, families, children, refugees, victims)
        beneficiaries, beneficiary_count = self._extract_beneficiaries(lowered)

        # 3. Segment into clauses and extract food/beverage items
        items = self._extract_food_items(cleaned_text)

        # 4. Extract locations
        location = self._extract_location(cleaned_text)

        # 5. Extract dietary classification
        dietary_type = self._determine_dietary_type(lowered, items)

        # 6. Extract time/freshness mentions
        freshness_info = self._extract_freshness(lowered)

        # Calculate total quantity and primary food description
        total_quantity = sum(item.get("quantity", 0) for item in items if item.get("quantity"))
        primary_item_name = ", ".join(item.get("item_name", "") for item in items[:3]) if items else "Food Items"
        primary_category = items[0].get("category", "COOKED_FOOD") if items else "COOKED_FOOD"

        return {
            "items": items,
            "total_items_count": len(items),
            "primary_item_name": primary_item_name,
            "primary_category": primary_category,
            "total_quantity": total_quantity if total_quantity > 0 else (beneficiary_count if beneficiary_count else 0),
            "beneficiaries": beneficiaries,
            "beneficiary_count": beneficiary_count,
            "location": location,
            "dietary_type": dietary_type,
            "freshness": freshness_info,
            "non_food_detected": non_food_matches,
            "is_valid_food": len(items) > 0 and len(non_food_matches) == 0
        }

    def _extract_beneficiaries(self, text: str) -> Tuple[Dict[str, Any], Optional[int]]:
        """
        Extracts beneficiary/people count without confusing it with food item quantities.
        Example: '500 meals for 250 flood victims' -> beneficiaries count = 250, unit = 'flood victims'
        """
        pattern = r"(?:for|to|serve|feed|helping|affecting|around|approx|approximately)?\s*(\d+|[a-z]+)\s*(?:[a-zA-Z]+\s+)?(people|persons|individuals|families|kids|children|refugees|victims|elders|citizens|homeless|displaced)\b"
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for m in matches:
            qty_raw = m.group(1).lower()
            target_unit = m.group(2).lower()
            
            # Convert quantity
            count = None
            if qty_raw.isdigit():
                count = int(qty_raw)
            elif qty_raw in WORD_TO_NUM:
                count = WORD_TO_NUM[qty_raw]
                
            if count is not None and count > 0:
                return {
                    "count": count,
                    "unit": target_unit,
                    "target_group": target_unit
                }, count

        # Secondary check: "100 affected people", "50 families"
        secondary_pattern = r"\b(\d+)\s*(?:[a-zA-Z]+\s+)?(people|families|children|victims)\b"
        sec_match = re.search(secondary_pattern, text, re.IGNORECASE)
        if sec_match:
            cnt = int(sec_match.group(1))
            return {
                "count": cnt,
                "unit": sec_match.group(2).lower(),
                "target_group": sec_match.group(2).lower()
            }, cnt

        return {"count": 0, "unit": "people", "target_group": "people"}, None

    def _extract_food_items(self, text: str) -> List[Dict[str, Any]]:
        """
        Segments text by commas, semicolons, 'and', 'plus', '&' and extracts paired quantities, units, and food names.
        Example: '25 kg rice, 10 litres oil and 100 water bottles' -> 3 parsed items
        """
        # Segment into clauses
        clauses = re.split(r",|\band\b|\bplus\b|&|\n|;", text, flags=re.IGNORECASE)
        items: List[Dict[str, Any]] = []

        for raw_clause in clauses:
            clause = raw_clause.strip()
            if not clause:
                continue

            # Check if this clause is purely a beneficiary phrase (e.g. "for 100 people")
            if re.search(r"^\s*(?:for|to)\s+\d+\s+(?:people|families|children|victims|persons)", clause, re.IGNORECASE):
                continue

            extracted_item = self._parse_single_clause(clause)
            if extracted_item:
                items.append(extracted_item)

        # If clause splitting found nothing, attempt a global scan
        if not items:
            global_item = self._parse_single_clause(text)
            if global_item:
                items.append(global_item)

        return items

    def _parse_single_clause(self, clause: str) -> Optional[Dict[str, Any]]:
        """Parses a single phrase for quantity, unit, food term, and category."""
        lowered = clause.lower()

        # Find food matches from ontology
        matched_category = None
        matched_item_name = None
        longest_match_len = 0

        for cat, items_dict in self.ontology.items():
            for formal_name, syn_list in items_dict.items():
                for syn in syn_list:
                    pattern = rf"\b{re.escape(syn)}\b"
                    if re.search(pattern, lowered):
                        if len(syn) > longest_match_len:
                            matched_category = cat
                            matched_item_name = formal_name
                            longest_match_len = len(syn)

        if not matched_category or not matched_item_name:
            # Check generic food terms
            if any(term in lowered for term in ["food", "meal", "ration", "breakfast", "lunch", "dinner"]):
                matched_category = "COOKED_FOOD"
                matched_item_name = "Prepared Meals"
            elif "grocery" in lowered or "ration kit" in lowered:
                matched_category = "GROCERIES"
                matched_item_name = "Grocery Kit"
            elif "water" in lowered:
                matched_category = "WATER"
                matched_item_name = "Drinking Water Bottles"
            else:
                return None

        # Extract quantity and unit
        quantity, unit = self._extract_quantity_and_unit(clause)

        # Default units by category if missing
        if not unit:
            if matched_category == "COOKED_FOOD":
                unit = "meals"
            elif matched_category == "WATER":
                unit = "bottles" if "bottle" in lowered else ("cans" if "can" in lowered else "litres")
            elif matched_category in ["GROCERIES", "VEGETABLES", "FRUITS"]:
                unit = "kg"
            elif matched_category == "DAIRY":
                unit = "litres" if "milk" in lowered else "packets"
            elif matched_category == "PACKAGED_FOOD":
                unit = "packets"
            else:
                unit = "units"

        # Determine perishability & shelf life
        is_perishable = matched_category in ["COOKED_FOOD", "DAIRY", "FRUITS", "VEGETABLES"]
        shelf_life_hours = {
            "COOKED_FOOD": 6,
            "DAIRY": 24,
            "FRUITS": 48,
            "VEGETABLES": 72,
            "WATER": 720,
            "GROCERIES": 2160,
            "PACKAGED_FOOD": 1440,
            "BABY_FOOD": 720
        }.get(matched_category, 24)

        return {
            "item_name": matched_item_name,
            "raw_text": clause,
            "category": matched_category,
            "quantity": quantity,
            "unit": unit,
            "perishable": is_perishable,
            "shelf_life_hours": shelf_life_hours
        }

    def _extract_quantity_and_unit(self, clause: str) -> Tuple[Optional[float], Optional[str]]:
        """Extracts numerical quantity and standardizes the unit."""
        # Find all numbers (digits or word numbers) in the clause
        # Pattern: digits (int or decimal)
        tokens = clause.strip().split()
        for idx, token in enumerate(tokens):
            clean_tok = token.strip(".,;:()[]{}").lower()
            val = None
            if re.match(r"^\d+(?:\.\d+)?$", clean_tok):
                try:
                    val = float(clean_tok)
                    if val.is_integer():
                        val = int(val)
                except ValueError:
                    val = None
            elif clean_tok in WORD_TO_NUM:
                val = float(WORD_TO_NUM[clean_tok])

            if val is not None:
                # Look at the next 1 to 3 tokens for a valid unit
                found_unit = None
                for offset in range(1, 4):
                    if idx + offset < len(tokens):
                        nxt = tokens[idx + offset].strip(".,;:()[]{}").lower()
                        # If next token is a beneficiary term, this number might be for beneficiaries
                        if nxt in ["people", "persons", "families", "kids", "children", "victims", "refugees", "elders"]:
                            break
                        if nxt in self.unit_synonyms:
                            found_unit = self.unit_synonyms[nxt]
                            break
                        if nxt in self.unit_synonyms.values():
                            found_unit = nxt
                            break

                # If found unit or no next unit found yet
                if found_unit:
                    return val, found_unit
                # If no explicit unit word found in next 3 tokens, check if next token was not a beneficiary
                if idx + 1 < len(tokens):
                    nxt = tokens[idx + 1].strip(".,;:()[]{}").lower()
                    if nxt not in ["people", "persons", "families", "kids", "children", "victims", "refugees"]:
                        return val, None
                return val, None

        return None, None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extracts geographic location from known locations or prepositions."""
        lowered = text.lower()

        # Check known locations
        for loc in KNOWN_LOCATIONS:
            if re.search(rf"\b{re.escape(loc)}\b", lowered):
                return loc.title()

        # Prepositional location extraction: 'at <Loc>', 'near <Loc>', 'in <Loc>', 'location: <Loc>'
        loc_patterns = [
            r"\b(?:at|near|around|in|from|to|location:?)\s+([A-Z][a-zA-Z0-9\s,]{2,30}?)(?:\.|\band\b|\bwith\b|\bfor\b|$)",
            r"\b(?:area|locality|address|circle|hall|temple|school|college|shelter):\s*([a-zA-Z0-9\s,]{3,35})"
        ]

        for pat in loc_patterns:
            m = re.search(pat, text)
            if m:
                candidate = m.group(1).strip()
                if candidate and len(candidate) > 2 and not any(w in candidate.lower() for w in ["food", "meal", "rice", "urgently", "need", "have"]):
                    return candidate

        return None

    def _determine_dietary_type(self, text: str, items: List[Dict[str, Any]]) -> str:
        """Determines dietary type: Vegetarian, Non-Vegetarian, Vegan, Pure Water."""
        # Non-veg keywords
        if any(re.search(rf"\b{kw}\b", text) for kw in NON_VEG_KEYWORDS):
            return "Non-Vegetarian"

        # Check items
        if all(item.get("category") == "WATER" for item in items) and items:
            return "Pure Drinking Water"

        if any(item.get("category") == "DAIRY" for item in items):
            return "Vegetarian (Contains Dairy)"

        if any(re.search(rf"\b{kw}\b", text) for kw in VEG_KEYWORDS):
            return "Vegetarian"

        return "Vegetarian"

    def _extract_freshness(self, text: str) -> Dict[str, Any]:
        """Extracts freshness / preparation time cues."""
        if any(w in text for w in ["fresh", "freshly prepared", "just cooked", "hot"]):
            return {"status": "FRESH", "note": "Freshly cooked"}
        
        hours_match = re.search(r"(\d+)\s*(?:hours?|hrs?)\s*(?:ago|old)", text)
        if hours_match:
            hrs = int(hours_match.group(1))
            return {"status": "EDIBLE_WITHIN_HOURS", "hours_elapsed": hrs, "note": f"Prepared {hrs} hours ago"}

        return {"status": "STANDARD_FRESH", "note": "Safe consumption within shelf life window"}


entity_extractor = EntityExtractor()
