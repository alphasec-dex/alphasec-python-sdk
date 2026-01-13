from typing import Any, Optional
from eth_utils.address import is_address, to_checksum_address
import asyncio
import httpx
import logging
# eth_account.Account is used for type compatibility with signer
import time
import web3

from alphasec.api.constants import (
    ALPHASEC_KAIROS_URL,
    ALPHASEC_MAINNET_URL,
    KAIROS_URL,
    MAINNET_URL,
    BUY,
    SELL,
    LIMIT,
    MARKET,
    BASE_MODE,
    QUOTE_MODE,
)
from alphasec.transaction.constants import (
    DexCommandSessionCreate,
    DexCommandSessionUpdate,
    DexCommandSessionDelete,
)
from alphasec.transaction.sign import AlphasecSigner
from alphasec.transaction.utils import normalize_price_quantity

from .utils import market_to_market_id, _clean_params, split_base_quote_token


class AsyncAPI:
    """Async API client for AlphaSec DEX using httpx.AsyncClient."""

    def __init__(
        self,
        url: str,
        timeout: Optional[float] = None,
        signer: Optional[AlphasecSigner] = None,
    ):
        self.url = url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._logger = logging.getLogger(__name__)
        self.token_id_symbol_map: dict = {}
        self.symbol_token_id_map: dict = {}
        self.token_id_address_map: dict = {}
        self.token_id_decimals_map: dict = {}
        self.signer = signer
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure the client is initialized and token metadata is loaded."""
        if not self._initialized:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
            await self._map_token_metadata()
            self._initialized = True

    async def _map_token_metadata(self) -> None:
        """Load and map token metadata from the API."""
        tokens = await self.get_tokens()
        for token in tokens:
            self.token_id_symbol_map[token["tokenId"]] = token["l2Symbol"]
            self.symbol_token_id_map[token["l2Symbol"]] = token["tokenId"]
            self.token_id_address_map[token["tokenId"]] = token["l1Address"]
            self.token_id_decimals_map[token["tokenId"]] = token["l1Decimal"]

    async def __aenter__(self) -> "AsyncAPI":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        await self._map_token_metadata()
        self._initialized = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make an async GET request."""
        await self._ensure_initialized()
        assert self._client is not None
        response = await self._client.get(self.url + path, params=params)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    async def post(self, path: str, params: Optional[dict] = None) -> dict:
        """Make an async POST request."""
        await self._ensure_initialized()
        assert self._client is not None
        response = await self._client.post(self.url + path, json=params)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    async def put(self, path: str, params: Optional[dict] = None) -> dict:
        """Make an async PUT request."""
        await self._ensure_initialized()
        assert self._client is not None
        response = await self._client.put(self.url + path, json=params)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    async def delete(self, path: str, params: Optional[dict] = None) -> dict:
        """Make an async DELETE request."""
        await self._ensure_initialized()
        assert self._client is not None
        response = await self._client.request("DELETE", self.url + path, json=params)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    async def get_market_list(self) -> list:
        """Get list of available markets."""
        response = await self.get("/api/v1/market")
        return response["result"]

    async def get_depth(self, market: str, limit: int = 100) -> dict:
        """Get order book depth for a market."""
        await self._ensure_initialized()
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        response = await self.get(
            f"/api/v1/market/depth?marketId={market_id}&limit={limit}"
        )
        return response["result"]

    async def get_ticker(self, market: str) -> dict:
        """Get ticker information for a market."""
        await self._ensure_initialized()
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        response = await self.get(f"/api/v1/market/ticker?marketId={market_id}")
        return response["result"][0]

    async def get_tickers(self) -> list:
        """Get ticker information for all markets."""
        response = await self.get("/api/v1/market/ticker")
        return response["result"]

    async def get_tokens(self) -> list:
        """Get list of supported tokens."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        response = await self._client.get(self.url + "/api/v1/market/tokens")
        try:
            return response.json()["result"]
        except ValueError:
            return []

    async def get_trades(self, market: str, limit: int = 100) -> list:
        """Get recent trades for a market."""
        await self._ensure_initialized()
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        response = await self.get(
            f"/api/v1/market/trades?marketId={market_id}&limit={limit}"
        )
        return response["result"]

    async def get_balance(self, addr: str) -> list:
        """Get balance for an address."""
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        response = await self.get(f"/api/v1/wallet/balance?address={addr}")
        return response["result"]

    async def get_sessions(self, addr: str) -> list:
        """Get sessions for an address."""
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        response = await self.get(f"/api/v1/wallet/session?address={addr}")
        return response["result"]

    async def get_transfer_history(
        self,
        addr: str,
        token_id: Optional[int] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        limit: int = 100,
    ) -> list:
        """Get transfer history for a wallet address on the L2 network."""
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        params = _clean_params({
            "address": addr,
            "token_id": token_id,
            "from": from_msec,
            "to": to_msec,
            "limit": min(limit, 500),
        })
        response = await self.get("/api/v1/wallet/transfer", params=params)
        return response["result"]

    async def get_open_orders(
        self,
        addr: str,
        market: str,
        limit: int = 100,
        from_msec: Optional[int] = None,
        end_msec: Optional[int] = None,
    ) -> Optional[list]:
        """Get open orders for an address in a market."""
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        await self._ensure_initialized()
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        params = _clean_params(
            {
                "address": addr,
                "marketId": market_id,
                "limit": limit,
                "from": from_msec,
                "to": end_msec,
            }
        )
        response = await self.get("/api/v1/order/open", params=params)
        return response["result"]

    async def get_filled_canceled_orders(
        self,
        addr: str,
        market: str,
        limit: int = 100,
        from_msec: Optional[int] = None,
        end_msec: Optional[int] = None,
    ) -> Optional[list]:
        """Get filled and canceled orders for an address in a market."""
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        await self._ensure_initialized()
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        params = _clean_params(
            {
                "address": addr,
                "marketId": market_id,
                "limit": limit,
                "from": from_msec,
                "to": end_msec,
            }
        )
        response = await self.get("/api/v1/order/", params=params)
        return response["result"]

    async def get_order_by_id(self, order_id: str) -> Optional[dict]:
        """Get order by ID."""
        response = await self.get(f"/api/v1/order/{order_id}")
        if response.get("code") == 404 or "result" not in response:
            return None
        return response["result"]

    async def create_session(
        self, session_id: str, session_wallet: Any, expiry: int, nonce: int
    ) -> dict:
        """Create a new session."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        if self.signer.session_enabled:
            raise ValueError("Session is already enabled")
        data = self.signer.create_session_data(
            DexCommandSessionCreate, session_wallet.address, nonce, expiry
        )
        tx = self.signer.generate_alphasec_transaction(nonce, data, session_wallet)
        response = await self.post(
            "/api/v1/wallet/session",
            params={
                "name": session_id,
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "tx_hash": response["result"] if "result" in response else None,
        }

    async def update_session(
        self, session_id: str, session_wallet: Any, expiry: int, nonce: int
    ) -> dict:
        """Update an existing session."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_session_data(
            DexCommandSessionUpdate, session_wallet.address, nonce, expiry
        )
        tx = self.signer.generate_alphasec_transaction(nonce, data, session_wallet)
        response = await self.post(
            "/api/v1/wallet/session/update",
            params={
                "name": session_id,
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "tx_hash": response["result"] if "result" in response else None,
        }

    async def delete_session(self, session_wallet: Any) -> dict:
        """Delete a session."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        # nonce and expiry is not used in blockchain side
        nonce = int(time.time() * 1000)  # dummy
        expiry = int(time.time() * 1000) + 3600  # dummy

        data = self.signer.create_session_data(
            DexCommandSessionDelete, session_wallet.address, nonce, expiry
        )
        tx = self.signer.generate_alphasec_transaction(nonce, data, session_wallet)
        response = await self.post(
            "/api/v1/wallet/session/delete",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "tx_hash": response["result"] if "result" in response else None,
        }

    async def value_transfer(self, to: str, value: float) -> dict:
        """Transfer native value to an address."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_value_transfer_data(to, value)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/wallet/transfer",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "tx_hash": response["result"] if "result" in response else None,
        }

    async def token_transfer(self, to: str, value: float, token: str) -> dict:
        """Transfer tokens to an address."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        await self._ensure_initialized()
        data = self.signer.create_token_transfer_data(
            to, value, self.symbol_token_id_map[token]
        )
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/wallet/transfer",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "tx_hash": response["result"] if "result" in response else None,
        }

    async def order(
        self,
        market: str,
        side: int,
        price: float,
        quantity: float,
        order_type: int,
        order_mode: int,
        tp_limit: Optional[float] = None,
        sl_trigger: Optional[float] = None,
        sl_limit: Optional[float] = None,
    ) -> dict:
        """Place an order."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        await self._ensure_initialized()
        base_token, quote_token = split_base_quote_token(
            market, self.symbol_token_id_map
        )
        normalized_price, normalized_quantity = normalize_price_quantity(
            price, quantity
        )
        adjusted_quantity = normalized_quantity if order_type == LIMIT else quantity
        data = self.signer.create_order_data(
            base_token,
            quote_token,
            side,
            normalized_price,
            adjusted_quantity,
            order_type,
            order_mode,
            tp_limit,
            sl_trigger,
            sl_limit,
        )
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/order",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "order_id": response["result"] if "result" in response else None,
        }

    async def cancel(self, order_id: str) -> dict:
        """Cancel an order."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_cancel_data(order_id)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/order/cancel",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "order_id": response["result"] if "result" in response else None,
        }

    async def cancel_all(self) -> dict:
        """Cancel all orders."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_cancel_all_data()
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/order/cancel/all",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "order_id": response["result"] if "result" in response else None,
        }

    async def modify(
        self,
        order_id: str,
        new_price: Optional[float] = None,
        new_qty: Optional[float] = None,
        order_mode: Optional[int] = None,
    ) -> dict:
        """Modify an existing order."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        normalized_price, normalized_quantity = normalize_price_quantity(
            new_price or 0.0, new_qty or 0.0
        )
        data = self.signer.create_modify_data(
            order_id, normalized_price, normalized_quantity, order_mode
        )
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/order/modify",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "order_id": response["result"] if "result" in response else None,
        }

    async def stop_order(
        self,
        market: str,
        stop_price: float,
        price: float,
        quantity: float,
        side: int,
        order_type: int,
        order_mode: int,
    ) -> dict:
        """Place a stop order."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")
        if side not in [BUY, SELL]:
            raise ValueError("Invalid side")
        if order_type not in [LIMIT, MARKET]:
            raise ValueError("Invalid order type")
        if order_mode not in [BASE_MODE, QUOTE_MODE]:
            raise ValueError("Invalid order mode")

        await self._ensure_initialized()
        base_token, quote_token = split_base_quote_token(
            market, self.symbol_token_id_map
        )
        normalized_price, normalized_quantity = normalize_price_quantity(
            price, quantity
        )
        normalized_stop_price, _ = normalize_price_quantity(stop_price, quantity)
        data = self.signer.create_stop_order_data(
            base_token,
            quote_token,
            normalized_stop_price,
            normalized_price,
            normalized_quantity,
            side,
            order_type,
            order_mode,
        )
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = await self.post(
            "/api/v1/order/trigger",
            params={
                "tx": tx,
            },
        )
        return {
            "status": response["code"] == 200,
            "error": response["errMsg"],
            "order_id": response["result"] if "result" in response else None,
        }

    async def withdraw_to_kaia(self, symbol: str, value: float) -> dict:
        """Withdraw tokens to Kaia network. Value is in token units."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        await self._ensure_initialized()
        token_id = self.symbol_token_id_map[symbol]
        token_l1_address = self.token_id_address_map.get(token_id)

        l2_provider = None
        if self.signer.network == "mainnet":
            l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_MAINNET_URL))
        else:
            l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_KAIROS_URL))

        tx = self.signer.generate_withdraw_transaction(
            l2_provider, token_id, value, token_l1_address
        )
        response = await self.post(
            "/api/v1/wallet/withdraw",
            params={
                "tx": tx,
            },
        )
        if response["code"] == 200:
            return {
                "status": True,
                "error": None,
                "tx_hash": response["result"] if "result" in response else None,
            }
        else:
            return {
                "status": False,
                "error": "withdraw failed",
                "tx_hash": response["result"] if "result" in response else None,
            }

    async def deposit_to_alphasec(self, symbol: str, value: float) -> dict:
        """Deposit tokens to AlphaSec. Value is in token units."""
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        await self._ensure_initialized()
        token_id = self.symbol_token_id_map[symbol]
        token_l1_address = self.token_id_address_map.get(token_id)

        l1_provider = None
        if self.signer.network == "mainnet":
            l1_provider = web3.Web3(web3.HTTPProvider(MAINNET_URL))
        else:
            l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))

        tx = self.signer.generate_deposit_transaction(
            l1_provider, token_id, value, token_l1_address
        )
        # Wrap blocking web3 calls with asyncio.to_thread to avoid blocking event loop
        txHash = await asyncio.to_thread(l1_provider.eth.send_raw_transaction, tx)
        receipt = await asyncio.to_thread(l1_provider.eth.wait_for_transaction_receipt, txHash)
        if receipt["status"] == 1:
            return {
                "status": True,
                "error": None,
                "tx_hash": txHash,
            }
        else:
            return {
                "status": False,
                "error": "deposit failed",
                "tx_hash": txHash,
            }
