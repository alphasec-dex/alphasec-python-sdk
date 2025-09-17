"""
Example showing how to subscribe to user-specific events via Agent.
This example only requires a base_url, no signer needed.
"""
import os
import sys
import time

# Add parent directory to path to import alphasec
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from alphasec import Agent, load_config

def handle_user_event(message):
    """Callback function to handle user events"""
    print(f"User Event: {message}")

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(os.path.dirname(__file__)))
    
    # Initialize agent for WebSocket operations
    agent = Agent(config['api_url'])
    
    # Start WebSocket connection
    agent.start()
    
    print("=== WebSocket Connection Started ===")
    
    # Subscribe to user events using ultra-simple format
    wallet_address = config['l1_address']
    print(f"Subscribing to userEvents@{wallet_address}...")
    
    user_events_sub_id = agent.subscribe(f'userEvents@{wallet_address}', handle_user_event, timeout=5)
    
    print(f"User events subscription created: {user_events_sub_id}")
    print("Listening for user events (orders, fills, etc.) for 60 seconds...")
    print("Try placing/canceling orders in another terminal to see events...")
    
    # Keep the connection alive for 60 seconds
    time.sleep(60)
    
    # Unsubscribe using ultra-simple format
    print("\n=== Unsubscribing ===")
    agent.unsubscribe(f'userEvents@{wallet_address}', user_events_sub_id)
    
    # Stop WebSocket connection
    agent.stop()
    print("WebSocket connection closed")

if __name__ == "__main__":
    main()