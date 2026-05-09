from datetime import datetime, timedelta
import random
import json
from pathlib import Path

# Every item we track — stock levels, thresholds, usage patterns
INVENTORY = [
    {"part_name": "Bearing 6204", "supplier_name": "Bearings Direct", "stock_level": 45, "min_stock": 12, "lead_time_days": 4, "avg_daily_usage": 2, "usage_volatility": 0.3},
    {"part_name": "Cardboard Shipping Box Large", "supplier_name": "Packaging Solutions Inc", "stock_level": 250, "min_stock": 80, "lead_time_days": 2, "avg_daily_usage": 12, "usage_volatility": 0.3},
    {"part_name": "Cable Tie Pack 200mm", "supplier_name": "ElectroParts Depot", "stock_level": 600, "min_stock": 150, "lead_time_days": 2, "avg_daily_usage": 30, "usage_volatility": 0.15},
    {"part_name": "Hydraulic Hose 1/2 inch", "supplier_name": "FluidPower Systems", "stock_level": 35, "min_stock": 10, "lead_time_days": 4, "avg_daily_usage": 1, "usage_volatility": 0.5},
    {"part_name": "Safety Goggles Clear", "supplier_name": "WorkSafe Equipment Co", "stock_level": 275, "min_stock": 70, "lead_time_days": 4, "avg_daily_usage": 10, "usage_volatility": 0.2},
    {"part_name": "Precision Bolt M4", "supplier_name": "Global Fasteners Inc", "stock_level": 200, "min_stock": 60, "lead_time_days": 2, "avg_daily_usage": 18, "usage_volatility": 0.2},
    {"part_name": "Zip Lock Bag 30x40cm", "supplier_name": "Acme Packaging", "stock_level": 20, "min_stock": 250, "lead_time_days": 2, "avg_daily_usage": 50, "usage_volatility": 0.15},
    {"part_name": "Hard Hat Class E Yellow", "supplier_name": "WorkSafe Equipment Co", "stock_level": 60, "min_stock": 15, "lead_time_days": 3, "avg_daily_usage": 3, "usage_volatility": 0.2},
    {"part_name": "Proximity Sensor NPN", "supplier_name": "ElectroParts Depot", "stock_level": 55, "min_stock": 15, "lead_time_days": 4, "avg_daily_usage": 3, "usage_volatility": 0.35},
    {"part_name": "Machine Oil ISO 46 1L", "supplier_name": "FluidPower Systems", "stock_level": 80, "min_stock": 20, "lead_time_days": 3, "avg_daily_usage": 4, "usage_volatility": 0.2},
]

def generate_history(item, days=30):
    """
    Fake 30 days of daily usage for one item.
    Weekdays use more stock. Weekends use less.
    ds = date (Prophet needs this name)
    y  = units used that day (Prophet needs this name)
    """
    random.seed(hash(item["part_name"]) % 10000)
    history = []
    today = datetime.today().date()
    start = today - timedelta(days=days)

    for i in range(days):
        date = start + timedelta(days=i)
        weekday = date.weekday()

        # Warehouse is busier Mon-Fri
        if weekday < 5:
            multiplier = random.uniform(0.9, 1.2)
        else:
            multiplier = random.uniform(0.2, 0.5)

        noise = random.uniform(1 - item["usage_volatility"], 1 + item["usage_volatility"])
        usage = max(0, round(item["avg_daily_usage"] * multiplier * noise))
        history.append({"ds": date.isoformat(), "y": usage})

    return history

def seed_all(days=30):
    print(f"Seeding {days}-day history for {len(INVENTORY)} items...\n")
    result = {}

    for item in INVENTORY:
        history = generate_history(item, days)
        avg = round(sum(r["y"] for r in history) / days, 1)
        result[item["part_name"]] = {**item, "history": history, "seeded_avg": avg}
        print(f"  ✓ {item['part_name']:<35} avg {avg} units/day")

    output = Path(__file__).parent / "data" / "usage_history.json"
    output.parent.mkdir(exist_ok=True)
    with open(output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n✅ Saved to {output}")
    return result

if __name__ == "__main__":
    seed_all()