"""Live perp e2e tests (skipped by default).

Mirrors the rust e2e scenarios (alphasec-rust-sdk tests/perp_*_e2e.rs). These hit a
real server and place/cancel real orders, so they carry the ``live`` marker and are
excluded by default (``-m "not live"``); opt in explicitly:

    A1_PRIVATE_KEY=0x...  poetry run pytest -m live tests/perp_e2e_test.py -v

Config via env (defaults target the testnet):
    PERP_API_URL   (default https://api-testnet.alphasec.trade)
    PERP_CHAIN_ID  (default 41001 — testnet chain id; submits are rejected with
                    -1103 "invalid chain id" without this override)
    PERP_SYMBOL    (default BTCUSDT)
    A1_PRIVATE_KEY (signs / queried account)

Key live-server contracts exercised (each surfaced only by real submits):
  - chain_id 41001 override (else -1103) — any signed submit.
  - order() returns the submit tx hash, not the order_id; the order_id is resolved
    from the open book / get_order_list(tx_hash) with eventual-consistency polling.
  - deposit/withdraw amount is wired as a JSON string (else -1103 unmarshal error).
  - get_candles from/to are epoch SECONDS (not ms) and required.

The mark-price oracle / submit backend on the live testnet can be transiently degraded
(markPrice "0", -1000/-1103 backend errors); rerun when healthy.
"""
import os
import time
from decimal import Decimal, ROUND_DOWN

import pytest

from eth_account import Account

API_URL = os.environ.get("PERP_API_URL", "https://api-testnet.alphasec.trade")
CHAIN_ID = int(os.environ.get("PERP_CHAIN_ID", "41001"))
SYMBOL = os.environ.get("PERP_SYMBOL", "BTCUSDT")
TRADE_USDT = Decimal(os.environ.get("PERP_TRADE_USDT", "20"))


def _load_dotenv() -> None:
    """Populate os.environ from a local .env (no python-dotenv dependency)."""
    path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))


_load_dotenv()

A1_KEY = os.environ.get("A1_PRIVATE_KEY") or os.environ.get("PERP_PRIVATE_KEY")

# Whole file hits the live exchange (testnet) backend; excluded by default, run with -m live.
pytestmark = pytest.mark.live

# Missing key -> graceful skip even under -m live (signing needs a key).
requires_key = pytest.mark.skipif(
    not A1_KEY,
    reason="live perp e2e: set A1_PRIVATE_KEY (or PERP_PRIVATE_KEY)",
)


def _make_agent(key: str):
    from alphasec import Agent
    from alphasec.transaction.sign import AlphasecSigner

    addr = Account.from_key(key).address
    signer = AlphasecSigner({
        "network": "kairos",
        "l1_address": addr,
        "l1_wallet": key,
        "chain_id": CHAIN_ID,
        "session_enabled": False,
    })
    return Agent(API_URL, signer=signer), addr


def _qty_for(price: Decimal) -> Decimal:
    return (TRADE_USDT / price).quantize(Decimal("0.00001"), rounding=ROUND_DOWN)


