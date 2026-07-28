"""
E-commerce Tools Implementation adhering to 5 Tool Contract Principles:
1. Deterministic: same input -> same output.
2. Error as data: return {"ok": False, "error": "..."}, no exceptions thrown.
3. Strict Input Validation: validate required fields and types.
4. No internal LLM calls.
5. Single responsibility per tool.
"""

from typing import Dict, Any, Union

# Mock inventory database
MOCK_INVENTORY = {
    "iphone": {"price": 25000000, "stock": 15, "status": "in_stock"},
    "macbook": {"price": 35000000, "stock": 0, "status": "out_of_stock"},
    "ipad": {"price": 18000000, "stock": 8, "status": "in_stock"},
}

# Mock coupon database
MOCK_COUPONS = {
    "WINNER": {"discount_percent": 10, "valid": True},
    "LEGACY": {"discount_percent": 0, "valid": False},
}

# Mock shipping rates database
MOCK_SHIPPING = {
    "hanoi": {"shipping_cost": 38000, "estimated_days": 1},
    "ha noi": {"shipping_cost": 38000, "estimated_days": 1},
    "hà nội": {"shipping_cost": 38000, "estimated_days": 1},
    "saigon": {"shipping_cost": 45000, "estimated_days": 2},
    "sai gon": {"shipping_cost": 45000, "estimated_days": 2},
    "tp.hcm": {"shipping_cost": 45000, "estimated_days": 2},
    "ho chi minh": {"shipping_cost": 45000, "estimated_days": 2},
}


def check_stock(item_name: str = None, **kwargs) -> Dict[str, Any]:
    """
    Check item price, remaining stock, and status.
    Usage: check_stock(item_name="iPhone")
    """
    # Check if item_name was provided in kwargs or directly
    if not item_name and "item" in kwargs:
        item_name = kwargs["item"]
    
    if not item_name or not isinstance(item_name, str) or not item_name.strip():
        return {
            "ok": False,
            "error": "Missing or invalid required parameter 'item_name'."
        }

    clean_item = item_name.strip().lower()
    if clean_item in MOCK_INVENTORY:
        data = MOCK_INVENTORY[clean_item]
        return {
            "ok": True,
            "item_name": item_name,
            "price": data["price"],
            "stock": data["stock"],
            "status": data["status"]
        }

    return {
        "ok": False,
        "error": f"Item '{item_name}' not found in inventory."
    }


def get_discount(coupon_code: str = None, **kwargs) -> Dict[str, Any]:
    """
    Validate discount coupon code and return discount percentage.
    Usage: get_discount(coupon_code="WINNER")
    """
    if not coupon_code and "coupon" in kwargs:
        coupon_code = kwargs["coupon"]
    if not coupon_code and "code" in kwargs:
        coupon_code = kwargs["code"]

    if not coupon_code or not isinstance(coupon_code, str) or not coupon_code.strip():
        return {
            "ok": False,
            "error": "Missing or invalid required parameter 'coupon_code'."
        }

    clean_code = coupon_code.strip().upper()
    if clean_code in MOCK_COUPONS:
        coupon_info = MOCK_COUPONS[clean_code]
        return {
            "ok": True,
            "coupon_code": clean_code,
            "discount_percent": coupon_info["discount_percent"],
            "valid": coupon_info["valid"]
        }

    return {
        "ok": True,
        "coupon_code": coupon_code,
        "discount_percent": 0,
        "valid": False,
        "message": f"Coupon code '{coupon_code}' is invalid or expired."
    }


def calc_shipping(weight: Union[float, int] = None, destination: str = None, **kwargs) -> Dict[str, Any]:
    """
    Calculate shipping cost and estimated delivery days based on weight (kg) and destination.
    Usage: calc_shipping(weight=0.8, destination="Hanoi")
    """
    if weight is None and "dest" in kwargs:
        destination = kwargs.get("dest", destination)
    if destination is None and "dest" in kwargs:
        destination = kwargs["dest"]

    if weight is None or not isinstance(weight, (int, float)) or weight <= 0:
        return {
            "ok": False,
            "error": "Parameter 'weight' must be a positive number (kg)."
        }

    if not destination or not isinstance(destination, str) or not destination.strip():
        return {
            "ok": False,
            "error": "Missing or invalid required parameter 'destination'."
        }

    clean_dest = destination.strip().lower()
    base = MOCK_SHIPPING.get(clean_dest, {"shipping_cost": 50000, "estimated_days": 3})
    
    # Weight surcharge for items over 2kg: +10,000 VND per extra kg
    extra_weight_fee = max(0, int((weight - 2.0) * 10000)) if weight > 2.0 else 0
    total_shipping = base["shipping_cost"] + extra_weight_fee

    return {
        "ok": True,
        "weight": weight,
        "destination": destination,
        "shipping_cost": total_shipping,
        "estimated_days": base["estimated_days"]
    }