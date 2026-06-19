"""Perp read-only query example: account, positions, funding history.

The query methods use the own address (signer.l1_address), so a signer is required.
No signatures are submitted, so no actual trades occur.
Authentication/connection info is read from config.json, same as the spot examples.

Config file:
  examples/config/config.json  (network/api_url/l1_address/l1_wallet, etc.; shared with the spot examples)
  - Copy examples/config.json.example, fill it in, then use it.

Run:
  poetry run python examples/perp/perp_query.py
"""
import json
import os

from alphasec import Agent, AlphasecSigner, load_config


def build_agent() -> Agent:
    """Build a sync Agent for queries from config.json."""
    config = load_config(os.path.dirname(__file__) + "/../config")
    signer = AlphasecSigner(config)
    return Agent(config["api_url"], signer=signer)


def main() -> None:
    agent = build_agent()

    print("=== Perp account query (get_account) ===")
    account = agent.perp.get_account()
    print(json.dumps(account, indent=2))

    print("\n=== Perp positions query (get_positions) ===")
    positions = agent.perp.get_positions()
    print(json.dumps(positions, indent=2))

    print("\n=== Perp funding history query (get_funding) ===")
    # Pagination: limit defaults to 100 / max 500; cursor uses the last row's id as last_id.
    funding = agent.perp.get_funding(limit=10)
    print(json.dumps(funding, indent=2))


if __name__ == "__main__":
    main()