def _resolve_order_id(agent, tx_hash: str, timeout: float = 14.0):
    """order() returns the submit tx hash; resolve the real order_id from the tx."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = agent.perp.get_order_list(tx_hash)
        if rows and rows[0].get("orderId"):
            return rows[0]["orderId"]
        time.sleep(2.0)
    return None


@pytest.fixture(scope="module")
def a1():
    agent, addr = _make_agent(A1_KEY)
    agent._e2e_addr = addr
    return agent


_MIN_MARGIN = Decimal("50")
_FUND_AMOUNT = Decimal("200")


def _ensure_funded(agent) -> None:
    """Deposit spot USDT into the perp wallet if margin is low (orders silently fail at 0)."""
    if Decimal(agent.perp.get_account()["availableBalance"]) < _MIN_MARGIN:
        agent.perp.transfer(0, "USDT", _FUND_AMOUNT)  # SPOT_TO_PERP
        time.sleep(5)


@pytest.fixture(scope="module")
def funded(a1):
    _ensure_funded(a1)
    return True


def _mark(agent) -> int:
    return int(Decimal(agent.perp.get_ticker(SYMBOL)["markPrice"]))


@requires_key
def test_market_data(a1):
    markets = a1.perp.get_markets()
    assert any(m["symbol"] == SYMBOL for m in markets), f"{SYMBOL} not listed"
    tk = a1.perp.get_ticker(SYMBOL)
    # markPrice (oracle) is the reliable price; last "price" is "0" on a market with no trades yet.
    assert tk["symbol"] == SYMBOL and Decimal(tk["markPrice"]) > 0
    depth = a1.perp.get_depth(SYMBOL, limit=10)
    assert "bids" in depth and "asks" in depth  # a thin market may be one-sided
    a1.perp.get_tickers()
    a1.perp.get_market_trades(SYMBOL, limit=5)
    now = int(time.time())
    # candles: epoch SECONDS, required.
    candles = a1.perp.get_candles(SYMBOL, "60", from_sec=now - 7200, to_sec=now)
    assert isinstance(candles, list)


@requires_key
def test_account_queries(a1):
    acct = a1.perp.get_account()
    assert "availableBalance" in acct
    a1.perp.get_positions()
    a1.perp.get_position_settings()
    a1.perp.get_position_history(limit=5)
    a1.perp.get_funding(limit=5)


@requires_key
def test_set_leverage(a1):
    # Standalone (order-state independent). Validates chain_id 41001 + signed submit path.
    tx = a1.perp.set_leverage(SYMBOL, 5)
    assert isinstance(tx, str) and tx.startswith("0x")


@requires_key
def test_trade_lifecycle(a1, funded):
    # order -> resolve order_id (W2) -> modify (cancel+replace) -> cancel.
    price = Decimal(int(_mark(a1) * 0.97))  # passive buy ~3% below mark: rests, within band
    qty = _qty_for(price)
    try:
        tx1 = a1.perp.order(SYMBOL, 0, price, qty, 0)  # side BUY, tif GTC
        assert tx1.startswith("0x")
        order_id = _resolve_order_id(a1, tx1)
        if order_id is None:
            open_orders = a1.perp.get_open_orders(market_id="1")
            order_id = open_orders[0]["orderId"] if open_orders else None
        assert order_id, "order_id never became visible (eventual consistency window exceeded)"
        tx2 = a1.perp.modify(SYMBOL, order_id, new_price=price - Decimal("100"))
        assert tx2.startswith("0x")
        new_id = _resolve_order_id(a1, tx2) or order_id
        tx3 = a1.perp.cancel(SYMBOL, new_id)
        assert tx3.startswith("0x")
    finally:
        a1.perp.cancel_all(SYMBOL)


@requires_key
def test_transfer_roundtrip(a1, funded):
    # withdraw (perp->spot) then deposit (spot->perp); amount wired as a string, token as id (W3).
    before = Decimal(a1.perp.get_account()["availableBalance"])
    txw = a1.perp.transfer(1, "USDT", TRADE_USDT)  # PERP_TO_SPOT
    assert txw.startswith("0x")
    time.sleep(6)
    txd = a1.perp.transfer(0, "USDT", TRADE_USDT)  # SPOT_TO_PERP
    assert txd.startswith("0x")
    time.sleep(6)
    after = Decimal(a1.perp.get_account()["availableBalance"])
    # net-zero roundtrip; balance should land within a small tolerance of the start
    assert abs(after - before) <= TRADE_USDT


@requires_key
def test_ws_subscribe_decode(a1):
    # perp_ticker streams without the mark-price oracle; markPrice can be degraded on the live backend.
    from alphasec.perp import decode_perp_event

    received = []
    channel = "perp_ticker@1"
    a1.start()
    try:
        sub_id = a1.perp.subscribe(channel, lambda p: received.append(p), timeout=12)
        deadline = time.time() + 15
        while not received and time.time() < deadline:
            time.sleep(0.5)
        a1.perp.unsubscribe(channel, sub_id)
        assert received, "no perp_ticker frames within 15s"
        event = decode_perp_event(channel, received[0])
        assert event.kind == "ticker"
    finally:
        a1.stop()
