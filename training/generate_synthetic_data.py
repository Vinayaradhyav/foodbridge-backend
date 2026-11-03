import os
import csv
import random

def generate_data(num_records: int, output_file: str):
    # Ensure data directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    emergency_types = ['FLOOD', 'EARTHQUAKE', 'FIRE', 'ACCIDENT', 'CYCLONE', 'DISASTER', 'COMMUNITY_EMERGENCY', 'OTHER']
    urgencies = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    
    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Header
        writer.writerow([
            'number_of_people', 'requested_quantity', 'emergency_type', 'urgency', 
            'shortage', 'deadline_hours', 'distance_km', 'available_food', 
            'available_volunteers', 'available_vehicles', 'true_priority'
        ])
        
        for _ in range(num_records):
            emergency_type = random.choice(emergency_types)
            urgency = random.choice(urgencies)
            
            number_of_people = random.randint(10, 5000)
            requested_quantity = int(number_of_people * random.uniform(1.0, 3.0)) # People usually need 1-3 items
            
            available_food = random.randint(0, 1000)
            shortage = max(0, requested_quantity - available_food)
            
            deadline_hours = round(random.uniform(1.0, 72.0), 1)
            distance_km = round(random.uniform(0.5, 150.0), 1)
            
            available_volunteers = random.randint(0, 50)
            available_vehicles = random.randint(0, 10)
            
            # Synthetic Rule-based Priority logic to act as ground truth
            # Base score from urgency
            score = 0
            if urgency == 'CRITICAL': score += 40
            elif urgency == 'HIGH': score += 30
            elif urgency == 'MEDIUM': score += 15
            elif urgency == 'LOW': score += 5
            
            # Score from shortage ratio
            shortage_ratio = shortage / requested_quantity if requested_quantity > 0 else 0
            score += (shortage_ratio * 30)
            
            # Score from deadline (closer = higher score)
            if deadline_hours < 4: score += 20
            elif deadline_hours < 12: score += 15
            elif deadline_hours < 24: score += 10
            
            # Score from people affected
            if number_of_people > 1000: score += 15
            elif number_of_people > 100: score += 10
            elif number_of_people > 50: score += 5
            
            # Add some random noise to make ML learn rather than just memorizing rules
            score += random.uniform(-10, 10)
            
            # Determine target class
            if score >= 75:
                true_priority = 'CRITICAL'
            elif score >= 55:
                true_priority = 'HIGH'
            elif score >= 30:
                true_priority = 'MEDIUM'
            else:
                true_priority = 'LOW'
                
            writer.writerow([
                number_of_people, requested_quantity, emergency_type, urgency,
                shortage, deadline_hours, distance_km, available_food,
                available_volunteers, available_vehicles, true_priority
            ])

if __name__ == '__main__':
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'synthetic_emergencies.csv')
    generate_data(3000, output_path)
    print(f"Generated 3000 synthetic records at {output_path}")
