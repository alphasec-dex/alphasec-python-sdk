"""
Basic example showing how to get token metadata.
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
    
    print("=== Getting Token Metadata ===")
    tokens = agent.get_tokens()
    print(json.dumps(tokens, indent=2))
    
    print(f"\n=== Token Summary ===")
    print(f"Total tokens: {len(tokens)}")
    for token in tokens:
        print(f"- {token.get('l1Symbol', 'N/A')} (ID: {token.get('tokenId', 'N/A')})")

if __name__ == "__main__":
    main()
