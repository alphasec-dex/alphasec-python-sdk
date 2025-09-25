"""
Basic example showing how to place and cancel orders.
This example requires a signer (private key).
"""
import os

from alphasec import Agent, load_config, AlphasecSigner
from alphasec.api.constants import BASE_MODE, BUY, SELL, LIMIT

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    print("=== Placing a Limit Buy Order ===")
    # Place a limit buy order for 1 GRND at 15 USDT using constants
    result = agent.order("GRND/USDT", BUY, price=15, quantity=1, order_type=LIMIT, order_mode=BASE_MODE)
    print(f"Order result: {result}")
    
    if result:
        print("Order placed successfully!")
        
        # Get open orders to see our order
        l1_address = config['l1_address']
        open_orders = agent.get_open_orders(l1_address, "GRND/USDT", limit=5)
        print("\nCurrent open orders:")
        print(open_orders)
        
        # Cancel the order if it exists
        if open_orders and len(open_orders) > 0:
            order_id = open_orders[0].get('orderId')
            if order_id:
                print(f"\n=== Canceling Order {order_id} ===")
                cancel_result = agent.cancel(order_id)
                print(f"Cancel result: {cancel_result}")
        else:
            # Try canceling with a test order ID
            print(f"\n=== Canceling Order with ID '1' ===")
            cancel_result = agent.cancel("1")
            print(f"Cancel result: {cancel_result}")
    else:
        print("Failed to place order")

if __name__ == "__main__":
    main()
