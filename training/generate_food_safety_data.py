import pandas as pd
import numpy as np
import random
import os

def generate_enhanced_food_safety_data(num_samples=25000, output_path="data/food_safety_synthetic.csv"):
    """
    Generates realistic, scientifically grounded dataset for Food Safety ML models.
    Incorporates FSSAI 2020 2-Hour/4-Hour rules, Arrhenius microbial degradation kinetics,
    container protection factors, and ambient humidity & temperature parameters.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    random.seed(42)
    np.random.seed(42)

    food_types = [
        'Cooked Meals',       # Rice, Dal, Curry, Biryani, Sambhar
        'Raw Vegetables',     # Fresh produce, salad
        'Raw Meat',           # Poultry, mutton, fish
        'Baked Goods',        # Bread, roti, buns, cakes
        'Canned Food',        # Preserved, tinned groceries
        'Dairy'               # Milk, paneer, curd, sweets
    ]
    
    storage_conditions = ['Room Temperature', 'Refrigerated', 'Frozen', 'Heated']
    storage_containers = [
        'Airtight Stainless Steel',
        'Sealed Food Grade Plastic',
        'Insulated Hot Carrier',
        'Refrigerated Cooler',
        'Open Tray / Pot',
        'Aluminum Foil Wrap'
    ]
    
    base_shelf_life = {
        'Cooked Meals': 6.0,
        'Raw Meat': 4.5,
        'Dairy': 5.0,
        'Baked Goods': 36.0,
        'Raw Vegetables': 48.0,
        'Canned Food': 720.0
    }
    
    container_multipliers = {
        'Airtight Stainless Steel': 1.35,
        'Sealed Food Grade Plastic': 1.20,
        'Insulated Hot Carrier': 1.85,
        'Refrigerated Cooler': 4.50,
        'Aluminum Foil Wrap': 0.95,
        'Open Tray / Pot': 0.60
    }

    data = []

    for _ in range(num_samples):
        f_type = random.choice(food_types)
        storage = random.choice(storage_conditions)
        container = random.choice(storage_containers)
        has_expiry = random.choice([0, 1])

        # Temperature sampling based on storage
        if storage == 'Room Temperature':
            temp_c = round(random.uniform(18.0, 38.0), 1)
        elif storage == 'Refrigerated':
            temp_c = round(random.uniform(1.0, 7.0), 1)
        elif storage == 'Frozen':
            temp_c = round(random.uniform(-22.0, -2.0), 1)
        else: # Heated hot holding (>60C)
            temp_c = round(random.uniform(55.0, 85.0), 1)

        humidity_pct = round(random.uniform(30.0, 92.0), 1)

        base_hrs = base_shelf_life[f_type]
        c_mult = container_multipliers[container]

        # Arrhenius microbial thermal kinetics
        if temp_c <= -10.0:
            k_temp = 0.05
        elif temp_c <= 4.0:
            k_temp = 0.22
        elif temp_c >= 65.0:
            k_temp = 0.25
        else:
            k_temp = float(2.2 ** ((temp_c - 20.0) / 10.0))

        # Humidity acceleration
        k_hum = 1.0 + max(0.0, (humidity_pct - 50.0) * 0.007)

        effective_safe_window = round(max(0.8, (base_hrs * c_mult) / (k_temp * k_hum)), 2)

        # Elapsed hours sampling
        max_elapsed = min(96.0, effective_safe_window * 1.5)
        elapsed_hrs = round(random.uniform(0.1, max(0.5, max_elapsed)), 1)

        # Hours remaining
        hours_remaining = max(0.0, round(effective_safe_window - elapsed_hrs, 2))
        risk_score = min(1.0, max(0.0, round(elapsed_hrs / effective_safe_window, 3)))

        # FSSAI 2-Hour / 4-Hour statutory rule mapping
        if hours_remaining <= 0.6 or elapsed_hrs >= effective_safe_window:
            label = 'UNSAFE'
        elif hours_remaining <= 2.2 or risk_score >= 0.60:
            label = 'CAUTION'
        else:
            label = 'SAFE'

        # Regulatory constraints for room temperature perishables
        if storage == 'Room Temperature' and f_type in ['Cooked Meals', 'Raw Meat', 'Dairy']:
            if elapsed_hrs > 4.0:
                label = 'UNSAFE'
                hours_remaining = 0.0
            elif elapsed_hrs > 2.0:
                label = 'CAUTION'
            else:
                label = 'SAFE'

        # Packaging string mapping
        if 'Stainless' in container or 'Plastic' in container:
            pkg = 'Container'
        elif 'Open' in container:
            pkg = 'Open'
        elif 'Foil' in container or 'Wrapped' in container:
            pkg = 'Wrapped'
        else:
            pkg = 'Sealed'

        data.append({
            'food_type': f_type,
            'elapsed_hours': elapsed_hrs,
            'temperature_c': temp_c,
            'humidity_pct': humidity_pct,
            'storage_condition': storage,
            'storage_container': container,
            'packaging': pkg,
            'has_expiry_info': has_expiry,
            'effective_safe_window': effective_safe_window,
            'safe_hours_remaining': hours_remaining,
            'risk_score': risk_score,
            'safety_status': label
        })

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} enhanced food safety records saved to {output_path}")
    print("\nSafety Status Label Distribution:")
    print(df['safety_status'].value_counts(normalize=True) * 100)

if __name__ == "__main__":
    generate_enhanced_food_safety_data(25000, "data/food_safety_synthetic.csv")
