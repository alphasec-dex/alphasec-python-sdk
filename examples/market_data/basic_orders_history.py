"""
Basic example showing how to get order history.
This example only requires a base_url, no signer needed.
"""
import json
import os
import sys

# Add parent directory to path to import alphasec
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from alphasec import Agent

def main():
    # Load config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    with open(config_path) as f:
        config = json.load(f)
    
    # Initialize agent without signer for read-only operations
    agent = Agent(config['base_url'])
    
    wallet_address = config['wallet_address']
    market = "KAIA/USDT"
    
    print(f"=== Getting Open Orders for {wallet_address} ===")
    open_orders = agent.get_open_orders(wallet_address, market, limit=10)
    print(json.dumps(open_orders, indent=2))
    
    print(f"\n=== Getting Filled/Canceled Orders for {wallet_address} ===")
    history = agent.get_filled_canceled_orders(wallet_address, market, limit=10)
    print(json.dumps(history, indent=2))
    
    # Example of getting specific order by ID (if you have one)
    if open_orders and len(open_orders) > 0:
        order_id = open_orders[0].get('orderId')
        if order_id:
            print(f"\n=== Getting Order by ID: {order_id} ===")
            order_detail = agent.get_order_by_id(order_id)
            print(json.dumps(order_detail, indent=2))

if __name__ == "__main__":
    main()
