"""
Example showing how to subscribe to user-specific event via Agent.
This example only requires a base_url, no signer needed.
"""
import os
import time

from alphasec import Agent, load_config
from alphasec.transaction.utils import load_config

def handle_user_event(message):
    """Callback function to handle user event"""
    print(f"User Event: {message}")

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Initialize agent for WebSocket operations
    agent = Agent(config['api_url'])
    
    # Start WebSocket connection
    agent.start()
    
    print("=== WebSocket Connection Started ===")
    
    # Subscribe to user event using ultra-simple format
    l1_address = config['l1_address']
    print(f"Subscribing to userEvent@{l1_address}...")
    
    user_event_sub_id = agent.subscribe(f'userEvent@{l1_address}', handle_user_event, timeout=5)
    
    print(f"User event subscription created: {user_event_sub_id}")
    print("Listening for user event (orders, fills, etc.) for 60 seconds...")
    print("Try placing/canceling orders in another terminal to see event...")
    
    # Keep the connection alive for 30 seconds
    time.sleep(30)
    
    # Unsubscribe using ultra-simple format
    print("\n=== Unsubscribing ===")
    agent.unsubscribe(f'userEvent@{l1_address}', user_event_sub_id)

    # Stop WebSocket connection
    agent.stop()
    print("WebSocket connection closed")

if __name__ == "__main__":
    main()