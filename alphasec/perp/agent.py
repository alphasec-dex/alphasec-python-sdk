"""Sync PerpAgent — sub-facade for all perpetual futures (perp) operations.

Accessed via ``agent.perp`` (wiring done in a later phase). Holds a back-reference to
the parent ``Agent`` and reads ``parent.api`` / ``parent.ws`` lazily at call time, so it
works with both the eager sync ``Agent`` and the lazy async lifecycle expectations.

All trading methods resolve ``symbol`` -> numeric ``market_id`` via a lazily-populated
cache (lock-free read fast path; ``threading.Lock`` only around the populate critical
section), backed by ``GET /fapi/v1/market``. All signed-transaction endpoints share a
single ``_submit`` helper; all read endpoints return the raw ``result`` payload.
"""

import threading
import time
from typing import Any, Callable, Optional

from alphasec.api.utils import _clean_params
from alphasec.exceptions import AlphasecAPIError
from alphasec.perp.constants import PERP_TO_SPOT, SPOT_TO_PERP


class PerpAgent:
    """Sub-facade for perpetual futures. Owns all perp REST; does not touch spot API."""

    def __init__(self, agent):
        # Back-reference to the parent Agent. api/ws are read lazily (the async parent
        # creates them only after __aenter__, so capturing them here would bind to None).
        self._agent = agent
        # symbol(str) -> market_id(int). Lock-free reads; lock only the populate section.
        self._market_cache: dict[str, int] = {}
        self._cache_lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Lazy back-reference accessors
    # -----------------------------------------------------------------------

    @property
    def _api(self):
        api = getattr(self._agent, "api", None)
        if api is None:
            raise RuntimeError("Agent API is not initialized")
        return api

    @property
    def _ws(self):
        ws = getattr(self._agent, "ws", None)
        if ws is None:
            raise RuntimeError("Agent WebSocket is not initialized")
        return ws

    @property
    def _signer(self):
        signer = self._api.signer
        if signer is None:
            raise ValueError("Only read-only API is available when signer is not set")
        return signer

    # -----------------------------------------------------------------------
    # Market cache
    # -----------------------------------------------------------------------

    def _resolve_market_id(self, symbol: str) -> int:
        """Resolve a perp ``symbol`` (e.g. "BTCUSDT") to its numeric market_id.

        Fast path: lock-free dict read. Slow path on a miss: fetch markets, populate
        under the lock, then re-read. If the fetch SUCCEEDS but the symbol is still
        absent -> ValueError. If the fetch FAILS, serve a previously-cached value if
        present, else propagate the real transport/api error (never mask it as an
        unknown symbol).
        """
        # Fast path: lock-free read.
        cached = self._market_cache.get(symbol)
        if cached is not None:
            return cached

        # Slow path: populate under the lock (collapses a concurrent miss herd to
        # a single fetch — mirrors the async agent).
        with self._cache_lock:
            # Re-check: another thread may have populated while we waited.
            cached = self._market_cache.get(symbol)
            if cached is not None:
                return cached

            try:
                markets = self.get_markets()
            except Exception:
                # Refresh failed. Serve a previously-cached id if present;
                # otherwise propagate the real error so the caller's retry
                # decision is preserved (never mask it as "unknown symbol").
                cached = self._market_cache.get(symbol)
                if cached is not None:
                    return cached
                raise

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
            self._market_cache = {**self._market_cache, **new_cache}

            resolved = self._market_cache.get(symbol)
            if resolved is None:
                # Fetch succeeded: a missing symbol genuinely does not exist.
                raise ValueError(f"Unknown perp symbol: {symbol}")
            return resolved

    # -----------------------------------------------------------------------
    # Submit / unwrap helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _unwrap(resp: Any) -> Any:
        """Unwrap the ``{code, errMsg, result}`` envelope.

        Raises AlphasecAPIError on a missing/non-200 code (covers the low-level
        ``{"error": ...}`` non-JSON fallback, which has no ``code``). Returns ``result``.
        """
        code = resp.get("code") if isinstance(resp, dict) else None
        if code != 200:
            err_msg = resp.get("errMsg") if isinstance(resp, dict) else None
            if err_msg is None and isinstance(resp, dict):
                err_msg = resp.get("error")
            raise AlphasecAPIError(f"{code}: {err_msg}")
        return resp.get("result")

    def _submit(self, path: str, data: bytes) -> str:
        """Sign ``data``, POST ``{"tx": signed}`` to ``path``, return the tx-hash string."""
        tx = self._signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        resp = self._api.post(path, {"tx": tx})
        return self._unwrap(resp)

    # -----------------------------------------------------------------------
    # Trading / funds
    # -----------------------------------------------------------------------

    def order(
        self,
        symbol: str,
        side: int,
        price,
        quantity,
        tif: int,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> str:
        """Place a new perp order. Returns the accepted tx hash (not an order_id).

        Price/quantity are NOT auto-normalized: the caller must round them to the
        market's ``tickSize``/``lotSize`` (from ``get_markets``) and satisfy
        ``minNotional``, otherwise the server rejects the order.
        """
        market_id = self._resolve_market_id(symbol)
        data = self._signer.create_perp_order_data(
            market_id, side, price, quantity, reduce_only, tif, client_order_id
        )
        return self._submit("/fapi/v1/order", data)

    def cancel(self, symbol: str, order_id: str) -> str:
        """Cancel an open perp order by order_id. Returns the tx hash."""
        market_id = self._resolve_market_id(symbol)
        data = self._signer.create_perp_cancel_data(market_id, order_id)
        return self._submit("/fapi/v1/order/cancel", data)

    def cancel_all(self, symbol: str) -> str:
        """Cancel all open perp orders for a symbol (market-scoped). Returns the tx hash."""
        market_id = self._resolve_market_id(symbol)
        data = self._signer.create_perp_cancel_all_data(market_id)
        return self._submit("/fapi/v1/order/cancel/all", data)

    def modify(
        self,
        symbol: str,
        order_id: str,
        new_price=None,
        new_quantity=None,
        client_order_id: Optional[str] = None,
    ) -> str:
        """Modify an open perp order via cancel-and-replace. Returns the tx hash."""
        market_id = self._resolve_market_id(symbol)
        data = self._signer.create_perp_modify_data(
            market_id, order_id, new_price, new_quantity, client_order_id
        )
        return self._submit("/fapi/v1/order/modify", data)

    def set_leverage(self, symbol: str, leverage: int) -> str:
        """Set leverage for a symbol (market-scoped). Returns the tx hash."""
        market_id = self._resolve_market_id(symbol)
        data = self._signer.create_perp_set_leverage_data(market_id, leverage)
        return self._submit("/fapi/v1/position/leverage", data)

    def transfer(self, direction: int, token: str, amount) -> str:
        """Transfer margin between Spot and Perp wallets.

        SPOT_TO_PERP -> deposit wire (0x12) + POST /fapi/v1/wallet/deposit.
        PERP_TO_SPOT -> withdraw wire (0x44) + POST /fapi/v1/wallet/withdraw.

        ``token`` may be a symbol (e.g. "USDT") or a numeric token id. The wire
        requires the numeric id (the server rejects a symbol with -1103 "token must
        be a 64-bit unsigned integer"), so the symbol is resolved via the token map;
        an id passed directly falls through unchanged. Mirrors spot token_transfer.
        """
        self._api._ensure_initialized()
        token_id = self._api.symbol_token_id_map.get(token, token)
        if direction == SPOT_TO_PERP:
            data = self._signer.create_perp_deposit_data(token_id, amount)
            return self._submit("/fapi/v1/wallet/deposit", data)
        elif direction == PERP_TO_SPOT:
            data = self._signer.create_perp_withdraw_data(token_id, amount)
            return self._submit("/fapi/v1/wallet/withdraw", data)
        raise ValueError(f"Unknown transfer direction: {direction}")

    # -----------------------------------------------------------------------
    # Account / position queries
    # -----------------------------------------------------------------------

    def get_account(self) -> dict:
        """Get perp account balances and risk aggregates."""
        params = _clean_params({"address": self._signer.l1_address})
        return self._unwrap(self._api.get("/fapi/v1/wallet/account", params))

    def get_positions(self) -> list[dict]:
        """Get all open positions. Unwraps ``result.positions``."""
        params = _clean_params({"address": self._signer.l1_address})
        result = self._unwrap(self._api.get("/fapi/v1/position", params))
        if isinstance(result, dict):
            return result.get("positions", [])
        return result

    def get_position_history(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get position lifecycle history (offset paging; no cursor)."""
        params = _clean_params({
            "address": self._signer.l1_address,
            "marketId": market_id,
            "from": from_msec,
            "to": to_msec,
            "limit": limit,
        })
        return self._unwrap(self._api.get("/fapi/v1/position/history", params))

    def get_position_settings(self) -> list[dict]:
        """Get per-market leverage / margin-mode settings."""
        params = _clean_params({"address": self._signer.l1_address})
        return self._unwrap(self._api.get("/fapi/v1/position/settings", params))

    def get_funding(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get funding payment history (keyset cursor via lastID)."""
        params = _clean_params({
            "address": self._signer.l1_address,
            "marketId": market_id,
            "from": from_msec,
            "to": to_msec,
            "lastID": last_id,
            "limit": limit,
        })
        return self._unwrap(self._api.get("/fapi/v1/wallet/funding", params))

    # -----------------------------------------------------------------------
    # Order queries
    # -----------------------------------------------------------------------

    def get_open_orders(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get open orders."""
        params = _clean_params({
            "address": self._signer.l1_address,
            "marketId": market_id,
            "from": from_msec,
            "to": to_msec,
            "lastID": last_id,
            "limit": limit,
        })
        return self._unwrap(self._api.get("/fapi/v1/order/open", params))

    def get_order_history(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get order history (filled / cancelled)."""
        params = _clean_params({
            "address": self._signer.l1_address,
            "marketId": market_id,
            "from": from_msec,
            "to": to_msec,
            "lastID": last_id,
            "limit": limit,
        })
        return self._unwrap(self._api.get("/fapi/v1/order", params))

    def get_order(self, order_id: str) -> dict:
        """Get a single order by ID."""
        return self._unwrap(self._api.get(f"/fapi/v1/order/{order_id}", None))

    def get_order_list(self, tx_hash: str) -> list[dict]:
        """Get orders submitted in a given transaction (by tx hash)."""
        params = _clean_params({"txHash": tx_hash})
        return self._unwrap(self._api.get("/fapi/v1/order/list", params))

    def get_my_trades(
        self,
        market_id: Optional[str] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        last_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Get personal trade history (fills)."""
        params = _clean_params({
            "address": self._signer.l1_address,
            "marketId": market_id,
            "from": from_msec,
            "to": to_msec,
            "lastID": last_id,
            "limit": limit,
        })
        return self._unwrap(self._api.get("/fapi/v1/order/trade", params))

    # -----------------------------------------------------------------------
    # Market data queries
    # -----------------------------------------------------------------------

    def get_markets(self) -> list[dict]:
        """Get all perp markets. Unwraps ``result.symbols``."""
        result = self._unwrap(self._api.get("/fapi/v1/market", None))
        if isinstance(result, dict):
            return result.get("symbols", [])
        return result

    def get_tickers(self) -> list[dict]:
        """Get tickers for all markets."""
        return self._unwrap(self._api.get("/fapi/v1/market/ticker", None))

    def get_ticker(self, symbol: str) -> dict:
        """Get ticker for a specific symbol (server returns a 1-element array)."""
        market_id = self._resolve_market_id(symbol)
        params = _clean_params({"marketId": str(market_id)})
        result = self._unwrap(self._api.get("/fapi/v1/market/ticker", params))
        if not result:
            raise AlphasecAPIError(f"No ticker found for symbol: {symbol}")
        return result[0]

    def get_depth(self, symbol: str, limit: int = 100) -> dict:
        """Get order book depth snapshot."""
        market_id = self._resolve_market_id(symbol)
        # limit is always sent (matches rust + the async agent); never dropped.
        params = {"marketId": str(market_id), "limit": str(limit if limit is not None else 100)}
        return self._unwrap(self._api.get("/fapi/v1/market/depth", params))

    def get_market_trades(self, symbol: str, limit: int = 100) -> list[dict]:
        """Get recent public trades."""
        market_id = self._resolve_market_id(symbol)
        # limit is always sent (matches rust + the async agent); never dropped.
        params = {"marketId": str(market_id), "limit": str(limit if limit is not None else 100)}
        return self._unwrap(self._api.get("/fapi/v1/market/trades", params))

    def get_candles(
        self,
        symbol: str,
        resolution: str,
        from_sec: Optional[int] = None,
        to_sec: Optional[int] = None,
    ) -> list[dict]:
        """Get OHLCV candles. ``resolution`` is validated server-side, not by the SDK.

        Note: unlike the other queries (which use epoch milliseconds), the candles
        endpoint expects ``from``/``to`` in epoch SECONDS, and both are required
        (the server returns -1100 for a missing/invalid range).
        """
        market_id = self._resolve_market_id(symbol)
        params = _clean_params({
            "marketId": str(market_id),
            "resolution": resolution,
            "from": from_sec,
            "to": to_sec,
        })
        return self._unwrap(self._api.get("/fapi/v1/market/candles", params))

    # -----------------------------------------------------------------------
    # WebSocket — forward the perp channel string straight to the WS manager.
    # -----------------------------------------------------------------------

    def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], None],
        timeout: Optional[int] = None,
    ) -> int:
        """Subscribe to a perp WS channel (channel routing handled by the WS lane)."""
        return self._ws.subscribe(channel, callback, timeout=timeout)

    def unsubscribe(
        self,
        channel: str,
        subscription_id: int,
        timeout: Optional[int] = None,
    ) -> bool:
        """Unsubscribe from a perp WS channel."""
        return self._ws.unsubscribe(channel, subscription_id, timeout=timeout)
