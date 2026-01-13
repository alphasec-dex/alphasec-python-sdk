"""
Basic example showing how to get wallet transfer history.
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

    print(f"=== Getting Transfer History for {wallet_address} ===")

    # Get all transfer history (default limit: 100)
    transfers = agent.get_transfer_history(wallet_address)
    print(f"Total transfers found: {len(transfers)}")
    print(json.dumps(transfers, indent=2))

    # Example: Filter by token_id (if you know the token_id)
    # transfers = agent.get_transfer_history(wallet_address, token_id=1)

    # Example: Get transfers within a time range (timestamps in milliseconds)
    # from datetime import datetime, timedelta
    # now = int(datetime.now().timestamp() * 1000)
    # one_week_ago = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
    # transfers = agent.get_transfer_history(wallet_address, from_msec=one_week_ago, to_msec=now)

if __name__ == "__main__":
    main()
