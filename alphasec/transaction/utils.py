import json
import os
import math

def load_config(path: str):
    config_path = os.path.join(path, "config.json")
    with open(config_path, "r") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Invalid config file")

    if "l1_address" not in config:
        raise ValueError("l1_address should be set")
    if "l1_wallet" not in config and "l2_wallet" not in config:
        raise ValueError("l1_wallet, l2_wallet are not set")
    if "session_enabled" in config and "l2_wallet" not in config:
        raise ValueError("session_enabled is set but l2_wallet is not set")

    return config

def normalize_price_quantity(price: float, quantity: float) -> tuple[float, float]:
    """
    Normalize price and quantity based on value-based rules.
    
    Price decimal rules (based on price value):
    - ≥ $10,000: 0 decimals
    - ≥ $1,000: 1 decimal
    - ≥ $100: 2 decimal
    - ≥ $10: 3 decimal
    - ≥ $1: 4 decimal
    - < $1: 8 decimal
    
    Quantity minimum size rules (based on price value):
    - ≥ $10,000: min size 0.00001
    - ≥ $1,000: min size 0.0001
    - ≥ $100: min size 0.001
    - ≥ $10: min size 0.01
    - ≥ $1: min size 0.1
    - < $1: min size 1
    
    Args:
        price: The price value to normalize (determines decimal precision)
        quantity: The quantity value to normalize (applies minimum size constraint)
        
    Returns:
        Tuple of (normalized_price, normalized_quantity)
    """
    def get_price_decimal_precision(price_value: float) -> int:
        """Get decimal precision for price based on price value thresholds."""
        abs_value = abs(price_value)
        
        if abs_value >= 10000:
            return 0
        elif abs_value >= 1000:
            return 1
        elif abs_value >= 100:
            return 2
        elif abs_value >= 10:
            return 3
        elif abs_value >= 1:
            return 4
        else:
            return 8
    
    def get_quantity_decimal_precision(price_value: float) -> int:
        """Get quantity precision for quantity based on price value thresholds."""
        abs_value = abs(price_value)
        
        if abs_value >= 10000:
            return 5
        elif abs_value >= 1000:
            return 4
        elif abs_value >= 100:
            return 3
        elif abs_value >= 10:
            return 2
        elif abs_value >= 1:
            return 1
        else:
            return 0

    # Validation
    if price <= 0:
        raise ValueError("Price must be positive")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    
    # Normalize price based on its own value
    price_precision = get_price_decimal_precision(price)
    normalized_price = round(price, price_precision)
    
    # Normalize quantity based on price value (minimum size constraint)
    quantity_precision = get_quantity_decimal_precision(price)
    normalized_quantity = round(quantity, quantity_precision)
    
    return normalized_price, normalized_quantity