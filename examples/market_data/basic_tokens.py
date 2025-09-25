"""
Basic example showing how to get token metadata.
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
    
    print("=== Getting Token Metadata ===")
    tokens = agent.get_tokens()
    print(json.dumps(tokens, indent=2))
    
    print(f"\n=== Token Summary ===")
    print(f"Total tokens: {len(tokens)}")
    for token in tokens:
        print(f"- {token.get('l1Symbol', 'N/A')} (ID: {token.get('tokenId', 'N/A')})")

if __name__ == "__main__":
    main()
