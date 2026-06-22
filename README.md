# AlphaSec Python SDK

A Python SDK for trading spot and perpetuals on the AlphaSec orderbook DEX, built on the Kaia blockchain.

[![PyPI version](https://img.shields.io/pypi/v/alphasec-py.svg)](https://pypi.org/project/alphasec-py/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A single `Agent` is the entry point. It covers spot trading, transfers, sessions, queries, and
WebSocket subscriptions; perpetuals are reached through `agent.perp`, which returns a `PerpAgent`.
Both sync (`Agent`) and async (`AsyncAgent`) variants are available. Transaction signing is handled
internally, so callers never deal with signatures directly.

## 🔗 Links

- [Official](https://alphasec.trade)
- [Telegram](https://t.me/alphasecofficial)
- [Discord](https://discord.gg/alphasec)
- [X](https://x.com/AlphaSec_Trade)

## 🌐 Network Information

### Kairos Testnet

- **API URL**: `https://api-testnet.alphasec.trade`
- **WebSocket URL**: `wss://api-testnet.alphasec.trade/ws`
- **Network**: `kairos`
- **L1 Chain ID**: 1001 (Kaia Kairos)
- **L2 Chain ID**: 41001 (AlphaSec L2)

### Mainnet

- **API URL**: `https://api.alphasec.trade`
- **WebSocket URL**: `wss://api.alphasec.trade/ws`
- **Network**: `mainnet`
- **L1 Chain ID**: 8217 (Kaia Mainnet)
- **L2 Chain ID**: 48217 (AlphaSec L2)

## 📦 Installation

```bash
pip install alphasec-py
```

Installed as `alphasec-py`, imported as `alphasec`.

## 🚀 Quickstart

Load a `config.json` with `load_config(dir_path)`, where the argument is the directory that contains
the file (not the file path). Build an `AlphasecSigner` from it and pass it to `Agent`. Token metadata
is fetched at construction, so a network connection is required. Call `start()` only when you need
WebSocket streaming.

`config.json` fields:

| Field | Required | Description |
| ----- | -------- | ----------- |
| `network` | Optional | `"mainnet"` or `"kairos"`; selects the default chain_id and bridge contracts. |
| `api_url` | Optional | REST and WebSocket base URL passed to the Agent constructor. |
| `l1_address` | Yes | L1 address. A missing value raises `ValueError`. |
| `l1_wallet` | Optional | L1 private key (hex). If both `l1_wallet` and `l2_wallet` are missing, raises `ValueError`. |
| `l2_wallet` | Optional | L2 (session) private key. Required when `session_enabled` is true. |
| `session_enabled` | Optional | When true, trades are signed with the L2 wallet; otherwise the L1 wallet. |
| `chain_id` | Optional | Overrides the network default. |

```python
import os
from alphasec import Agent, load_config, AlphasecSigner
from alphasec.api.constants import BUY, LIMIT, BASE_MODE

config = load_config(os.path.dirname(__file__) + "/config")  # directory holding config.json
signer = AlphasecSigner(config)                              # required for trading
agent = Agent(config["api_url"], signer=signer)             # fetches token metadata on construction

tickers = agent.get_tickers()
balance = agent.get_balance(config["l1_address"])

result = agent.order(
    "KAIA/USDT", BUY,
    price=0.15, quantity=10,
    order_type=LIMIT, order_mode=BASE_MODE,
)
# result: {"status": bool, "error": <message>, "order_id": <id or None>}
```

- Omit `signer` to get a read-only Agent; trading, transfer, session, and deposit methods then raise `ValueError`.
- The signing wallet is the L2 wallet when `session_enabled` is on, otherwise the L1 wallet. See [Sessions](#sessions).
- Perp trading and queries are REST only, so `agent.start()` is not needed for them.

Async uses the same surface through `AsyncAgent`, which initializes on `async with` and cleans up on exit:

```python
import asyncio, os
from alphasec import AsyncAgent, load_config, AlphasecSigner
from alphasec.api.constants import BUY, LIMIT, BASE_MODE

async def main():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    async with AsyncAgent(config["api_url"], signer=signer) as agent:
        result = await agent.order(
            "KAIA/USDT", BUY,
            price=0.15, quantity=10,
            order_type=LIMIT, order_mode=BASE_MODE,
        )

asyncio.run(main())
```

## Spot

Markets are written `"BASE/QUOTE"`; prices and quantities are passed as floats and normalized by the
SDK (value-based rounding) before submission. All spot trading is submitted over REST.

```python
from alphasec.api.constants import BUY, LIMIT, BASE_MODE

# Limit buy 10 KAIA @ 0.15 USDT.
result = agent.order(
    "KAIA/USDT", BUY,
    price=0.15, quantity=10,
    order_type=LIMIT, order_mode=BASE_MODE,
)
order_id = result["order_id"]

agent.cancel(order_id)
```

### Trading

| Method | Description |
| ------ | ----------- |
| `order` | Submit an order. `order_type` = LIMIT or MARKET, `order_mode` = BASE_MODE (quantity) or QUOTE_MODE (amount); optional TP-limit, SL-trigger, SL-limit. |
| `cancel` | Cancel one order by id. |
| `cancel_all` | Cancel every open order (account-wide). |
| `modify` | Amend the price or quantity of an open order. |
| `stop_order` | Stop order that fires at a trigger price. |

### Transfers & Deposits

| Method | Description |
| ------ | ----------- |
| `value_transfer` | Send native KAIA to an address. |
| `token_transfer` | Send a token to an address (L2 symbol, resolved to an id internally). |
| `deposit` | Deposit from L1 into the exchange. Sends an L1 tx and waits for the receipt; returns a status dict (`status`, `error`, `tx_hash`). |
| `withdraw` | Withdraw from the exchange to L1. Signs with the L1 wallet and submits via the exchange API. |

L1 deposit and withdraw always need the L1 wallet, regardless of session mode.

### Sessions

A session registers an L2 key for trade signing without exposing the L1 key.

| Method | Description |
| ------ | ----------- |
| `create_session` | Register a session. Pass the session wallet as an `eth_account.Account` object. |
| `update_session` | Renew a session. |
| `delete_session` | Remove a session. |
| `get_sessions` | List the sessions for an address. |

### Queries

| Group | Methods |
| ----- | ------- |
| Market | `get_market_list`, `get_ticker`, `get_tickers`, `get_depth`, `get_trades`, `get_tokens` |
| Orders | `get_open_orders`, `get_filled_canceled_orders`, `get_order_by_id` |
| Account | `get_balance`, `get_sessions`, `get_transfer_history` |

### WebSocket

Subscribe with `agent.subscribe(channel, callback)`; the return value is an int subscription id, and
`agent.unsubscribe(channel, subscription_id)` cancels it. Channels use the friendly `type@MARKET` form.

| Channel | Content |
| ------- | ------- |
| `ticker@{market}` | Ticker |
| `trade@{market}` | Trades |
| `depth@{market}` | Order book |
| `userEvent@{address}` | Account events (shared by spot and perp) |

```python
agent.start()
sub_id = agent.subscribe("trade@KAIA/USDT", print)
# ...
agent.unsubscribe("trade@KAIA/USDT", sub_id)
agent.stop()
```

The callback receives `params.result` (the snake_case payload), not the full envelope. Trade
submission is always REST.

## Perp

The entry point is `agent.perp`. Trading and market methods take a `symbol` and resolve it to a
numeric `market_id` internally (markets are fetched once and cached). All perp trading is REST.

```python
from decimal import Decimal
from alphasec.perp.constants import BUY, GTC

agent = Agent(config["api_url"], signer=signer)  # REST only, start() not required

# Limit buy 0.01 BTC @ 60000 USDT (below market, so it rests). Returns the accepted tx hash.
tx_hash = agent.perp.order(
    "BTCUSDT", BUY,
    Decimal("60000"),  # price
    Decimal("0.01"),   # quantity
    GTC, reduce_only=False,
)

positions = agent.perp.get_positions()
```

### Trading

| Method | Description |
| ------ | ----------- |
| `order` | Submit an order. `tif` = GTC, IOC, POST, or MARKET; supports `reduce_only` and `client_order_id`. Returns the accepted tx hash. |
| `cancel` | Cancel one order by id. |
| `cancel_all` | Cancel all open orders for a symbol (market-scoped, unlike spot). |
| `modify` | Amend an order (cancel-and-replace). |

Prices and quantities are passed as `Decimal` or `str` (floats are rejected). Perp does not
auto-normalize: round to the market `tickSize` and `lotSize` from `get_markets` and meet
`minNotional`, or the server rejects the order. Resolve order ids from a tx hash with `get_order_list`.

### Funds & Leverage

| Method | Description |
| ------ | ----------- |
| `transfer` | Move margin between the spot and perp wallets (`SPOT_TO_PERP` or `PERP_TO_SPOT`; USDT only). Internal to the exchange, does not touch L1. |
| `set_leverage` | Set leverage per symbol (1 to 125). |

### Queries

| Group | Methods |
| ----- | ------- |
| Account | `get_account`, `get_positions`, `get_position_history`, `get_position_settings`, `get_funding` |
| Orders | `get_open_orders`, `get_order_history`, `get_order`, `get_order_list`, `get_my_trades` |
| Market | `get_markets`, `get_ticker`, `get_tickers`, `get_depth`, `get_market_trades`, `get_candles` |

`get_candles` takes `from` and `to` in epoch seconds; other time ranges use milliseconds.

### WebSocket

Perp streams share the same connection as spot; trade submission is always REST. Channels use the
numeric `market_id` (resolve it with `get_markets`). Decode frames with `decode_perp_event` into a
`PerpEvent`.

| Channel | Content |
| ------- | ------- |
| `perp_ticker@{market_id}` | Ticker |
| `perp_markPrice@{market_id}` | Mark price |
| `perp_aggTrade@{market_id}` | Aggregated trades |
| `perp_aggDepth@{market_id}` | Order book |
| `perp_candle@{market_id}:{res}` | Candles |
| `userEvent@{address}` | User events (orders, positions, funding, deposits and withdrawals) |

Subscribe through `agent.perp.subscribe(channel, callback)` and cancel with
`agent.perp.unsubscribe(channel, subscription_id)`.

## 📋 Examples

### Spot

| Example | Description |
| ------- | ----------- |
| [`market_data/basic_balance`](examples/market_data/basic_balance.py) | Wallet balance and sessions. No key required. |
| [`market_data/basic_orders_history`](examples/market_data/basic_orders_history.py) | Open orders and order history. No key required. |
| [`market_data/basic_tickers`](examples/market_data/basic_tickers.py) | All and single tickers. No key required. |
| [`market_data/basic_tokens`](examples/market_data/basic_tokens.py) | Token metadata. No key required. |
| [`market_data/basic_trades`](examples/market_data/basic_trades.py) | Recent trades. No key required. |
| [`market_data/basic_transfer_history`](examples/market_data/basic_transfer_history.py) | Transfer history. No key required. |
| [`trading/basic_order`](examples/trading/basic_order.py) | Limit buy and sell, then cancel. Signer required. |
| [`trading/async_basic_order`](examples/trading/async_basic_order.py) | Async version of the order flow. Signer required. |
| [`trading/basic_stop_order`](examples/trading/basic_stop_order.py) | Stop order submission. Signer required. |
| [`trading/basic_session`](examples/trading/basic_session.py) | Session create, update, delete, list. Signer required. |
| [`trading/basic_bridge`](examples/trading/basic_bridge.py) | L1 bridge deposit and withdraw. Signer required, real funds. |
| [`trading/basic_token_deposit`](examples/trading/basic_token_deposit.py) | Native and token deposit. Signer required. |
| [`trading/basic_token_withdraw`](examples/trading/basic_token_withdraw.py) | Native and token withdraw. Signer required. |
| [`trading/basic_token_transfer`](examples/trading/basic_token_transfer.py) | ERC-20 token transfer. Signer required. |
| [`trading/basic_value_transfer`](examples/trading/basic_value_transfer.py) | Native value (KAIA) transfer. Signer required. |
| [`websocket/basic_subscribe`](examples/websocket/basic_subscribe.py) | Subscribe to trade, depth, userEvent; receive and unsubscribe. No key required. |
| [`websocket/user_events`](examples/websocket/user_events.py) | Single `userEvent@{address}` subscription for account events. No key required. |

### Perp

| Example | Description |
| ------- | ----------- |
| [`perp/perp_order`](examples/perp/perp_order.py) | Place a perp order, resolve order ids, then cancel. Signer required, real funds. |
| [`perp/perp_query`](examples/perp/perp_query.py) | Perp account, positions, and funding history. Signer required. |
| [`perp/perp_websocket`](examples/perp/perp_websocket.py) | Subscribe to mark price and decode into `PerpEvent`. No key required. |

## 🔐 Security

**Important Security Notes:**

- Never commit private keys to version control
- Use environment variables or secure key management
- Always test on the Kairos testnet before mainnet
- Verify transaction details before signing
- Blockchain transactions are irreversible

## ⚠️ Disclaimer

This SDK is provided as-is. Trading cryptocurrencies involves substantial risk and may result in
significant losses. Always do your own research and never invest more than you can afford to lose. The
developers are not responsible for any trading losses incurred while using this SDK.
