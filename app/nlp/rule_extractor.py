import re
from datetime import datetime, timedelta
from typing import Dict, Any
from app.nlp.base import BaseEmergencyExtractor
from app.models.emergency import EmergencyType, Urgency

class RuleBasedEmergencyExtractor(BaseEmergencyExtractor):
    def extract(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        extracted: Dict[str, Any] = {}
        fields_found = 0
        total_fields = 7

        # 1. Quantity & Food Type
        # Match pattern like "500 vegetarian meals" or "500 meals" or "200 water bottles"
        quantity_pattern = r'(\d+)\s+([a-z\s]*)(meals?|packets?|boxes|box|bottles?|kits?|groceries|rations?|food)'
        q_match = re.search(quantity_pattern, text_lower)
        if q_match:
            extracted['quantity'] = int(q_match.group(1))
            food_desc = q_match.group(2).strip()
            base_type = q_match.group(3).strip()
            extracted['food_type'] = f"{food_desc} {base_type}".strip()
            fields_found += 2
        else:
            # Fallback for just quantity without specific food keyword (e.g. "need 500 for...")
            q_fallback = re.search(r'need\s+(\d+)', text_lower)
            if q_fallback:
                extracted['quantity'] = int(q_fallback.group(1))
                fields_found += 1

        # 2. Number of people
        people_pattern = r'(\d+)\s*(people|persons?|families|family|individuals?|survivors?)'
        p_match = re.search(people_pattern, text_lower)
        if p_match:
            extracted['number_of_people'] = int(p_match.group(1))
            fields_found += 1

        # 3. Emergency Type
        emergency_keywords = {
            'flood': EmergencyType.FLOOD,
            'earthquake': EmergencyType.EARTHQUAKE,
            'fire': EmergencyType.FIRE,
            'accident': EmergencyType.ACCIDENT,
            'cyclone': EmergencyType.CYCLONE,
            'disaster': EmergencyType.DISASTER,
            'storm': EmergencyType.CYCLONE,
            'tsunami': EmergencyType.DISASTER,
        }
        for kw, e_type in emergency_keywords.items():
            if kw in text_lower:
                extracted['emergency_type'] = e_type.value
                fields_found += 1
                break

        # 4. Urgency
        urgency_keywords = {
            'immediately': Urgency.CRITICAL,
            'urgent': Urgency.CRITICAL,
            'urgently': Urgency.CRITICAL,
            'critical': Urgency.CRITICAL,
            'asap': Urgency.HIGH,
            'soon': Urgency.MEDIUM,
        }
        for kw, u_type in urgency_keywords.items():
            if kw in text_lower:
                extracted['urgency'] = u_type.value
                fields_found += 1
                break
        
        # Default urgency if not found but it's an emergency NLP extract
        if 'urgency' not in extracted:
            extracted['urgency'] = Urgency.HIGH.value

        # 5. Location
        # Extract nouns after "at", "in", "near" up to the next preposition or punctuation
        loc_pattern = r'\b(?:at|in|near)\b\s+([a-z0-9\s]+?)(?=\s+by|\s+for|\s+immediately|\s+urgently|\s+urgent|\.|\,|$)'
        l_matches = re.findall(loc_pattern, text_lower)
        if l_matches:
            best_match = max(l_matches, key=len).strip()
            extracted['location'] = best_match.title()
            fields_found += 1

        # 6. Deadline
        from datetime import timezone
        now = datetime.now(timezone.utc)
        time_pattern = r'by\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)'
        t_match = re.search(time_pattern, text_lower)
        if t_match:
            hour = int(t_match.group(1))
            minute = int(t_match.group(2)) if t_match.group(2) else 0
            meridian = t_match.group(3)
            
            if meridian == 'pm' and hour != 12:
                hour += 12
            elif meridian == 'am' and hour == 12:
                hour = 0
                
            # Default to today
            deadline_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If the time has already passed today, assume tomorrow
            if deadline_dt < now:
                deadline_dt += timedelta(days=1)
                
            extracted['deadline'] = deadline_dt.isoformat()
            fields_found += 1
        else:
            # Fallback: "in X hours"
            hr_pattern = r'in\s+(\d+)\s*hours?'
            hr_match = re.search(hr_pattern, text_lower)
            if hr_match:
                hours = int(hr_match.group(1))
                deadline_dt = now + timedelta(hours=hours)
                extracted['deadline'] = deadline_dt.isoformat()
                fields_found += 1

        # Calculate Confidence
        confidence = round(fields_found / total_fields, 2)
        extracted['confidence'] = min(confidence, 1.0) # Cap at 1.0

        return extracted
