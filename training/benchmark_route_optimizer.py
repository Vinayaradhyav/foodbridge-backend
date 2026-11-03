import os
import sys
import json
import time
import random
import numpy as np

# Ensure Unicode characters print correctly on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure backend root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.ai.assignment.route_optimizer import route_optimizer, RouteOptimizer

def generate_random_stops(center_lat=12.9716, center_lon=77.5946, num_pickups=3, num_dropoffs=2, radius_km=15.0):
    """Generates synthetic pickup and dropoff coordinates clustered around urban center."""
    # 1 degree latitude ~ 111 km
    deg_per_km = 1.0 / 111.0
    
    pickups = []
    for i in range(num_pickups):
        d_lat = random.uniform(-radius_km, radius_km) * deg_per_km
        d_lon = random.uniform(-radius_km, radius_km) * deg_per_km
        pickups.append({
            "id": f"P-{i+1}",
            "donor_name": f"Surplus Donor {i+1}",
            "lat": center_lat + d_lat,
            "lon": center_lon + d_lon,
            "quantity": random.randint(20, 80),
            "expiry_hours": random.choice([3.0, 3.5, 4.0, 4.5, 5.0]),
            "food_type": random.choice(["Cooked Meals", "Bakery Items", "Fresh Produce"])
        })
        
    dropoffs = []
    total_pickup_qty = sum(p["quantity"] for p in pickups)
    remaining_qty = total_pickup_qty
    for j in range(num_dropoffs):
        d_lat = random.uniform(-radius_km, radius_km) * deg_per_km
        d_lon = random.uniform(-radius_km, radius_km) * deg_per_km
        if j == num_dropoffs - 1:
            qty = remaining_qty
        else:
            qty = random.randint(15, max(16, remaining_qty // 2))
            remaining_qty -= qty
            
        dropoffs.append({
            "id": f"D-{j+1}",
            "shelter_name": f"Shelter / Relief Hub {j+1}",
            "lat": center_lat + d_lat,
            "lon": center_lon + d_lon,
            "quantity": qty,
            "expiry_hours": 4.0,
            "food_type": "Meals"
        })
        
    return pickups, dropoffs

def run_logistics_benchmarks(num_trials=1000):
    print(f"==================================================")
    print(f"AI Module 6: Route Optimization & Logistics Engine")
    print(f"Running Empirical CVRPTW-S Benchmark ({num_trials} Scenarios)")
    print(f"==================================================")

    output_dir = os.path.join(BASE_DIR, 'models', 'logistics')
    os.makedirs(output_dir, exist_ok=True)

    vehicle_configs = [
        {"vehicle_type": "Bike", "vehicle_capacity": 60, "name": "Volunteer Bike"},
        {"vehicle_type": "Auto", "vehicle_capacity": 150, "name": "Eco Auto"},
        {"vehicle_type": "Car", "vehicle_capacity": 250, "name": "Delivery Car"},
        {"vehicle_type": "Van", "vehicle_capacity": 600, "name": "Relief Van"},
        {"vehicle_type": "Tempo", "vehicle_capacity": 1200, "name": "Logistics Tempo"}
    ]

    metrics_accum = {
        "distance_saved_km": [],
        "distance_reduction_pct": [],
        "transit_time_saved_mins": [],
        "co2_saved_kg": [],
        "execution_time_ms": [],
        "spoilage_safe_count": 0,
        "total_stops_processed": 0,
        "total_meals_routed": 0,
        "per_vehicle_stats": {v["vehicle_type"]: {"trials": 0, "avg_saved_km": 0.0, "avg_co2": 0.0} for v in vehicle_configs}
    }

    start_bench = time.time()

    for trial in range(num_trials):
        v = random.choice(vehicle_configs)
        v_copy = dict(v)
        v_copy["lat"] = 12.9716 + random.uniform(-0.05, 0.05)
        v_copy["lon"] = 77.5946 + random.uniform(-0.05, 0.05)

        num_p = random.randint(2, 4)
        num_d = random.randint(1, 3)
        pickups, dropoffs = generate_random_stops(
            center_lat=v_copy["lat"],
            center_lon=v_copy["lon"],
            num_pickups=num_p,
            num_dropoffs=num_d,
            radius_km=random.uniform(5.0, 18.0)
        )

        total_req = sum(p["quantity"] for p in pickups)
        if total_req > v_copy["vehicle_capacity"]:
            # Scale down to fit capacity for valid dispatch
            ratio = v_copy["vehicle_capacity"] / float(total_req) * 0.85
            for p in pickups:
                p["quantity"] = max(5, int(p["quantity"] * ratio))
            scaled_sum = sum(p["quantity"] for p in pickups)
            rem = scaled_sum
            for idx, d in enumerate(dropoffs):
                if idx == len(dropoffs) - 1:
                    d["quantity"] = rem
                else:
                    d["quantity"] = max(5, rem // len(dropoffs))
                    rem -= d["quantity"]

        t0 = time.perf_counter()
        res = route_optimizer.optimize_multi_stop_route(
            vehicle=v_copy,
            pickups=pickups,
            dropoffs=dropoffs,
            traffic_multiplier=random.uniform(1.1, 1.4)
        )
        t1 = time.perf_counter()

        if res["success"]:
            dur_ms = (t1 - t0) * 1000.0
            m = res["metrics"]
            metrics_accum["distance_saved_km"].append(m["distance_saved_km"])
            metrics_accum["distance_reduction_pct"].append(m["distance_reduction_pct"])
            metrics_accum["co2_saved_kg"].append(m["co2_emissions_saved_kg"])
            metrics_accum["execution_time_ms"].append(dur_ms)
            metrics_accum["total_stops_processed"] += len(res["stops"])
            metrics_accum["total_meals_routed"] += m["total_food_delivered"]

            if m["spoilage_violations"] == 0:
                metrics_accum["spoilage_safe_count"] += 1

            v_type = v_copy["vehicle_type"]
            metrics_accum["per_vehicle_stats"][v_type]["trials"] += 1
            metrics_accum["per_vehicle_stats"][v_type]["avg_saved_km"] += m["distance_saved_km"]
            metrics_accum["per_vehicle_stats"][v_type]["avg_co2"] += m["co2_emissions_saved_kg"]

    total_bench_time = time.time() - start_bench

    # Aggregate
    for v_type, data in metrics_accum["per_vehicle_stats"].items():
        if data["trials"] > 0:
            data["avg_saved_km"] = round(data["avg_saved_km"] / data["trials"], 2)
            data["avg_co2"] = round(data["avg_co2"] / data["trials"], 2)

    summary_metrics = {
        "module": "AI Module 6: Logistics & Vehicle Route Optimization Engine",
        "algorithm": "Clarke-Wright Savings + 2-Opt Local Search (CVRPTW-S)",
        "benchmark_scenarios_evaluated": num_trials,
        "total_stops_optimized": metrics_accum["total_stops_processed"],
        "total_meals_routed": metrics_accum["total_meals_routed"],
        "average_distance_reduction_pct": round(float(np.mean(metrics_accum["distance_reduction_pct"])), 1),
        "median_distance_reduction_pct": round(float(np.median(metrics_accum["distance_reduction_pct"])), 1),
        "average_distance_saved_km_per_route": round(float(np.mean(metrics_accum["distance_saved_km"])), 2),
        "average_co2_saved_kg_per_route": round(float(np.mean(metrics_accum["co2_saved_kg"])), 2),
        "total_co2_offset_simulation_kg": round(float(np.sum(metrics_accum["co2_saved_kg"])), 2),
        "spoilage_compliance_rate_pct": round((metrics_accum["spoilage_safe_count"] / num_trials) * 100, 2),
        "average_solver_latency_ms": round(float(np.mean(metrics_accum["execution_time_ms"])), 2),
        "p99_solver_latency_ms": round(float(np.percentile(metrics_accum["execution_time_ms"], 99)), 2),
        "supported_fleet_types": list(RouteOptimizer.AVERAGE_SPEEDS_KMH.keys()),
        "per_vehicle_performance": metrics_accum["per_vehicle_stats"],
        "fssai_safety_window_hours": 4.0,
        "benchmarking_duration_seconds": round(total_bench_time, 2)
    }

    metrics_file = os.path.join(output_dir, 'model_metrics.json')
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(summary_metrics, f, indent=2)

    config_file = os.path.join(output_dir, 'logistics_config.json')
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({
            "average_speeds_kmh": RouteOptimizer.AVERAGE_SPEEDS_KMH,
            "emission_factors_co2_per_km": RouteOptimizer.EMISSION_FACTORS,
            "max_stops_per_cluster": 12,
            "fssai_perishable_threshold_hours": 4.0,
            "default_traffic_multiplier": 1.25
        }, f, indent=2)

    print("\nBenchmark Finished Successfully!")
    print(f"Metrics saved to: {metrics_file}")
    print(f"Configuration saved to: {config_file}")
    print(f"- Scenarios Evaluated: {num_trials}")
    print(f"- Avg Distance Saved: {summary_metrics['average_distance_reduction_pct']}% ({summary_metrics['average_distance_saved_km_per_route']} km/route)")
    print(f"- Spoilage SLA Compliance: {summary_metrics['spoilage_compliance_rate_pct']}%")
    print(f"- Avg CO2 Saved: {summary_metrics['average_co2_saved_kg_per_route']} kg/route")
    print(f"- Avg Solver Latency: {summary_metrics['average_solver_latency_ms']} ms (P99: {summary_metrics['p99_solver_latency_ms']} ms)")

if __name__ == '__main__':
    run_logistics_benchmarks(1000)
