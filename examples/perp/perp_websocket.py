"""Perp WebSocket subscription example: perp_markPrice@{marketId} mark price stream.

In the receive callback, events are classified and printed via decode_perp_event. No signer required (read-only).
Connection info (api_url) is read from config.json, same as the spot example.

Config file:
  examples/config/config.json  (api_url etc.; shared with the spot example)
  - Copy examples/config.json.example, fill it in, then use it.

Runtime selectors (optional, environment variables):
  PERP_MARKET_ID  Numeric marketId to subscribe to. If unset, PERP_SYMBOL is resolved from markets
  PERP_SYMBOL     Symbol used to resolve marketId (default: BTCUSDT)

Run:
  poetry run python examples/perp/perp_websocket.py
"""
import os
import time

from alphasec import Agent, load_config
from alphasec.perp.ws import decode_perp_event


def resolve_market_id(agent: Agent) -> str:
    """Determine the numeric marketId string to use for subscription.

    If PERP_MARKET_ID is set, use it as-is; otherwise resolve PERP_SYMBOL from markets.
    Perp WS channels are based on the numeric marketId, not the symbol.
    """
    market_id = os.environ.get("PERP_MARKET_ID")
    if market_id:
        return market_id

    symbol = os.environ.get("PERP_SYMBOL", "BTCUSDT")
    for market in agent.perp.get_markets():
        if market.get("symbol") == symbol:
            return str(market["marketId"])
    raise ValueError(f"Unknown perp symbol: {symbol}")


def main() -> None:
    config = load_config(os.path.dirname(__file__) + "/../config")
    agent = Agent(config["api_url"])

    market_id = resolve_market_id(agent)
    channel = f"perp_markPrice@{market_id}"

    def on_mark_price(payload) -> None:
        # The callback receives the WS envelope's params.result (the inner payload).
        # decode_perp_event classifies the event kind by the channel prefix.
        # The WS manager converts keys to snake_case, so event.data fields are
        # snake_case (e.g. mark_price, not markPrice).
        event = decode_perp_event(channel, payload)
        print(f"[{event.kind}] {event.data}")

    agent.start()
    print(f"=== Subscribing to {channel} ===")
    sub_id = agent.perp.subscribe(channel, on_mark_price, timeout=5)

    print("Waiting for mark price updates for 10 seconds...")
    time.sleep(10)

    print("\n=== Unsubscribing ===")
    agent.perp.unsubscribe(channel, sub_id)
    agent.stop()
    print("WebSocket connection closed")


if __name__ == "__main__":
    main()
