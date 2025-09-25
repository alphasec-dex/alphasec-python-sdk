"""
Basic example showing how to get wallet balance and sessions.
This example only requires a base_url, no signer needed.
"""
import json
import os

from alphasec import Agent, load_config

def main():
    # Load config
    config = load_config(os.path.dirname(__file__) + "/../config")
    
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
