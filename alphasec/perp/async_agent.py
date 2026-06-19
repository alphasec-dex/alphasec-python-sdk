"""Async PerpAgent sub-facade — async mirror of the sync PerpAgent.

Access via ``async_agent.perp`` (wired in a later phase). All trading methods
resolve ``symbol`` -> ``market_id`` via a lazily-populated cache backed by
GET /fapi/v1/market. Reads are lock-free once the cache is warm; the populate
critical section is guarded by an ``asyncio.Lock``.

Lifecycle note: ``AsyncAgent`` creates ``api``/``ws`` lazily (None until
``__aenter__`` / ``_ensure_initialized``). This sub-agent therefore holds a
back-reference to its parent and reads ``parent.api`` / ``parent.ws`` LAZILY at
call time, raising a clear ``RuntimeError`` if not yet initialized.
"""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Any, Callable, Optional, Union

from alphasec.exceptions import AlphasecAPIError
from alphasec.perp.constants import PERP_TO_SPOT, SPOT_TO_PERP

# Default server-side page size applied for /market/depth and /market/trades
# when the caller passes limit=None (matches rust DEFAULT_LIMIT).
DEFAULT_LIMIT = 100

PerpNumber = Union[Decimal, str]


class AsyncPerpAgent:
    """Sub-facade for all perpetual futures operations (async).

    Constructed with a back-reference to the parent ``AsyncAgent``; the
    parent's ``api``/``ws`` are read lazily at call time so this works with the
    parent's lazy initialization.
    """

    def __init__(self, agent: Any) -> None:
        """Create a new AsyncPerpAgent.

        Args:
            agent: The parent AsyncAgent. Its ``api``/``ws`` are read lazily.
        """
        self._agent = agent
        # symbol(str) -> market_id(int); populated lazily on first miss.
        self._market_cache: dict[str, int] = {}
        # Guards only the populate critical section; reads are lock-free.
        self._cache_lock = asyncio.Lock()

    # -----------------------------------------------------------------------
    # Lazy parent accessors
    # -----------------------------------------------------------------------

    @property
    def _api(self):
        api = self._agent.api
        if api is None:
            raise RuntimeError(
                "AsyncAgent is not initialized; use 'async with AsyncAgent(...)' "
                "or await agent._ensure_initialized()"
            )
        return api

    @property
    def _ws(self):
        ws = self._agent.ws
        if ws is None:
            raise RuntimeError(
                "AsyncAgent is not initialized; use 'async with AsyncAgent(...)' "
                "or await agent._ensure_initialized()"
            )
        return ws

    @property
    def _signer(self):
        signer = self._api.signer
        if signer is None:
            raise ValueError(
                "Only read-only API is available when signer is not set"
            )
        return signer

    @property
    def _address(self) -> str:
        # Route through the guarded _signer so a missing signer raises the same
        # ValueError as the sync agent (not an AttributeError on None).
        return self._signer.l1_address

    # -----------------------------------------------------------------------
    # Internal: market cache
    # -----------------------------------------------------------------------

    async def _resolve_market_id(self, symbol: str) -> int:
        """Resolve a symbol to its numeric market_id.

        Fast path is a lock-free dict read. On a miss, fetch markets under the
        populate lock and re-read. If the symbol is still absent after a
        SUCCESSFUL fetch, raise ValueError. If the fetch FAILS, serve a
        previously-cached value if present, otherwise propagate the real
        transport/api error (do NOT mask it as "unknown symbol").
        """
        # Fast path: lock-free read.
        cached = self._market_cache.get(symbol)
        if cached is not None:
            return cached

        # Slow path: populate under the lock.
        async with self._cache_lock:
            # Re-check: another coroutine may have populated while we waited.
            cached = self._market_cache.get(symbol)
            if cached is not None:
                return cached

            try:
                markets = await self.get_markets()
            except Exception as exc:
                # Fetch failed. Serve a previously-cached value if present;
                # otherwise propagate the real error (masking it as an unknown
                # symbol would corrupt the caller's retry decision).
                cached = self._market_cache.get(symbol)
                if cached is not None:
                    return cached
                raise exc

            # Build-then-swap so concurrent lock-free readers never observe a
            # partially populated map.
            new_cache: dict[str, int] = {}
            for m in markets:
                market_id = m.get("marketId")
                sym = m.get("symbol")
                if market_id is None or sym is None:
                    continue
                try:
                    new_cache[sym] = int(market_id)
                except (TypeError, ValueError):
                    continue
            # Preserve any prior entries not present in the fresh fetch.
            merged = {**self._market_cache, **new_cache}
            self._market_cache = merged

            resolved = self._market_cache.get(symbol)
            if resolved is None:
                # Fetch succeeded: a missing symbol genuinely does not exist.
                raise ValueError(f"Unknown perp symbol: {symbol}")
            return resolved

    # -----------------------------------------------------------------------
    # Internal: sign and submit helpers
    # -----------------------------------------------------------------------

    async def _submit(self, path: str, data: bytes) -> str:
        """Sign ``data`` and POST ``{"tx": ...}`` to ``path``; return tx hash.

        Raises:
            AlphasecAPIError: If the response envelope code != 200.
        """
        tx = self._signer.generate_alphasec_transaction(
            int(time.time() * 1000), data
        )
        resp = await self._api.post(path, {"tx": tx})
        return _unwrap_submit(resp)

    # -----------------------------------------------------------------------
    # Trading methods
    # -----------------------------------------------------------------------

    async def order(
        self,
        symbol: str,
        side: int,
        price: PerpNumber,
        quantity: PerpNumber,
        tif: int,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> str:
        """Place a new perp limit/market order. Returns the submit tx hash.

        Price/quantity are NOT auto-normalized: the caller must round them to the
        market's ``tickSize``/``lotSize`` (from ``get_markets``) and satisfy
        ``minNotional``, otherwise the server rejects the order.
        """
        market_id = await self._resolve_market_id(symbol)
        data = self._signer.create_perp_order_data(
            market_id,
            side,
            price,
            quantity,
            reduce_only,
            tif,
            client_order_id,
        )
        return await self._submit("/fapi/v1/order", data)

    async def cancel(self, symbol: str, order_id: str) -> str:
        """Cancel an open perp order by order ID. Returns the submit tx hash."""
        market_id = await self._resolve_market_id(symbol)
        data = self._signer.create_perp_cancel_data(market_id, order_id)
        return await self._submit("/fapi/v1/order/cancel", data)

    async def cancel_all(self, symbol: str) -> str:
        """Cancel all open perp orders for a symbol (market-scoped)."""
        market_id = await self._resolve_market_id(symbol)
        data = self._signer.create_perp_cancel_all_data(market_id)
        return await self._submit("/fapi/v1/order/cancel/all", data)

    async def modify(
        self,
        symbol: str,
        order_id: str,
        new_price: Optional[PerpNumber] = None,
        new_quantity: Optional[PerpNumber] = None,
        client_order_id: Optional[str] = None,
    ) -> str:
        """Modify (amend) an open perp order via cancel-and-replace (0x4A).

        ``None`` fields are omitted from the wire so the server inherits the
        existing value. Returns the submit tx hash.
        """
        market_id = await self._resolve_market_id(symbol)
        data = self._signer.create_perp_modify_data(
            market_id,
            order_id,
            new_price,
            new_quantity,
            client_order_id,
        )
        return await self._submit("/fapi/v1/order/modify", data)

    async def transfer(self, direction: int, token: str, amount: PerpNumber) -> str:
        """Transfer margin between Spot and Perp wallets.

        ``SPOT_TO_PERP`` (0) -> deposit wire (0x12) -> /fapi/v1/wallet/deposit.
        ``PERP_TO_SPOT`` (1) -> withdraw wire (0x44) -> /fapi/v1/wallet/withdraw.
        Returns the submit tx hash.

        ``token`` may be a symbol (e.g. "USDT") or a numeric token id. The wire
        requires the numeric id (the server rejects a symbol with -1103 "token must
        be a 64-bit unsigned integer"), so the symbol is resolved via the token map;
        an id passed directly falls through unchanged. Mirrors spot token_transfer.
        """
        await self._api._ensure_initialized()
        token_id = self._api.symbol_token_id_map.get(token, token)
        if direction == SPOT_TO_PERP:
            data = self._signer.create_perp_deposit_data(token_id, amount)
            path = "/fapi/v1/wallet/deposit"
        elif direction == PERP_TO_SPOT:
            data = self._signer.create_perp_withdraw_data(token_id, amount)
            path = "/fapi/v1/wallet/withdraw"
        else:
            raise ValueError(f"Invalid transfer direction: {direction}")
        return await self._submit(path, data)

    async def set_leverage(self, symbol: str, leverage: int) -> str:
        """Set leverage for a symbol. Returns the submit tx hash."""
        market_id = await self._resolve_market_id(symbol)
        data = self._signer.create_perp_set_leverage_data(market_id, leverage)
        return await self._submit("/fapi/v1/position/leverage", data)

    # -----------------------------------------------------------------------
    # Account / position queries
    # -----------------------------------------------------------------------

    async def get_account(self) -> dict:
        """Get perp account balances and risk aggregates."""
        resp = await self._api.get(
            "/fapi/v1/wallet/account", {"address": self._address}
        )
        return _unwrap_query(resp)

    async def get_positions(self) -> list:
        """Get all open positions. Unwraps ``result.positions``."""
        resp = await self._api.get("/fapi/v1/position", {"address": self._address})
        result = _unwrap_query(resp)
        if isinstance(result, dict):
            return result.get("positions", [])
        return result

    async def get_position_history(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Get position lifecycle history (offset paging; no lastID cursor)."""
        params = _clean(
            {
                "address": self._address,
                "marketId": market_id,
                "from": from_msec,
                "to": to_msec,
                "limit": limit,
            }
        )
        resp = await self._api.get("/fapi/v1/position/history", params)
        return _unwrap_query(resp)

    async def get_position_settings(self) -> list:
        """Get per-market leverage / margin-mode settings."""
        resp = await self._api.get(
            "/fapi/v1/position/settings", {"address": self._address}
        )
        return _unwrap_query(resp)

    async def get_funding(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Get funding payment history (keyset cursor: uppercase lastID)."""
        params = _clean(
            {
                "address": self._address,
                "marketId": market_id,
                "from": from_msec,
                "to": to_msec,
                "lastID": last_id,
                "limit": limit,
            }
        )
        resp = await self._api.get("/fapi/v1/wallet/funding", params)
        return _unwrap_query(resp)

    # -----------------------------------------------------------------------
    # Order queries
    # -----------------------------------------------------------------------

    async def get_open_orders(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Get open orders."""
        params = _order_params(
            self._address, market_id, from_msec, to_msec, last_id, limit
        )
        resp = await self._api.get("/fapi/v1/order/open", params)
        return _unwrap_query(resp)

    async def get_order_history(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Get order history (filled / cancelled)."""
        params = _order_params(
            self._address, market_id, from_msec, to_msec, last_id, limit
        )
        resp = await self._api.get("/fapi/v1/order", params)
        return _unwrap_query(resp)

    async def get_order(self, order_id: str) -> dict:
        """Get a single order by ID."""
        resp = await self._api.get(f"/fapi/v1/order/{order_id}")
        return _unwrap_query(resp)

    async def get_order_list(self, tx_hash: str) -> list:
        """Get orders submitted in a given transaction (by tx hash)."""
        resp = await self._api.get("/fapi/v1/order/list", {"txHash": tx_hash})
        return _unwrap_query(resp)

    async def get_my_trades(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Get personal trade history (fills)."""
        params = _order_params(
            self._address, market_id, from_msec, to_msec, last_id, limit
        )
        resp = await self._api.get("/fapi/v1/order/trade", params)
        return _unwrap_query(resp)

    # -----------------------------------------------------------------------
    # Market data queries
    # -----------------------------------------------------------------------

    async def get_markets(self) -> list:
        """Get all perp markets. Unwraps ``result.symbols``."""
        resp = await self._api.get("/fapi/v1/market")
        result = _unwrap_query(resp)
        if isinstance(result, dict):
            return result.get("symbols", [])
        return result

    async def get_tickers(self) -> list:
        """Get tickers for all markets."""
        resp = await self._api.get("/fapi/v1/market/ticker")
        return _unwrap_query(resp)

    async def get_ticker(self, symbol: str) -> dict:
        """Get ticker for a specific symbol."""
        market_id = await self._resolve_market_id(symbol)
        resp = await self._api.get(
            "/fapi/v1/market/ticker", {"marketId": str(market_id)}
        )
        tickers = _unwrap_query(resp)
        if not tickers:
            raise AlphasecAPIError(f"No ticker found for symbol: {symbol}")
        return tickers[0]

    async def get_depth(self, symbol: str, limit: int = 100) -> dict:
        """Get order book depth snapshot."""
        market_id = await self._resolve_market_id(symbol)
        params = {
            "marketId": str(market_id),
            "limit": str(limit if limit is not None else DEFAULT_LIMIT),
        }
        resp = await self._api.get("/fapi/v1/market/depth", params)
        return _unwrap_query(resp)

    async def get_market_trades(self, symbol: str, limit: int = 100) -> list:
        """Get recent public trades."""
        market_id = await self._resolve_market_id(symbol)
        params = {
            "marketId": str(market_id),
            "limit": str(limit if limit is not None else DEFAULT_LIMIT),
        }
        resp = await self._api.get("/fapi/v1/market/trades", params)
        return _unwrap_query(resp)

    async def get_candles(
        self,
        symbol: str,
        resolution: str,
        from_sec: Optional[int] = None,
        to_sec: Optional[int] = None,
    ) -> list:
        """Get OHLCV candles.

        Note: unlike the other queries (which use epoch milliseconds), the candles
        endpoint expects ``from``/``to`` in epoch SECONDS, and both are required
        (the server returns -1100 for a missing/invalid range).
        """
        market_id = await self._resolve_market_id(symbol)
        params = _clean(
            {
                "marketId": str(market_id),
                "resolution": resolution,
                "from": from_sec,
                "to": to_sec,
            }
        )
        resp = await self._api.get("/fapi/v1/market/candles", params)
        return _unwrap_query(resp)

    # -----------------------------------------------------------------------
    # WebSocket
    # -----------------------------------------------------------------------

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], Any],
        timeout: Optional[float] = None,
    ) -> int:
        """Subscribe to a perp WebSocket channel (raw channel string)."""
        return await self._ws.subscribe(channel, callback, timeout=timeout)

    async def unsubscribe(
        self,
        channel: str,
        subscription_id: int,
        timeout: Optional[float] = None,
    ) -> bool:
        """Unsubscribe from a perp WebSocket channel."""
        return await self._ws.unsubscribe(
            channel, subscription_id, timeout=timeout
        )


# ---------------------------------------------------------------------------
# Module-level helpers (pure)
# ---------------------------------------------------------------------------


def _clean(params: dict) -> dict:
    """Drop keys whose value is None (omit absent optional query params)."""
    return {k: v for k, v in params.items() if v is not None}


def _order_params(
    address: str,
    market_id: Optional[str],
    from_msec: Optional[int],
    to_msec: Optional[int],
    last_id: Optional[int],
    limit: Optional[int],
) -> dict:
    """Build the shared address + order-query param dict (uppercase lastID)."""
    return _clean(
        {
            "address": address,
            "marketId": market_id,
            "from": from_msec,
            "to": to_msec,
            "lastID": last_id,
            "limit": limit,
        }
    )


def _unwrap_submit(resp: dict) -> str:
    """Unwrap a submit envelope: return the tx-hash result string.

    The low-level api.post returns the parsed JSON envelope, or
    ``{"error": ...}`` on a non-JSON body. Treat a missing or non-200 code as
    an error.
    """
    if not isinstance(resp, dict) or resp.get("code") != 200:
        _raise_envelope_error(resp)
    return resp.get("result")


def _unwrap_query(resp: dict):
    """Unwrap a query envelope: return the raw ``result`` (dict / list)."""
    if not isinstance(resp, dict) or resp.get("code") != 200:
        _raise_envelope_error(resp)
    return resp.get("result")


def _raise_envelope_error(resp: Any) -> None:
    """Raise AlphasecAPIError from an error envelope or non-JSON body."""
    if isinstance(resp, dict):
        if "error" in resp and "code" not in resp:
            raise AlphasecAPIError(str(resp["error"]))
        code = resp.get("code", "unknown")
        err_msg = resp.get("errMsg", "unknown error")
        raise AlphasecAPIError(f"{code}: {err_msg}")
    raise AlphasecAPIError(f"unexpected response: {resp!r}")
