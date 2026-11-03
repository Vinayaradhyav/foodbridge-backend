import math
from typing import List, Dict, Any

class AssignmentOptimizer:
    def __init__(self, strategy="weighted"):
        self.strategy = strategy

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate the great circle distance in kilometers between two points."""
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _calculate_travel_time(self, distance_km: float) -> int:
        """Estimate travel time in minutes assuming 30 km/h average city speed."""
        speed_km_per_min = 30.0 / 60.0
        return int(distance_km / speed_km_per_min)

    def optimize(self, task: Dict[str, Any], volunteers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Finds the optimal volunteer for a task.
        task = { "pickup_lat", "pickup_lon", "quantity", "priority" }
        volunteers = [ { "id", "name", "lat", "lon", "is_authorized", "is_available", "vehicle_capacity", "current_workload" } ]
        """
        ranked_candidates = []

        for v in volunteers:
            # 1. Hard Constraints
            if not v.get("is_authorized", False):
                continue
            if not v.get("is_available", False):
                continue
            if v.get("vehicle_capacity", 0) < task.get("quantity", 0):
                continue

            # 2. Weighted Scoring (Heuristic)
            distance = self._haversine_distance(
                task["pickup_lat"], task["pickup_lon"], 
                v["lat"], v["lon"]
            )
            
            # Closer is better. Base score 100, lose 2 points per km
            distance_score = max(0, 100 - (distance * 2))
            
            # Workload penalty (lose 10 points per active task)
            workload = v.get("current_workload", 0)
            workload_score = max(0, 100 - (workload * 10))
            
            # Capacity utilization bonus (prefer smaller vehicles that just fit, to save large vehicles)
            capacity = v.get("vehicle_capacity", 1)
            utilization = task.get("quantity", 0) / capacity
            capacity_score = utilization * 100 # Closer to 1.0 is better
            
            # Final heuristic score
            total_score = (distance_score * 0.5) + (workload_score * 0.3) + (capacity_score * 0.2)
            
            travel_time = self._calculate_travel_time(distance)
            
            ranked_candidates.append({
                "id": v["id"],
                "name": v["name"],
                "vehicle_type": v.get("vehicle_type", "Unknown"),
                "vehicle_capacity": capacity,
                "current_workload": workload,
                "distance_km": round(distance, 2),
                "estimated_travel_time_mins": travel_time,
                "assignment_score": round(total_score, 2)
            })
            
        # Sort by highest score
        ranked_candidates.sort(key=lambda x: x["assignment_score"], reverse=True)

        if not ranked_candidates:
            return {
                "success": False,
                "message": "No eligible volunteers found meeting capacity and availability constraints."
            }

        return {
            "success": True,
            "ranked_candidates": ranked_candidates,
            "recommended_volunteer": ranked_candidates[0], # The best candidate
            "algorithm_used": self.strategy
        }

assignment_optimizer = AssignmentOptimizer(strategy="weighted")
