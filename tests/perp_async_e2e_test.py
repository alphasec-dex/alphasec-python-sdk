"""Live ASYNC perp e2e tests (skipped by default).

Async mirror of tests/perp_e2e_test.py. These hit a real server and place/cancel
real orders, so they carry the ``live`` marker and are excluded by default
(``-m "not live"``); opt in explicitly:

    A1_PRIVATE_KEY=0x...  poetry run pytest -m live tests/perp_async_e2e_test.py -v

A plain ``pytest`` run excludes every test here (deselected by ``-m "not live"``),
so no live trades happen by default.

Config via env (defaults target the testnet):
    PERP_API_URL   (default https://api-testnet.alphasec.trade)
    PERP_CHAIN_ID  (default 41001 — testnet chain id; submits rejected with
                    -1103 "invalid chain id" without this override)
    PERP_SYMBOL    (default BTCUSDT)
    A1_PRIVATE_KEY (signs / queried account)

Async-specific contracts exercised:
  - ``async with AsyncAgent(url, signer=signer)`` initializes api+ws and cleans up.
  - ``agent.perp.<method>`` are coroutines; WS lifecycle is ``await agent.start()`` /
    ``await agent.perp.subscribe(...)`` / ``agent.stop()`` (run on context exit).
  - an ``async def`` callback is invoked by the receive pump and the frame decodes
    via ``decode_perp_event(channel, payload).kind == 'ticker'``.

The mark-price oracle / submit backend on the live testnet can be transiently degraded
(markPrice "0", -1000/-1103 backend errors); rerun when healthy.
"""
import asyncio
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

_MIN_MARGIN = Decimal("50")
_FUND_AMOUNT = Decimal("200")


def _signer_for(key: str):
    from alphasec.transaction.sign import AlphasecSigner

    addr = Account.from_key(key).address
    signer = AlphasecSigner({
        "network": "kairos",
        "l1_address": addr,
        "l1_wallet": key,
        "chain_id": CHAIN_ID,
        "session_enabled": False,
    })
    return signer, addr


def _agent_for(key: str):
    """Build an un-entered AsyncAgent; caller drives it with `async with`."""
    from alphasec import AsyncAgent

    signer, addr = _signer_for(key)
    return AsyncAgent(API_URL, signer=signer), addr


def _qty_for(price: Decimal) -> Decimal:
    return (TRADE_USDT / price).quantize(Decimal("0.00001"), rounding=ROUND_DOWN)


async def _mark(agent) -> int:
    return int(Decimal((await agent.perp.get_ticker(SYMBOL))["markPrice"]))


