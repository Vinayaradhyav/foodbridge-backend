import logging
import re

logger = logging.getLogger(__name__)

class EmergencyNLP:
    def extract_emergency_parameters(self, raw_text: str) -> dict:
        """
        Parses a natural language emergency request and extracts structured parameters.
        Example: 'Need 500 meals for 200 people at Relief Hub A immediately.'
        """
        logger.info(f"NLP Processing string: {raw_text}")
        
        # Base Regex Implementation for Architecture outline
        quantity_match = re.search(r'(\d+)\s*(meals|kg|liters)', raw_text, re.IGNORECASE)
        people_match = re.search(r'(\d+)\s*people', raw_text, re.IGNORECASE)
        
        extracted = {
            "food_type": "Meals" if "meals" in raw_text.lower() else "Unknown",
            "quantity": int(quantity_match.group(1)) if quantity_match else 0,
            "people_affected": int(people_match.group(1)) if people_match else 0,
            "location": self._extract_location(raw_text),
            "urgency": "Immediate" if "immediately" in raw_text.lower() or "urgent" in raw_text.lower() else "Normal"
        }
        
        return extracted

    def calculate_priority(self, extracted_data: dict) -> str:
        """Calculates AI Priority based on people affected and time remaining."""
        people = extracted_data.get("people_affected", 0)
        urgency = extracted_data.get("urgency", "Normal")
        
        if people > 100 or urgency == "Immediate":
            return "CRITICAL"
        if people > 50:
            return "HIGH"
        return "MEDIUM"

    def _extract_location(self, text: str) -> str:
        lower = text.lower()
        cities_map = [
            ("Maddur", ["maddur", "ಮದ್ದೂರು"]),
            ("Mandya", ["mandya", "ಮಂಡ್ಯ"]),
            ("Srirangapatna", ["srirangapatna", "ಶ್ರೀರಂಗಪಟ್ಟಣ"]),
            ("Mysuru", ["mysuru", "mysore", "ಮೈಸೂರು"]),
            ("Ramanagara", ["ramanagara", "ರಾಮನಗರ"]),
            ("Channapatna", ["channapatna", "ಚನ್ನಪಟ್ಟಣ"]),
            ("Bangalore Central", ["bangalore", "bengaluru", "ಬೆಂಗಳೂರು", "indiranagar", "koramangala"]),
            ("Agrahara Circle", ["agrahara", "ಅಗ್ರಹಾರ"]),
        ]
        for canonical, aliases in cities_map:
            if any(a in lower for a in aliases):
                return canonical
        if "at" in lower:
            parts = text.split("at")
            if len(parts) > 1:
                return parts[1].split("immediately")[0].strip()
        return "Local Community"

emergency_nlp = EmergencyNLP()
