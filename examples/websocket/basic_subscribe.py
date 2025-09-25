"""
Basic example showing how to use WebSocket subscriptions via Agent.
This example only requires a base_url, no signer needed.
Ultra-simple API with channel@target format.
"""
import os
import time

from alphasec import Agent, load_config

def print_message(message):
    """Callback function to print received messages"""
    print(f"Received: {message}")

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Initialize agent for WebSocket operations
    agent = Agent(config['api_url'])
    
    # Start WebSocket connection
    agent.start()
    
    print("=== WebSocket Connection Started ===")
    
    # Subscribe to various channels using ultra-simple format
    print("Subscribing to trade@KAIA/USDT...")
    trade_sub_id = agent.subscribe('trade@KAIA/USDT', print_message, timeout=5)
    
    # print("Subscribing to ticker@KAIA/USDT...")
    # ticker_sub_id = agent.subscribe('ticker@KAIA/USDT', print_message, timeout=5)
    
    print("Subscribing to depth@KAIA/USDT...")
    depth_sub_id = agent.subscribe('depth@KAIA/USDT', print_message, timeout=5)
    
    # Subscribe to user events
    print("Subscribing to user events...")
    user_address = config['l1_address']
    user_event_sub_id = agent.subscribe(f'userEvent@{user_address}', print_message, timeout=5)
    
    # print(f"Subscriptions created: trades={trade_sub_id}, ticker={ticker_sub_id}, depth={depth_sub_id}, user_events={user_event_sub_id}")
    
    # Keep the connection alive for 30 seconds
    print("Listening for messages for 30 seconds...")
    time.sleep(10)
    
    # Unsubscribe using the same ultra-simple format
    print("\n=== Unsubscribing ===")
    agent.unsubscribe('trade@KAIA/USDT', trade_sub_id)
    # agent.unsubscribe('ticker@KAIA/USDT', ticker_sub_id)
    agent.unsubscribe('depth@KAIA/USDT', depth_sub_id)
    agent.unsubscribe(f'userEvent@{user_address}', user_event_sub_id)

    # Stop WebSocket connection
    agent.stop()
    print("WebSocket connection closed")

if __name__ == "__main__":
    main()