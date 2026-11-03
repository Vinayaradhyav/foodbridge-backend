import logging
import math
from typing import List, Dict, Any
from bson import ObjectId

logger = logging.getLogger(__name__)

class MatchingEngine:
    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Placeholder Haversine formula for distance in km.
        """
        if None in [lat1, lon1, lat2, lon2]:
            return 5.0 # fallback default distance
        
        R = 6371 # Radius of earth in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    @classmethod
    async def match_donation_to_ngos(cls, donation_id: str) -> List[Dict[str, Any]]:
        """
        Donation-to-Receiver Matching Engine.
        1. Validate donation
        2. Find verified active receivers
        3. Filter incompatible receivers
        4. Calculate matching score
        """
        from app.database.mongodb import mongodb
        
        try:
            donation = await mongodb.db.donations.find_one({"_id": ObjectId(donation_id)})
        except Exception:
            donation = await mongodb.db.donations.find_one({"id": donation_id}) # Fallback for string ID
            
        if not donation:
            logger.error(f"Donation {donation_id} not found for matching.")
            return []

        if donation.get("status") not in ["PENDING", "AVAILABLE"]:
            logger.info("Donation is not in a matchable state.")
            return []

        donation_qty = donation.get("quantity", 0)
        donation_lat = donation.get("latitude")
        donation_lon = donation.get("longitude")
        food_type = (donation.get("food_type") or "").lower()

        # Fetch only VERIFIED active receivers (NGOs, Food Receivers, Relief Hubs)
        receivers = await mongodb.db.users.find({
            "role": {"$in": ["FOOD_RECEIVER", "food_receiver", "NGO", "ngo", "RECEIVER", "receiver", "RELIEF_HUB", "relief_hub"]},
            "verification_status": "VERIFIED",
            "status": "active"
        }).to_list(length=100)

        candidates = []
        for r in receivers:
            score = 0.0
            reasons = []
            
            # 1. Quantity / Capacity Compatibility (Weight: 30%)
            daily_cap = r.get("daily_food_capacity") or r.get("food_capacity", 50)
            try:
                cap = int(daily_cap)
            except:
                cap = 50
                
            capacity_compatibility = 0
            if cap >= donation_qty:
                capacity_compatibility = 30
                reasons.append("Capacity perfectly aligns")
            elif cap >= donation_qty * 0.5:
                capacity_compatibility = 15
                reasons.append("Can accept partial donation")
            else:
                continue # Filter completely incompatible

            score += capacity_compatibility

            # 2. Distance (Weight: 30%)
            dist = cls._calculate_distance(
                donation_lat, donation_lon,
                r.get("latitude"), r.get("longitude")
            )
            
            distance_score = 0
            if dist <= 2.0:
                distance_score = 30
                reasons.append("Very close proximity (<2km)")
            elif dist <= 5.0:
                distance_score = 20
                reasons.append("Close proximity (<5km)")
            elif dist <= 15.0:
                distance_score = 10
            
            score += distance_score
            
            # 3. Food Compatibility (Weight: 20%)
            food_compatibility = 10 # Default base
            r_prefs = (r.get("food_preferences") or "").lower()
            if food_type and food_type in r_prefs:
                food_compatibility = 20
                reasons.append("Matches preferred food type")
            
            score += food_compatibility
            
            # 4. Storage & Availability (Weight: 20%)
            availability_score = 0
            has_vehicle = r.get("has_vehicle", r.get("vehicle_availability", False))
            if has_vehicle:
                availability_score += 10
                reasons.append("Has transport")
                
            storage_cap = r.get("storage_capacity", 0)
            if storage_cap:
                availability_score += 10
                reasons.append("Has adequate storage")
                
            score += availability_score
            
            candidates.append({
                "receiverId": str(r.get("_id", r.get("firebase_uid", ""))),
                "receiverName": r.get("name", "Unknown NGO"),
                "matchScore": min(100, int(score)),
                "distance": round(dist, 1),
                "capacityCompatibility": capacity_compatibility,
                "foodCompatibility": food_compatibility,
                "availability": availability_score,
                "reason": " | ".join(reasons)
            })

        # Sort by highest score
        candidates.sort(key=lambda x: x["matchScore"], reverse=True)
        return candidates

    @classmethod
    async def match_donation_to_emergencies(cls, donation_id: str) -> List[Dict[str, Any]]:
        # Dummy implementation for now to satisfy the API
        return []

    @classmethod
    def _score_emergency_for_donation(cls, emergency: dict, donation: dict) -> Dict[str, Any]:
        """
        Scores how well an available donation can fulfill an emergency request.
        """
        score = 0
        breakdown = []
        
        req_quantity = emergency.get("quantity", 0)
        don_quantity = donation.get("quantity", 0)
        
        # 1. Quantity compatibility
        if don_quantity >= req_quantity:
            score += 40
            breakdown.append("Donation fully satisfies request (+40)")
        elif don_quantity >= req_quantity * 0.5:
            score += 20
            breakdown.append("Donation partially satisfies request (>50%) (+20)")
        elif don_quantity > 0:
            score += 5
            breakdown.append("Donation partially satisfies request (+5)")
            
        # 2. Food type match
        e_type = str(emergency.get("food_type", "")).lower()
        d_type = str(donation.get("food_type", "")).lower()
        if e_type and e_type in d_type or d_type in e_type:
            score += 30
            breakdown.append("Food type matches exactly (+30)")
            
        # 3. Distance
        dist = cls._calculate_distance(
            emergency.get("latitude"), emergency.get("longitude"),
            donation.get("latitude"), donation.get("longitude")
        )
        if dist <= 5.0:
            score += 30
            breakdown.append(f"Very close proximity: {round(dist, 1)}km (+30)")
        elif dist <= 15.0:
            score += 15
            breakdown.append(f"Within region: {round(dist, 1)}km (+15)")
            
        return {
            "total_score": score,
            "breakdown": breakdown
        }
        
    @classmethod
    async def aggregate_donations_for_emergency(cls, request_id: str) -> Dict[str, Any]:
        # Dummy implementation
        return {"error": "Not implemented"}

    def calculate_suitability_score(self, donor: dict, volunteer: dict) -> float:
        # Legacy dummy method
        return 0.8