async def _resolve_order_id(agent, tx_hash: str, timeout: float = 14.0):
    """order() returns the submit tx hash; resolve the real order_id from the tx."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = await agent.perp.get_order_list(tx_hash)
        if rows and rows[0].get("orderId"):
            return rows[0]["orderId"]
        await asyncio.sleep(2.0)
    return None


async def _ensure_funded(agent) -> None:
    """Deposit spot USDT into the perp wallet if margin is low (orders fail at 0)."""
    if Decimal((await agent.perp.get_account())["availableBalance"]) < _MIN_MARGIN:
        await agent.perp.transfer(0, "USDT", _FUND_AMOUNT)  # SPOT_TO_PERP
        await asyncio.sleep(5)


@requires_key
async def test_market_data():
    async with _agent_for(A1_KEY)[0] as a1:
        markets = await a1.perp.get_markets()
        assert any(m["symbol"] == SYMBOL for m in markets), f"{SYMBOL} not listed"
        tk = await a1.perp.get_ticker(SYMBOL)
        # markPrice (oracle) is reliable; last "price" is "0" on a market with no trades yet.
        assert tk["symbol"] == SYMBOL and Decimal(tk["markPrice"]) > 0
        depth = await a1.perp.get_depth(SYMBOL, limit=10)
        assert "bids" in depth and "asks" in depth  # a thin market may be one-sided
        await a1.perp.get_tickers()
        await a1.perp.get_market_trades(SYMBOL, limit=5)
        now = int(time.time())
        # candles: epoch SECONDS, required.
        candles = await a1.perp.get_candles(SYMBOL, "60", from_sec=now - 7200, to_sec=now)
        assert isinstance(candles, list)


@requires_key
async def test_account_queries():
    async with _agent_for(A1_KEY)[0] as a1:
        acct = await a1.perp.get_account()
        assert "availableBalance" in acct
        await a1.perp.get_positions()
        await a1.perp.get_position_settings()
        await a1.perp.get_position_history(limit=5)
        await a1.perp.get_funding(limit=5)


@requires_key
async def test_set_leverage():
    # Standalone (order-state independent). Validates chain_id 41001 + signed submit path.
    async with _agent_for(A1_KEY)[0] as a1:
        tx = await a1.perp.set_leverage(SYMBOL, 5)
        assert isinstance(tx, str) and tx.startswith("0x")


@requires_key
async def test_trade_lifecycle():
    # order -> resolve order_id -> modify (cancel+replace) -> cancel.
    async with _agent_for(A1_KEY)[0] as a1:
        await _ensure_funded(a1)
        price = Decimal(int(await _mark(a1) * 0.97))  # passive buy ~3% below mark: rests, in band
        qty = _qty_for(price)
        try:
            tx1 = await a1.perp.order(SYMBOL, 0, price, qty, 0)  # side BUY, tif GTC
            assert tx1.startswith("0x")
            order_id = await _resolve_order_id(a1, tx1)
            if order_id is None:
                open_orders = await a1.perp.get_open_orders(market_id="1")
                order_id = open_orders[0]["orderId"] if open_orders else None
            assert order_id, "order_id never became visible (eventual consistency window exceeded)"
            tx2 = await a1.perp.modify(SYMBOL, order_id, new_price=price - Decimal("100"))
            assert tx2.startswith("0x")
            new_id = await _resolve_order_id(a1, tx2) or order_id
            tx3 = await a1.perp.cancel(SYMBOL, new_id)
            assert tx3.startswith("0x")
        finally:
            await a1.perp.cancel_all(SYMBOL)


@requires_key
async def test_transfer_roundtrip():
    # withdraw (perp->spot) then deposit (spot->perp); amount wired as a string, token as id.
    async with _agent_for(A1_KEY)[0] as a1:
        await _ensure_funded(a1)
        before = Decimal((await a1.perp.get_account())["availableBalance"])
        txw = await a1.perp.transfer(1, "USDT", TRADE_USDT)  # PERP_TO_SPOT
        assert txw.startswith("0x")
        await asyncio.sleep(6)
        txd = await a1.perp.transfer(0, "USDT", TRADE_USDT)  # SPOT_TO_PERP
        assert txd.startswith("0x")
        await asyncio.sleep(6)
        after = Decimal((await a1.perp.get_account())["availableBalance"])
        # net-zero roundtrip; balance should land within a small tolerance of the start
        assert abs(after - before) <= TRADE_USDT


@requires_key
async def test_ws_subscribe_decode():
    # perp_ticker streams without the mark-price oracle; markPrice can be degraded on the live backend.
    from alphasec.perp import decode_perp_event

    received = []
    channel = "perp_ticker@1"

    async def on_frame(payload):
        received.append(payload)

    async with _agent_for(A1_KEY)[0] as a1:
        await a1.start()
        sub_id = await a1.perp.subscribe(channel, on_frame, timeout=12)
        deadline = time.time() + 15
        while not received and time.time() < deadline:
            await asyncio.sleep(0.5)
        await a1.perp.unsubscribe(channel, sub_id)
        assert received, "no perp_ticker frames within 15s"
        event = decode_perp_event(channel, received[0])
        assert event.kind == "ticker"
