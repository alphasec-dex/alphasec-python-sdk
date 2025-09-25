"""
Basic example showing how to get recent trades.
This example only requires a base_url, no signer needed.
"""
import json
import os
import sys

from alphasec import Agent, load_config

def main():
    # Load config
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Initialize agent without signer for read-only operations
    agent = Agent(config['api_url'])
    
    print("=== Getting Recent Trades (KAIA/USDT) ===")
    trades = agent.get_trades("KAIA/USDT", limit=10)
    print(json.dumps(trades, indent=2))
    
    print("\n=== Getting More Trades (limit=50) ===")
    more_trades = agent.get_trades("KAIA/USDT", limit=50)
    print(f"Retrieved {len(more_trades)} trades")
    print("Latest 3 trades:")
    print(json.dumps(more_trades[:3], indent=2))

if __name__ == "__main__":
    main()
