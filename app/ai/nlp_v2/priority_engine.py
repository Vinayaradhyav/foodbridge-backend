"""
FoodBridge NLP V2 — Explainable Emergency Priority Engine
Calculates multi-factor urgency scores (0-100), maps to priority tiers,
and provides transparent evidence breakdowns with human verification flags.
"""

import re
from typing import Dict, List, Any

# Urgency indicator lexicons
IMMEDIATE_EMERGENCY_WORDS = [
    "urgent", "urgently", "emergency", "crisis", "sos", "critical", "immediate",
    "disaster", "flood", "floods", "earthquake", "fire", "accident", "trapped"
]

HUNGER_SCARCITY_WORDS = [
    "starving", "starvation", "no food", "empty", "hunger", "hungry", "without food",
    "severe shortage", "no rations", "food ran out", "exhausted", "desperate",
    "running low", "low on food", "scarcity", "shortage", "need meals"
]

TIME_CRITICAL_WORDS = [
    "immediately", "right now", "within 2 hours", "today", "tonight", "asap",
    "within an hour", "before night", "instant"
]

VULNERABLE_GROUP_WORDS = [
    "children", "kids", "infant", "infants", "baby", "babies", "orphanage", "orphans",
    "elderly", "elders", "senior citizens", "hospital", "patient", "patients",
    "refugee camp", "shelter home"
]


class PriorityEngine:
    """Computes explainable priority scores for food distribution and relief requests."""

    def calculate_priority(
        self,
        intent: str,
        text: str,
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates 0-100 score, priority tier, explainability evidence, and human review requirement.
        """
        lowered = text.lower()
        score = 0
        reasons: List[str] = []
        breakdown: Dict[str, int] = {
            "emergency_keywords": 0,
            "population_scale": 0,
            "hunger_scarcity": 0,
            "time_criticality": 0,
            "vulnerable_demographics": 0
        }

        # Offers are generally not emergency relief requests
        is_offer = intent in ["FOOD_DONATION_OFFER", "GROCERY_DONATION", "WATER_DONATION"]
        if is_offer:
            return {
                "score": 10,
                "priority_level": "LOW",
                "reasons": ["Standard voluntary food donation offer"],
                "evidence_breakdown": breakdown,
                "verification_status": "AUTO_PREPARED",
                "human_verification_required": False
            }

        # 1. Immediate Emergency Keywords (Up to 35 pts)
        matched_em_words = [w for w in IMMEDIATE_EMERGENCY_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
        if matched_em_words or intent in ["EMERGENCY_FOOD_REQUEST", "FOOD_SHORTAGE"]:
            em_pts = min(35, 20 + len(matched_em_words) * 5)
            breakdown["emergency_keywords"] = em_pts
            score += em_pts
            reasons.append(f"Emergency indicator words detected: {', '.join(matched_em_words) if matched_em_words else intent}")

        # 2. Population Scale (Up to 20 pts)
        pop_count = entities.get("beneficiary_count") or entities.get("total_quantity") or 0
        if pop_count >= 500:
            breakdown["population_scale"] = 20
            score += 20
            reasons.append(f"High population impact: {pop_count} individuals/meals")
        elif pop_count >= 200:
            breakdown["population_scale"] = 15
            score += 15
            reasons.append(f"Substantial population impact: {pop_count} individuals/meals")
        elif pop_count >= 50:
            breakdown["population_scale"] = 10
            score += 10
            reasons.append(f"Moderate population scale: {pop_count} individuals/meals")
        elif pop_count > 0:
            breakdown["population_scale"] = 5
            score += 5
            reasons.append(f"Local group: {pop_count} individuals/meals")

        # 3. Hunger / Food Scarcity Context (Up to 25 pts)
        matched_scarcity = [w for w in HUNGER_SCARCITY_WORDS if w in lowered]
        if matched_scarcity:
            sc_pts = min(25, 15 + len(matched_scarcity) * 5)
            breakdown["hunger_scarcity"] = sc_pts
            score += sc_pts
            reasons.append(f"Severe food scarcity cues identified: {', '.join(matched_scarcity)}")

        # 4. Time Criticality (Up to 15 pts)
        matched_time = [w for w in TIME_CRITICAL_WORDS if w in lowered]
        if matched_time:
            time_pts = 15
            breakdown["time_criticality"] = time_pts
            score += time_pts
            reasons.append(f"Urgent time dispatch requirement: {', '.join(matched_time)}")

        # 5. Vulnerable Demographics (Up to 5 pts)
        matched_vuln = [w for w in VULNERABLE_GROUP_WORDS if w in lowered]
        if matched_vuln:
            breakdown["vulnerable_demographics"] = 5
            score += 5
            reasons.append(f"Involves vulnerable demographic: {', '.join(matched_vuln)}")

        # Ensure score within 0 - 100
        score = min(100, max(0, score))

        # Determine Priority Tier
        if score >= 75:
            priority_level = "CRITICAL"
        elif score >= 50:
            priority_level = "HIGH"
        elif score >= 25:
            priority_level = "MEDIUM"
        else:
            priority_level = "LOW"

        # Verification Safety Rule: High or Critical requests ALWAYS require human admin/coordinator verification
        human_verification_required = priority_level in ["CRITICAL", "HIGH"]

        return {
            "score": score,
            "priority_level": priority_level,
            "reasons": reasons,
            "evidence_breakdown": breakdown,
            "verification_status": "UNVERIFIED" if human_verification_required else "AUTO_VERIFIED",
            "human_verification_required": human_verification_required
        }


priority_engine = PriorityEngine()
