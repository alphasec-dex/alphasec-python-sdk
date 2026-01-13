"""Async Agent for AlphaSec DEX.

Provides a high-level async interface combining AsyncAPI and AsyncWebsocketManager.
"""
from typing import Any, Callable, Optional, Union
import asyncio

from alphasec.api.async_api import AsyncAPI
from alphasec.websocket.async_ws import AsyncWebsocketManager
from alphasec.transaction.sign import AlphasecSigner
from alphasec.api.utils import market_to_market_id


class AsyncAgent:
    """Async agent combining API and WebSocket functionality.

    Provides async versions of all Agent methods for use in async applications.

    Example:
        >>> async with AsyncAgent(base_url, signer=signer) as agent:
        ...     await agent.start()
        ...     markets = await agent.get_market_list()
        ...     await agent.subscribe('trade@KAIA/USDT', handle_trade)
        ...     await agent.stop()
    """

    def __init__(
        self,
        base_url: str,
        signer: Optional[AlphasecSigner] = None,
        timeout: Optional[float] = None,
    ):
        self._base_url = base_url
        self._signer = signer
        self._timeout = timeout
        self.api: Optional[AsyncAPI] = None
        self.ws: Optional[AsyncWebsocketManager] = None
        self._ws_task: Optional[asyncio.Task] = None

    async def __aenter__(self) -> "AsyncAgent":
        """Async context manager entry."""
        self.api = AsyncAPI(self._base_url, timeout=self._timeout, signer=self._signer)
        await self.api._ensure_initialized()
        self.ws = AsyncWebsocketManager(self._base_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
        if self.api is not None:
            await self.api.close()

    async def _ensure_initialized(self) -> None:
        """Ensure API and WebSocket are initialized."""
        if self.api is None:
            self.api = AsyncAPI(self._base_url, timeout=self._timeout, signer=self._signer)
            await self.api._ensure_initialized()
        if self.ws is None:
            self.ws = AsyncWebsocketManager(self._base_url)

    # WebSocket lifecycle
    async def start(self) -> None:
        """Start the WebSocket connection and message loop."""
        await self._ensure_initialized()
        assert self.ws is not None
        await self.ws.connect()
        self._ws_task = asyncio.create_task(self.ws.run())

    async def stop(self) -> None:
        """Stop the WebSocket connection."""
        if self.ws is not None:
            await self.ws.stop()
        if self._ws_task is not None and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

    # WebSocket subscriptions
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], None],
        timeout: Optional[int] = None,
    ) -> int:
        """
        Subscribe to WebSocket channels with user-friendly channel format.

        Parameters
        ----------
        channel : str
            Channel in format 'type@target':
            - 'trade@KAIA/USDT' for trade data
            - 'ticker@BTC/USDT' for ticker data
            - 'depth@ETH/USDT' for order book
            - 'userEvent@0x123...' for user events
        callback : Callable
            Function to handle received messages
        timeout : int, optional
            Timeout in seconds

        Returns
        -------
        int
            Subscription ID for later unsubscribing

        Examples
        --------
        await agent.subscribe('trade@KAIA/USDT', print_trades)
        await agent.subscribe('userEvent@0x123...', print_events)
        """
        await self._ensure_initialized()
        assert self.api is not None
        assert self.ws is not None

        if '@' not in channel:
            raise ValueError(f"Channel format should be 'type@target', got: {channel}")

        channel_type, target = channel.split('@', 1)

        if channel_type in ['trade', 'ticker', 'depth']:
            # Convert market name to market_id
            market_id = market_to_market_id(target, self.api.symbol_token_id_map)
            actual_channel = f"{channel_type}@{market_id}"
        elif channel_type == 'userEvent':
            # Use address directly
            actual_channel = f"{channel_type}@{target}"
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}. Use 'trade', 'ticker', 'depth', or 'userEvent'")

        return await self.ws.subscribe(actual_channel, callback, timeout=timeout)

    async def unsubscribe(
        self,
        channel: str,
        subscription_id: int,
        timeout: Optional[int] = None,
    ) -> bool:
        """
        Unsubscribe from WebSocket channels with user-friendly channel format.

        Parameters
        ----------
        channel : str
            Channel in format 'type@target' (same as used in subscribe)
        subscription_id : int
            ID returned from subscribe()
        timeout : int, optional
            Timeout in seconds

        Examples
        --------
        await agent.unsubscribe('trade@KAIA/USDT', sub_id)
        await agent.unsubscribe('userEvent@0x123...', sub_id)
        """
        await self._ensure_initialized()
        assert self.api is not None
        assert self.ws is not None

        if '@' not in channel:
            raise ValueError(f"Channel format should be 'type@target', got: {channel}")

        channel_type, target = channel.split('@', 1)

        if channel_type in ['trade', 'ticker', 'depth']:
            # Convert market name to market_id
            market_id = market_to_market_id(target, self.api.symbol_token_id_map)
            actual_channel = f"{channel_type}@{market_id}"
        elif channel_type == 'userEvent':
            # Use address directly
            actual_channel = f"{channel_type}@{target}"
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}. Use 'trade', 'ticker', 'depth', or 'userEvent'")

        return await self.ws.unsubscribe(actual_channel, subscription_id, timeout=timeout)

    # API helpers (commonly used)
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
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.order(market, side, price, quantity, order_type, order_mode, tp_limit, sl_trigger, sl_limit)

    async def cancel(self, order_id: str) -> dict:
        """Cancel an order."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.cancel(order_id)

    async def cancel_all(self) -> dict:
        """Cancel all orders."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.cancel_all()

    async def modify(
        self,
        order_id: str,
        new_price: Optional[float] = None,
        new_qty: Optional[float] = None,
        order_mode: Optional[int] = None,
    ) -> dict:
        """Modify an existing order."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.modify(order_id, new_price, new_qty, order_mode)

    async def value_transfer(self, to: str, value: float) -> dict:
        """Transfer native value to an address."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.value_transfer(to, value)

    async def token_transfer(self, to: str, value: float, token: str) -> dict:
        """Transfer tokens to an address."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.token_transfer(to, value, token)

    async def withdraw(self, token: str, value: float) -> dict:
        """Withdraw tokens to Kaia with balance check."""
        await self._ensure_initialized()
        assert self.api is not None

        if self.api.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        balances = await self.get_balance(self.api.signer.l1_address)
        try:
            token_id = self.api.symbol_token_id_map[token]
        except KeyError:
            raise ValueError(f"Unknown token symbol: {token}")

        # balances may be a list of { tokenId, locked, unlocked }
        available: Union[float, int, str] = 0
        if isinstance(balances, list):
            matched = next((b for b in balances if str(b.get('tokenId')) == str(token_id)), None)
            if matched is not None:
                available = matched.get('unlocked', 0)

        try:
            available_float = float(available)
        except (TypeError, ValueError):
            available_float = 0.0

        if available_float < value:
            raise ValueError("Insufficient balance")

        return await self.api.withdraw_to_kaia(token, value)

    async def deposit(self, token: str, value: float) -> dict:
        """Deposit tokens to AlphaSec."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.deposit_to_alphasec(token, value)

    # Market data helpers
    async def get_depth(self, market: str, limit: int = 100) -> dict:
        """Get order book depth for a market."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_depth(market, limit)

    async def get_ticker(self, market: str) -> dict:
        """Get ticker for a market."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_ticker(market)

    async def get_tickers(self) -> list:
        """Get all tickers."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_tickers()

    async def get_market_list(self) -> list:
        """Get list of available markets."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_market_list()

    async def get_trades(self, market: str, limit: int = 100) -> list:
        """Get recent trades for a market."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_trades(market, limit)

    async def get_tokens(self) -> list:
        """Get list of supported tokens."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_tokens()

    # Order history helpers
    async def get_open_orders(
        self,
        addr: str,
        market: str,
        limit: int = 100,
        from_msec: Optional[int] = None,
        end_msec: Optional[int] = None,
    ) -> list:
        """Get open orders for an address."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_open_orders(addr, market, limit, from_msec, end_msec)

    async def get_filled_canceled_orders(
        self,
        addr: str,
        market: str,
        limit: int = 100,
        from_msec: Optional[int] = None,
        end_msec: Optional[int] = None,
    ) -> list:
        """Get filled/canceled orders for an address."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_filled_canceled_orders(addr, market, limit, from_msec, end_msec)

    async def get_order_by_id(self, order_id: str) -> Optional[dict]:
        """Get order details by ID."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_order_by_id(order_id)

    # Wallet/session helpers
    async def get_balance(self, addr: str) -> list:
        """Get balance for an address."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_balance(addr)

    async def get_sessions(self, addr: str) -> list:
        """Get sessions for an address."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_sessions(addr)

    async def get_transfer_history(
        self,
        addr: str,
        token_id: Optional[int] = None,
        from_msec: Optional[int] = None,
        to_msec: Optional[int] = None,
        limit: int = 100,
    ) -> list:
        """Get transfer history for a wallet address on the L2 network."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.get_transfer_history(addr, token_id, from_msec, to_msec, limit)

    # Session management
    async def create_session(
        self,
        session_id: str,
        session_wallet: Any,
        expiry: int,
        nonce: int,
    ) -> dict:
        """Create a new session."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.create_session(session_id, session_wallet, expiry, nonce)

    async def update_session(
        self,
        session_id: str,
        session_wallet: Any,
        expiry: int,
        nonce: int,
    ) -> dict:
        """Update an existing session."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.update_session(session_id, session_wallet, expiry, nonce)

    async def delete_session(self, session_wallet: Any) -> dict:
        """Delete a session."""
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.delete_session(session_wallet)

    # Additional trading helpers
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
        await self._ensure_initialized()
        assert self.api is not None
        return await self.api.stop_order(market, stop_price, price, quantity, side, order_type, order_mode)
