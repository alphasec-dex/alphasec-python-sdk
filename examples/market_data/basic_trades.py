"""
Basic example showing how to get recent trades.
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
