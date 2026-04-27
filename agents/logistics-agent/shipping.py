"""
Logistics Agent: Shipping cost and ETA calculator.
Challenge 3 — Multi-Agent Composition.

Given: supplier name, item type, item count, destination
Returns: shipping cost, carrier, ETA, and route details.
"""
import logging
import os

logger = logging.getLogger(__name__)

# Supplier → warehouse location mapping
SUPPLIER_LOCATIONS = {
    "packaging solutions inc": {"city": "Chicago", "state": "IL", "zone": 2},
    "industrial supply co": {"city": "Detroit", "state": "MI", "zone": 2},
    "acme packaging": {"city": "Columbus", "state": "OH", "zone": 2},
    "acme corp": {"city": "Columbus", "state": "OH", "zone": 2},
    "global fasteners inc": {"city": "Cleveland", "state": "OH", "zone": 2},
    "metro supply co": {"city": "Cincinnati", "state": "OH", "zone": 3},
    "craft materials ltd": {"city": "Indianapolis", "state": "IN", "zone": 3},
    "sealtech industries": {"city": "Louisville", "state": "KY", "zone": 3},
    "mechanical parts co": {"city": "Nashville", "state": "TN", "zone": 3},
    "bearings direct": {"city": "Atlanta", "state": "GA", "zone": 4},
    "storage systems ltd": {"city": "Memphis", "state": "TN", "zone": 3},
    "supply chain pros": {"city": "St. Louis", "state": "MO", "zone": 3},
    "metalworks international": {"city": "Pittsburgh", "state": "PA", "zone": 2},
    "electroparts depot": {"city": "Philadelphia", "state": "PA", "zone": 2},
    "fluidpower systems": {"city": "Houston", "state": "TX", "zone": 4},
    "worksafe equipment co": {"city": "Dallas", "state": "TX", "zone": 4},
    "metalworks international": {"city": "Pittsburgh", "state": "PA", "zone": 2},
    "sealtech industries": {"city": "Louisville", "state": "KY", "zone": 3},
}

# Item weight estimates (kg per unit)
ITEM_WEIGHTS = {
    "cardboard": 0.5,
    "box": 0.5,
    "container": 2.0,
    "bolt": 0.1,
    "nut": 0.05,
    "screw": 0.02,
    "dowel": 0.3,
    "gasket": 0.1,
    "spring": 0.2,
    "bearing": 0.3,
    "aluminum": 1.5,
    "cable": 0.2,
    "hose": 1.0,
    "goggles": 0.3,
    "tape": 0.5,
    "steel": 2.0,
    "silicone": 0.4,
    "widget": 1.0,
    "default": 0.5,
}

# Zone-based shipping rates (USD per kg)
ZONE_RATES = {
    1: 2.50,
    2: 3.75,
    3: 5.00,
    4: 6.50,
    5: 8.00,
}

# Zone-based ETA (business days)
ZONE_ETA = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
}

CARRIERS = {
    1: "FedEx Same Day",
    2: "UPS Ground",
    3: "FedEx Express",
    4: "UPS 3-Day Select",
    5: "USPS Priority Mail",
}


def estimate_weight(item_type: str, count: int) -> float:
    """Estimate total shipment weight based on item type and count."""
    item_lower = item_type.lower()
    weight_per_unit = ITEM_WEIGHTS["default"]

    for keyword, weight in ITEM_WEIGHTS.items():
        if keyword in item_lower:
            weight_per_unit = weight
            break

    total = weight_per_unit * count
    logger.info(f"Weight estimate: {count} x {weight_per_unit}kg = {total}kg")
    return total


def get_supplier_location(supplier_name: str) -> dict:
    """Look up supplier warehouse location."""
    key = supplier_name.lower().strip()
    location = SUPPLIER_LOCATIONS.get(key)

    if not location:
        # Fuzzy match — find closest key
        for sup_key, loc in SUPPLIER_LOCATIONS.items():
            if any(word in key for word in sup_key.split()):
                location = loc
                break

    return location or {"city": "Chicago", "state": "IL", "zone": 3}


def calculate_shipping(
    supplier_name: str,
    item_type: str,
    item_count: int,
    destination: str = "New York, NY",
) -> dict:
    """
    Calculate shipping cost and ETA.
    Returns cost, carrier, ETA, origin, and destination.
    """
    location = get_supplier_location(supplier_name)
    zone = location.get("zone", 3)
    origin_city = f"{location['city']}, {location['state']}"

    weight_kg = estimate_weight(item_type, item_count)
    # Minimum 0.5kg charge
    billable_weight = max(weight_kg, 0.5)

    rate = ZONE_RATES.get(zone, 5.00)
    base_cost = billable_weight * rate

    # Handling fee for large shipments
    if item_count > 50:
        handling_fee = 15.00
    elif item_count > 10:
        handling_fee = 8.00
    else:
        handling_fee = 3.50

    total_cost = round(base_cost + handling_fee, 2)
    eta_days = ZONE_ETA.get(zone, 3)
    carrier = CARRIERS.get(zone, "Standard Freight")

    result = {
        "shipping_cost": f"${total_cost:.2f}",
        "carrier": carrier,
        "eta_days": eta_days,
        "eta_label": f"{eta_days} business day{'s' if eta_days > 1 else ''}",
        "origin": origin_city,
        "destination": destination,
        "weight_kg": round(weight_kg, 2),
        "zone": zone,
        "breakdown": {
            "base_cost": f"${base_cost:.2f}",
            "handling_fee": f"${handling_fee:.2f}",
            "total": f"${total_cost:.2f}",
        },
    }

    logger.info(
        f"Shipping: {item_count}x {item_type} from {origin_city} to {destination} "
        f"= ${total_cost} via {carrier} ({eta_days} days)"
    )
    return result
