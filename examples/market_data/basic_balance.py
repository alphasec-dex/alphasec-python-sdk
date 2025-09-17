"""
Basic example showing how to get wallet balance and sessions.
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
    agent = Agent(config['api_url'])
    
    wallet_address = config['l1_address']
    
    print(f"=== Getting Balance for {wallet_address} ===")
    balance = agent.get_balance(wallet_address)
    print(json.dumps(balance, indent=2))
    
    print(f"\n=== Getting Sessions for {wallet_address} ===")
    sessions = agent.get_sessions(wallet_address)
    print(json.dumps(sessions, indent=2))

if __name__ == "__main__":
    main()
