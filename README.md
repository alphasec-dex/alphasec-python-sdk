# Alphasec Python SDK

A trading SDK for the Alphasec orderbook DEX.

[![PyPI version](https://badge.fury.io/py/alphasec-py.svg)](https://pypi.org/project/alphasec-py/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🔗 Links

- [Official](https://alphasec.trade)
- [Telegram](https://t.me/alphasecofficial)
- [Discord](https://discord.gg/alphasec)
- [X](https://x.com/AlphaSec_Trade)

## 🚀 Quick Start

### Install

```bash
pip install alphasec-py
```

> Installed as `alphasec-py`, imported as `alphasec`.

### Configure (required for examples)

```bash
cd examples
cp config.json.example config/config.json
# Then edit config.json and fill your values
```

### Minimal config.json

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

### Run an example

```bash
python examples/market_data/basic_tickers.py
```

## 🌐 Network Information

### Kairos Testnet

- **API URL**: `https://api-testnet.alphasec.trade`
- **Websocket URL**: `wss://api-testnet.alphasec.trade/ws`
- **Network**: `kairos`
- **L1 Chain ID**: 1001 (Kaia Kairos)
- **L2 Chain ID**: 41001 (AlphaSec L2)

### Mainnet

- **API URL**: `https://api.alphasec.trade`
- **Websocket URL**: `wss://api.alphasec.trade/ws`
- **Network**: `mainnet`
- **L1 Chain ID**: 8217 (Kaia Mainnet)
- **L2 Chain ID**: 48217 (AlphaSec L2)

## 🔐 Security

⚠️ **Important Security Notes:**

- Never commit private keys to version control
- Use environment variables or secure key management
- Always test on kairos testnet before mainnet
- Verify transaction details before signing
- Blockchain transactions are irreversible

## ⚠️ Disclaimer

This SDK is provided as-is. Trading cryptocurrencies involves substantial risk and may result in significant losses. Always do your own research and never invest more than you can afford to lose. The developers are not responsible for any trading losses incurred while using this SDK.
