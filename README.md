Alphasec Python SDK

A trading SDK for the Alphasec orderbook DEX.

Install
```bash
pip install alphasec-sdk
```

Configure (required for examples)
```bash
cd examples
cp config.json.example config.json
# Then edit config.json and fill your values
```

Minimal config.json
```json
{
  "network": "kairos",
  "api_url": "https://api.alphasec.trade",
  "l1_address": "0x...your_L1_address",
  "l1_wallet": "0x...your_L1_private_key",
  "l2_wallet": "0x...your_L2_private_key",
  "session_enabled": false
}
```

Quick start
```bash
python examples/market_data/basic_tickers.py
```

Notes
- Do NOT commit real private keys. Use test keys on testnet first.
