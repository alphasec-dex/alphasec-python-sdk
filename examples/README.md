# AlphaSEC SDK Examples

This directory contains example scripts demonstrating how to use the AlphaSEC Python SDK.

## Setup

1. Copy the configuration template:
   ```bash
   cp config.json.example config.json
   ```

2. Edit `config.json` with your settings:
   - `l1_wallet`: Your L1 wallet's private key (required for bridge operations)
   - `l2_wallet`: Your L2 wallet's private key (required for trading operations) 
   - `api_url`: API endpoint URL
   - `network`: "kairos" or "mainnet"
   - `l1_address`: Your wallet address
   - `session_enabled`: Whether session is enabled

## Directory Structure

### `market_data/`
Examples that only require a base URL (no private key needed):
- `basic_tickers.py` - Get ticker information and market list
- `basic_trades.py` - Get recent trade history
- `basic_balance.py` - Check wallet balances and sessions
- `basic_tokens.py` - Get token metadata
- `basic_orders_history.py` - View order history

### `trading/`
Examples that require a private key for signing transactions:
- `basic_order.py` - Place and cancel orders
- `basic_value_transfer.py` - Transfer native tokens (KAIA)
- `basic_token_transfer.py` - Transfer ERC-20 tokens
- `basic_bridge.py` - Deposit/withdraw between L1 and L2

### `websocket/`
Examples for real-time data subscriptions:
- `basic_subscribe.py` - Subscribe to market data streams
- `user_events.py` - Subscribe to user-specific events

## Usage

Run any example from the `examples/` directory:

```bash
# Market data examples (no private key required)
python market_data/basic_tickers.py
python market_data/basic_trades.py

# Trading examples (private key required)
python trading/basic_order.py
python trading/basic_value_transfer.py

# WebSocket examples
python websocket/basic_subscribe.py
```

## Safety Notes

- Always test on testnet first
- Bridge operations (`basic_bridge.py`) are commented out for safety
- Never commit your `config.json` file with real private keys
- Double-check recipient addresses before running transfer examples

## Configuration Example

```json
{
    "network": "kairos",
    "api_url": "https://api-dev.dexor.trade",
    "l1_address": "0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c",
    "l1_wallet": "0xca8c450e6775a185f2df9b41b97f03906343f0703bdeaa86200caae8605d0ff8",
    "l2_wallet": "0x71d9575098cdda737cd34ca12ee28efa574992692ce5d98a042a1b63f93d997d",
    "session_enabled": false
}
```
