from typing import Any, Callable, Optional

from alphasec.api.api import API
from alphasec.websocket.ws import WebsocketManager
from alphasec.transaction.sign import AlphasecSigner
from alphasec.api.utils import market_to_market_id


class Agent:
    def __init__(self, base_url: str, signer: Optional[AlphasecSigner] = None, timeout: Optional[int] = None):
        self.api = API(base_url, timeout=timeout, signer=signer)
        self.ws = WebsocketManager(base_url)

    # WebSocket lifecycle
    def start(self) -> None:
        self.ws.start()

    def stop(self) -> None:
        self.ws.stop()

    # WebSocket subscriptions
    def subscribe(self, channel: str, callback: Callable[[Any], None], timeout: Optional[int] = None) -> int:
        """
        Subscribe to WebSocket channels with user-friendly channel format.
        
        Parameters
        ----------
        channel : str
            Channel in format 'type@target':
            - 'trades@KAIA/USDT' for trade data
            - 'ticker@BTC/USDT' for ticker data  
            - 'depth@ETH/USDT' for order book
            - 'userEvents@0x123...' for user events
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
        agent.subscribe('trades@KAIA/USDT', print_trades)
        agent.subscribe('userEvents@0x123...', print_events)
        """
        if '@' not in channel:
            raise ValueError(f"Channel format should be 'type@target', got: {channel}")
            
        channel_type, target = channel.split('@', 1)
        
        if channel_type in ['trades', 'ticker', 'depth']:
            # Convert market name to market_id
            market_id = market_to_market_id(target, self.api.symbol_token_id_map)
            actual_channel = f"{channel_type}@{market_id}"
        elif channel_type == 'userEvents':
            # Use address directly
            actual_channel = f"userEvents@{target}"
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}. Use 'trades', 'ticker', 'depth', or 'userEvents'")
            
        return self.ws.subscribe({"channels": [actual_channel]}, callback, timeout=timeout)

    def unsubscribe(self, channel: str, subscription_id: int, timeout: Optional[int] = None) -> bool:
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
        agent.unsubscribe('trades@KAIA/USDT', sub_id)
        agent.unsubscribe('userEvents@0x123...', sub_id)
        """
        if '@' not in channel:
            raise ValueError(f"Channel format should be 'type@target', got: {channel}")
            
        channel_type, target = channel.split('@', 1)
        
        if channel_type in ['trades', 'ticker', 'depth']:
            # Convert market name to market_id
            market_id = market_to_market_id(target, self.api.symbol_token_id_map)
            actual_channel = f"{channel_type}@{market_id}"
        elif channel_type == 'userEvents':
            # Use address directly
            actual_channel = f"userEvents@{target}"
        else:
            raise ValueError(f"Unsupported channel type: {channel_type}. Use 'trades', 'ticker', 'depth', or 'userEvents'")
            
        return self.ws.unsubscribe({"channels": [actual_channel]}, subscription_id, timeout=timeout)

    # API helpers (commonly used)
    def order(self, market: str, side: int, price: int, quantity: int, order_type: int, order_mode: int, tp_limit: int | None = None, sl_trigger: int | None = None, sl_limit: int | None = None) -> bool:
        return self.api.order(market, side, price, quantity, order_type, order_mode, tp_limit, sl_trigger, sl_limit)

    def cancel(self, order_id: str) -> bool:
        return self.api.cancel(order_id)

    def cancel_all(self) -> bool:
        return self.api.cancel_all()

    def modify(self, order_id: str, new_price: int | None = None, new_qty: int | None = None, order_mode: int | None = None) -> bool:
        return self.api.modify(order_id, new_price, new_qty, order_mode)

    def value_transfer(self, to: str, value: int) -> bool:
        return self.api.value_transfer(to, value)

    def token_transfer(self, to: str, value: int, token: str) -> bool:
        return self.api.token_transfer(to, value, token)

    def withdraw(self, token: str, value: int, token_l1_address: str = None) -> bool:
        return self.api.withdraw_to_kaia(token, value, token_l1_address)

    def deposit(self, token: str, value: int, token_l1_address: str = None) -> bool:
        return self.api.deposit_to_alphasec(token, value, token_l1_address)

    # Market data helpers
    def get_ticker(self, market: str):
        return self.api.get_ticker(market)

    def get_tickers(self):
        return self.api.get_tickers()

    def get_market_list(self):
        return self.api.get_market_list()

    def get_trades(self, market: str, limit: int = 100):
        return self.api.get_trades(market, limit)

    def get_tokens(self):
        return self.api.get_tokens()

    # Order history helpers
    def get_open_orders(self, addr: str, market: str, limit: int = 100, from_msec: int = None, end_msec: int = None):
        return self.api.get_open_orders(addr, market, limit, from_msec, end_msec)

    def get_filled_canceled_orders(self, addr: str, market: str, limit: int = 100, from_msec: int = None, end_msec: int = None):
        return self.api.get_filled_canceled_orders(addr, market, limit, from_msec, end_msec)

    def get_order_by_id(self, order_id: str):
        return self.api.get_order_by_id(order_id)

    # Wallet/session helpers
    def get_balance(self, addr: str):
        return self.api.get_balance(addr)

    def get_sessions(self, addr: str):
        return self.api.get_sessions(addr)

    # Session management
    def create_session(self, session_id: str, session_wallet, expiry: int, nonce: int):
        return self.api.create_session(session_id, session_wallet, expiry, nonce)

    def update_session(self, session_id: str, session_wallet, expiry: int, nonce: int):
        return self.api.update_session(session_id, session_wallet, expiry, nonce)

    def delete_session(self, session_wallet):
        return self.api.delete_session(session_wallet)

    # Additional trading helpers
    def stop_order(self, base_token: str, quote_token: str, stop_price: int, price: int, quantity: int, side: int, order_type: int, order_mode: int):
        return self.api.stop_order(base_token, quote_token, stop_price, price, quantity, side, order_type, order_mode)
