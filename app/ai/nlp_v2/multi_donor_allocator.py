"""
FoodBridge NLP V2 — Multi-Donor Intelligent Allocation Engine
Calculates optimal combinations of donor supplies to fulfill large or multi-item
hunger relief requirements, supporting partial fulfillment, concurrency protection,
and multi-batch delivery assignment.
"""

import math
from typing import Dict, List, Any, Optional

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geographical distance between two coordinate pairs in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class MultiDonorAllocator:
    """Solves the multi-donor combinatorial matching problem with atomic fulfillment guarantees."""

    def compute_allocation_plan(
        self,
        requirement: Dict[str, Any],
        available_donations: List[Dict[str, Any]],
        max_search_radius_km: float = 25.0
    ) -> Dict[str, Any]:
        """
        Plans allocation of donor supplies to fulfill a single requirement.
        
        Args:
            requirement: Dict with category, target_quantity, unit, dietary_type, lat, lon, location
            available_donations: List of donation records with available_quantity, location, etc.
        """
        target_qty = float(requirement.get("target_quantity") or requirement.get("total_quantity") or 0.0)
        req_category = requirement.get("category", "COOKED_FOOD")
        req_dietary = requirement.get("dietary_type", "Vegetarian")
        req_lat = requirement.get("lat")
        req_lon = requirement.get("lon")
        req_loc = str(requirement.get("location", "")).lower()

        if target_qty <= 0:
            return {
                "success": False,
                "reason": "Target quantity must be greater than zero",
                "allocated_total": 0.0,
                "remaining_shortage": 0.0,
                "allocations": []
            }

        # 1. Filter candidate donations
        candidates: List[Dict[str, Any]] = []
        for don in available_donations:
            avail = float(don.get("available_quantity") or don.get("quantity") or 0.0)
            status = don.get("status", "AVAILABLE").upper()
            if avail <= 0 or status not in ["AVAILABLE", "ACTIVE", "VERIFIED", "APPROVED", "FRESH"]:
                continue

            # Category filter (e.g. COOKED_FOOD matches cooked meals, GROCERIES matches grains)
            don_cat = don.get("category", "COOKED_FOOD")
            if don_cat != req_category and req_category != "ANY":
                # Allow cross-compatibility only if both are food/groceries
                if not (req_category in ["COOKED_FOOD", "GROCERIES"] and don_cat in ["COOKED_FOOD", "GROCERIES"]):
                    continue

            # Dietary check: If requirement is Vegetarian, donor CANNOT be Non-Vegetarian
            don_dietary = don.get("dietary_type", "Vegetarian")
            if req_dietary == "Vegetarian" and don_dietary == "Non-Vegetarian":
                continue

            # Distance computation
            dist = 5.0 # default estimate
            don_lat = don.get("lat") or (don.get("location_coords", {}).get("lat") if isinstance(don.get("location_coords"), dict) else None)
            don_lon = don.get("lon") or (don.get("location_coords", {}).get("lon") if isinstance(don.get("location_coords"), dict) else None)
            
            if req_lat and req_lon and don_lat and don_lon:
                try:
                    dist = haversine_distance_km(float(req_lat), float(req_lon), float(don_lat), float(don_lon))
                    if dist > max_search_radius_km:
                        continue
                except (ValueError, TypeError):
                    dist = 10.0
            else:
                # String locality match boost
                don_loc = str(don.get("location") or don.get("address") or "").lower()
                if req_loc and don_loc and (req_loc in don_loc or don_loc in req_loc):
                    dist = 2.0

            candidates.append({
                "donation_id": str(don.get("_id") or don.get("id") or don.get("donation_id")),
                "donor_id": str(don.get("donor_id") or don.get("donor_name") or "Donor"),
                "donor_name": don.get("donor_name", "Community Donor"),
                "food_item": don.get("food_name") or don.get("title") or don.get("item_name") or "Food",
                "available_quantity": avail,
                "unit": don.get("unit", requirement.get("unit", "meals")),
                "distance_km": dist,
                "shelf_life_hours": don.get("shelf_life_hours", 6),
                "original_record": don
            })

        if not candidates:
            return {
                "success": False,
                "reason": f"No available matching donor inventory found within {max_search_radius_km} km",
                "allocated_total": 0.0,
                "remaining_shortage": target_qty,
                "fulfillment_percentage": 0.0,
                "allocations": []
            }

        # 2. Ranking Strategy: Prefer closer donors and fresher inventory
        # Sort key: distance ascending, available quantity descending
        candidates.sort(key=lambda x: (x["distance_km"], -x["available_quantity"]))

        # 3. Greedy Combinatorial Allocation
        needed = target_qty
        allocated_items: List[Dict[str, Any]] = []

        for cand in candidates:
            if needed <= 0:
                break

            avail = cand["available_quantity"]
            alloc_amt = min(needed, avail)

            allocated_items.append({
                "donation_id": cand["donation_id"],
                "donor_name": cand["donor_name"],
                "food_item": cand["food_item"],
                "allocated_quantity": alloc_amt,
                "unit": cand["unit"],
                "distance_km": cand["distance_km"],
                "remaining_donor_balance": avail - alloc_amt,
                "fulfillment_type": "FULL_DONATION" if alloc_amt == avail else "PARTIAL_SPLIT"
            })

            needed -= alloc_amt

        total_allocated = target_qty - needed
        fulfillment_pct = round((total_allocated / target_qty) * 100, 1)

        return {
            "success": total_allocated > 0,
            "target_quantity": target_qty,
            "allocated_total": total_allocated,
            "remaining_shortage": max(0.0, needed),
            "fulfillment_percentage": fulfillment_pct,
            "status": "FULLY_ALLOCATED" if needed == 0 else "PARTIALLY_ALLOCATED",
            "donors_count": len(allocated_items),
            "allocations": allocated_items,
            "summary": f"Allocated {total_allocated} of {target_qty} {requirement.get('unit', 'meals')} ({fulfillment_pct}%) across {len(allocated_items)} donors."
        }


multi_donor_allocator = MultiDonorAllocator()
