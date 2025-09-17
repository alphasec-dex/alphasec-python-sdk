"""
Basic example showing how to place stop orders.
This example requires a signer (private key).
"""
import os
import sys

# Add parent directory to path to import alphasec
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from alphasec import Agent, load_config, AlphasecSigner
from alphasec.api.constants import BASE_MODE, BUY, LIMIT

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(os.path.dirname(__file__)))
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    print("=== Placing a Stop Order ===")
    # Place a stop order: buy GRND at 4 USDT when price hits 3 USDT
    # Note: stop_order takes different parameters than regular order
    result = agent.stop_order(
        base_token="GRND", 
        quote_token="USDT", 
        stop_price=3, 
        price=4, 
        quantity=20, 
        side=BUY, 
        order_type=LIMIT, 
        order_mode=BASE_MODE
    )
    print(f"Stop order result: {result}")
    
    if result:
        print("Stop order placed successfully!")
    else:
        print("Failed to place stop order")

if __name__ == "__main__":
    main()
