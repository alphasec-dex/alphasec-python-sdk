import json
import os

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