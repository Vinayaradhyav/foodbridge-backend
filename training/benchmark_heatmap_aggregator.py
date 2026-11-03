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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.ai.analytics.heatmap_aggregator import heatmap_aggregator, HungerHeatmapAggregator

def generate_synthetic_supply_demand_data(num_samples=5000):
    donations = []
    demands = []

    zones = HungerHeatmapAggregator.DEFAULT_REFERENCE_ZONES

    for i in range(num_samples):
        # 60% chance to be around a known zone, 40% random in Karnataka
        if random.random() < 0.8:
            z = random.choice(zones)
            lat = z["lat"] + random.uniform(-0.04, 0.04)
            lon = z["lon"] + random.uniform(-0.04, 0.04)
        else:
            lat = 12.9716 + random.uniform(-0.25, 0.25)
            lon = 77.5946 + random.uniform(-0.25, 0.25)

        # 55% donation events, 45% demand events
        if random.random() < 0.55:
            donations.append({
                "id": f"DON-BENCH-{i}",
                "latitude": lat,
                "longitude": lon,
                "quantity": random.randint(15, 250),
                "food_category": random.choice(["Cooked Meals", "Bakery Items", "Fresh Produce", "Packaged"]),
                "created_at": "2026-10-16T10:00:00Z"
            })
        else:
            demands.append({
                "id": f"REQ-BENCH-{i}",
                "latitude": lat,
                "longitude": lon,
                "required_meals": random.randint(30, 300),
                "severity": random.choice(["NORMAL", "MEDIUM", "HIGH", "CRITICAL"]),
                "is_emergency": random.random() < 0.15
            })

    return donations, demands

def run_analytics_benchmarks():
    print("==================================================")
    print("AI Module 7: Platform Analytics & Hunger Heatmap Aggregator")
    print("Running Spatial Density & HSI Benchmarking (5,000 Points)")
    print("==================================================")

    output_dir = os.path.join(BASE_DIR, 'models', 'analytics')
    os.makedirs(output_dir, exist_ok=True)

    donations, demands = generate_synthetic_supply_demand_data(5000)

    # Measure execution latency of spatial aggregation
    t0 = time.perf_counter()
    heatmap_result = heatmap_aggregator.aggregate_hunger_heatmap(
        donations=donations,
        demands=demands,
        cluster_radius_km=5.0
    )
    t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000.0

    # Calculate Environmental Metrics
    total_food_kg = sum(d["quantity"] * 0.4 for d in donations) # ~0.4 kg per meal
    total_meals = sum(d["quantity"] for d in donations)
    env_metrics = heatmap_aggregator.compute_environmental_impact(total_food_kg, total_meals)

    # Diurnal profiles
    diurnal = heatmap_aggregator.compute_temporal_diurnal_patterns()

    summary_metrics = {
        "module": "AI Module 7: Platform Analytics & Hunger Heatmap Aggregator",
        "algorithm": "Spatial Density Centroid Clustering & Hunger Severity Index (HSI)",
        "synthetic_data_points_processed": len(donations) + len(demands),
        "total_donations_analyzed": len(donations),
        "total_demand_requests_analyzed": len(demands),
        "zones_monitored": len(heatmap_result["hotspots"]),
        "aggregation_latency_ms": round(latency_ms, 2),
        "overall_satisfaction_rate_pct": heatmap_result["summary"]["overall_satisfaction_rate_pct"],
        "critical_hotspots_detected": heatmap_result["summary"]["critical_zones_count"],
        "high_hotspots_detected": heatmap_result["summary"]["high_zones_count"],
        "redistribution_transfers_computed": len(heatmap_result["redistribution_recommendations"]),
        "environmental_impact": env_metrics,
        "temporal_diurnal_profiles_count": len(diurnal),
        "timestamp": heatmap_result["timestamp"]
    }

    metrics_file = os.path.join(output_dir, 'model_metrics.json')
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(summary_metrics, f, indent=2)

    config_file = os.path.join(output_dir, 'analytics_config.json')
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({
            "default_cluster_radius_km": 5.0,
            "max_hotspot_radius_km": 10.0,
            "hsi_weights": {"deficit_ratio": 0.55, "volume_factor": 0.30, "urgency": 0.15},
            "un_sdg_factors": {
                "co2e_per_kg_food": 2.5,
                "methane_per_kg_food": 0.15,
                "water_liters_per_meal": 1000
            },
            "reference_centroids": HungerHeatmapAggregator.DEFAULT_REFERENCE_ZONES
        }, f, indent=2)

    print("\nBenchmark Finished Successfully!")
    print(f"Metrics saved to: {metrics_file}")
    print(f"Config saved to: {config_file}")
    print(f"- Data Points: {len(donations) + len(demands)}")
    print(f"- Aggregation Latency: {summary_metrics['aggregation_latency_ms']} ms")
    print(f"- Hotspots Monitored: {summary_metrics['zones_monitored']}")
    print(f"- CO2e Avoided: {env_metrics['co2_emissions_avoided_kg']} kg")
    print(f"- Water Conserved: {env_metrics['water_footprint_conserved_liters']} Liters")

if __name__ == '__main__':
    run_analytics_benchmarks()
