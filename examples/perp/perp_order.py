"""Example of submitting and then cancelling a perp order.

Since signing is required, the authentication/connection info is read from
config.json, the same as the spot example.
(This triggers live trading, so be careful when running it directly.)

Config file:
  examples/config/config.json  (network/api_url/l1_address/l1_wallet, etc.; shared with the spot example)
  - Copy examples/config.json.example, fill it in, then use it.

Runtime selectors (optional, environment variables):
  PERP_SYMBOL  the perp symbol to order (default: BTCUSDT)

Run:
  poetry run python examples/perp/perp_order.py
"""
import os
from decimal import Decimal

from alphasec import Agent, AlphasecSigner, load_config
from alphasec.perp.constants import BUY, GTC

SYMBOL = os.environ.get("PERP_SYMBOL", "BTCUSDT")


def build_agent() -> Agent:
    """Build a sync Agent capable of signing from config.json."""
    config = load_config(os.path.dirname(__file__) + "/../config")
    # AlphasecSigner is shared between spot/perp. The perp signing reuses the same flow.
    signer = AlphasecSigner(config)
    return Agent(config["api_url"], signer=signer)


def main() -> None:
    agent = build_agent()

    # Price/quantity must be Decimal (or str). float misaligns the bytes at the 10^18 scale.
    price = Decimal("50000")
    quantity = Decimal("0.001")

    print(f"=== Submit {SYMBOL} limit buy order ===")
    # The return value is the tx hash accepted by the sequencer. It is not a fill or an order_id.
    tx_hash = agent.perp.order(
        SYMBOL,
        side=BUY,
        price=price,
        quantity=quantity,
        tif=GTC,
        reduce_only=False,
    )
    print(f"Order submission tx hash: {tx_hash}")

    # order_id is separate from the tx hash. Cancelling with the tx hash is rejected by the server (-1207).
    # Right after submission it may be empty due to asynchronous propagation, so only cancel when it exists.
    print(f"\n=== Resolve order_id by querying {SYMBOL} orders ===")
    orders = agent.perp.get_order_list(tx_hash)
    print(f"Order list for the submission transaction: {orders}")

    order_id = None
    if orders:
        order_id = orders[0].get("orderId")

    if order_id:
        print(f"\n=== Cancel order_id {order_id} ===")
        cancel_tx = agent.perp.cancel(SYMBOL, order_id)
        print(f"Cancellation tx hash: {cancel_tx}")
    else:
        # If the order_id is not found yet, clean up with a market-wide cancel-all.
        print("\n=== order_id unresolved: clean up with market-wide cancel-all ===")
        cancel_all_tx = agent.perp.cancel_all(SYMBOL)
        print(f"Cancel-all tx hash: {cancel_all_tx}")


if __name__ == "__main__":
    main()
