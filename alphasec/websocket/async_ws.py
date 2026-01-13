"""Async WebSocket Manager for AlphaSec DEX.

Provides asynchronous websocket connection management with subscription handling
using the websockets library and asyncio.
"""
import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, NamedTuple, Optional

import websockets
from eth_utils.address import is_address
from typing_extensions import TypeGuard

from .types import Ack, WsMsg, convert_to_snake_case

logger = logging.getLogger(__name__)

ActiveSubscription = NamedTuple(
    "ActiveSubscription", [("callback", Callable[[Any], None]), ("subscription_id", int)]
)


def channel_to_identifier(channel: str) -> str:
    """Convert a channel name to its identifier format.

    Args:
        channel: The channel name (e.g., "trade@5_2", "depth@ETH_USDC")

    Returns:
        The identifier string (e.g., "trade:5_2", "depth:eth_usdc")

    Raises:
        ValueError: If the channel format is unknown
    """
    if "trade" in channel:
        return f'trade:{channel.split("@")[1].lower()}'
    if "depth" in channel:
        return f'depth:{channel.split("@")[1].lower()}'
    if "ticker" in channel:
        return f'ticker:{channel.split("@")[1].lower()}'
    if "userEvent" in channel:
        return f'userevent:{channel.split("@")[1].lower()}'
    raise ValueError(f"Unknown channel: {channel}")


def ws_msg_to_identifier(ws_msg: WsMsg) -> Optional[str]:
    """Extract identifier from a websocket message.

    Args:
        ws_msg: The websocket message to process

    Returns:
        The identifier string or None if not applicable
    """
    channel = None
    if "method" in ws_msg and ws_msg["method"] == "subscription":
        channel = ws_msg["params"]["channel"]
    else:
        return None

    if "pong" in channel:
        return "pong"

    if "trade" in channel:
        trades = ws_msg["params"]["result"]
        if len(trades) == 0:
            return None
        else:
            return f'trade:{trades[0]["marketId"].lower()}'

    if "depth" in channel:
        depth = ws_msg["params"]["result"]
        if len(depth) == 0:
            return None
        else:
            return f'depth:{depth["marketId"].lower()}'

    if "ticker" in channel:
        ticker = ws_msg["params"]["result"]
        if len(ticker) == 0:
            return None
        else:
            return f'ticker:{ticker[0]["marketId"].lower()}'

    if "userEvent" in channel:
        user_event = ws_msg["params"]["result"]
        user_address = channel.split("@")[1]
        if not is_address(user_address):
            return None
        if len(user_event) == 0:
            return None
        else:
            return f'userevent:{user_address.lower()}'

    logger.error(f"Unknown channel: {channel}")
    return None


class AsyncWebsocketManager:
    """Asynchronous WebSocket manager for AlphaSec DEX subscriptions.

    This class provides async websocket connection management with support for
    subscribing to various channels (trades, depth, ticker, user events) using
    callback-based message handling.

    Attributes:
        ws_url: The websocket URL to connect to
        ws_ready: Whether the websocket connection is established
        subscription_id_counter: Counter for generating subscription IDs
        active_subscriptions: Dictionary mapping identifiers to their callbacks

    Example:
        >>> manager = AsyncWebsocketManager("http://api.example.com")
        >>> await manager.connect()
        >>> run_task = asyncio.create_task(manager.run())
        >>> await manager.subscribe("trade@5_2", lambda x: print(x))
        >>> # ... wait for messages ...
        >>> await manager.stop()
    """

    def __init__(self, base_url: str) -> None:
        """Initialize the AsyncWebsocketManager.

        Args:
            base_url: The base HTTP URL (e.g., "http://api.example.com")
                     Will be converted to websocket URL automatically.
        """
        self.subscription_id_counter: int = 0
        self.ws_ready: bool = False
        self.active_subscriptions: Dict[str, List[ActiveSubscription]] = defaultdict(list)

        # Convert http(s) URL to ws(s) URL
        self.ws_url: str = "ws" + base_url[len("http") :] + "/ws"

        self._ws: Optional[websockets.ClientConnection] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._ping_task: Optional[asyncio.Task] = None
        self._run_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Establish the websocket connection.

        This method connects to the websocket server and sets ws_ready to True
        once the connection is established.

        Raises:
            Exception: If the connection fails
        """
        logger.debug(f"Connecting to websocket at {self.ws_url}")
        self._ws = await websockets.connect(self.ws_url)
        self.ws_ready = True
        logger.debug("Websocket connection established")

    async def run(self) -> None:
        """Run the message loop and ping sender.

        This method starts the ping sender task and continuously receives
        messages from the websocket, dispatching them to registered callbacks.

        Should be run as a task in the background:
            run_task = asyncio.create_task(manager.run())
        """
        if self._ws is None:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        # Start ping sender
        self._ping_task = asyncio.create_task(self._ping_loop())

        try:
            async for message in self._ws:
                if self._stop_event.is_set():
                    break
                # Convert bytes to str if needed
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                self.on_message(message)
        except websockets.ConnectionClosed:
            logger.debug("WebSocket connection closed")
        except asyncio.CancelledError:
            logger.debug("WebSocket run loop cancelled")
        finally:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
                try:
                    await self._ping_task
                except asyncio.CancelledError:
                    pass

    async def _ping_loop(self) -> None:
        """Send periodic ping messages to keep the connection alive."""
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=50)
                    # If we get here, stop_event was set
                    break
                except asyncio.TimeoutError:
                    # Timeout means we should send a ping
                    if self._ws and self.ws_ready:
                        logger.debug("Websocket sending ping")
                        await self.send_ping()
        except asyncio.CancelledError:
            logger.debug("Ping loop cancelled")

    async def send_ping(self) -> None:
        """Send a ping message to the server."""
        if self._ws:
            await self._ws.send(json.dumps({"method": "ping"}))

    async def stop(self) -> None:
        """Stop the websocket manager gracefully.

        This method signals the stop event, cancels the ping task,
        and closes the websocket connection.
        """
        logger.debug("Stopping websocket manager")
        self._stop_event.set()

        # Cancel ping task
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        # Close websocket
        if self._ws:
            await self._ws.close()

        self.ws_ready = False
        logger.debug("Websocket manager stopped")

    def is_ack(self, msg: object) -> TypeGuard[Ack]:
        """Check if a message is an acknowledgment message.

        Args:
            msg: The message to check

        Returns:
            True if the message is an ACK, False otherwise
        """
        return (
            isinstance(msg, dict)
            and msg.get("jsonrpc") == "2.0"
            and isinstance(msg.get("id"), int)
            and isinstance(msg.get("result"), str)
        )

    def on_message(self, message: str) -> None:
        """Handle an incoming websocket message.

        This method parses the message, determines its type, and dispatches
        it to the appropriate callbacks.

        Args:
            message: The raw JSON message string
        """
        ws_msg: WsMsg = json.loads(message)

        if self.is_ack(ws_msg):
            logger.debug("Websocket received acknowledgment")
            return

        identifier = ws_msg_to_identifier(ws_msg)

        if identifier == "pong":
            logger.debug("Websocket received pong")
            return

        if identifier is None:
            logger.debug("Websocket not handling empty message")
            return

        active_subscriptions = self.active_subscriptions.get(identifier, [])

        if len(active_subscriptions) == 0:
            logger.error(f"Websocket message from unexpected subscription: {identifier}")
        else:
            for active_subscription in active_subscriptions:
                converted_msg = convert_to_snake_case(ws_msg)
                active_subscription.callback(converted_msg["params"]["result"])

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], None],
        subscription_id: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> int:
        """Subscribe to a channel with a callback.

        Args:
            channel: The channel to subscribe to (e.g., "trade@5_2")
            callback: The callback function to call when messages arrive
            subscription_id: Optional custom subscription ID
            timeout: Optional timeout in seconds to wait for connection

        Returns:
            The subscription ID

        Raises:
            TimeoutError: If timeout is specified and ws is not ready in time
            NotImplementedError: If trying to subscribe to userEvent multiple times
        """
        start_time = asyncio.get_running_loop().time()

        while not self.ws_ready:
            logger.debug("Websocket is not ready yet, waiting")
            if timeout is not None:
                elapsed = asyncio.get_running_loop().time() - start_time
                if elapsed > timeout:
                    raise TimeoutError("Websocket is not ready after timeout")
            await asyncio.sleep(0.1)

        if subscription_id is None:
            self.subscription_id_counter += 1
            subscription_id = self.subscription_id_counter

        logger.debug(f"Subscribing to {channel} with id {subscription_id}")
        identifier = channel_to_identifier(channel)

        if "userevent" in identifier:
            if len(self.active_subscriptions[identifier]) != 0:
                raise NotImplementedError(f"Cannot subscribe to {identifier} multiple times")

        self.active_subscriptions[identifier].append(
            ActiveSubscription(callback, subscription_id)
        )

        if self._ws:
            await self._ws.send(
                json.dumps(
                    {
                        "method": "subscribe",
                        "params": {"channels": [channel]},
                        "id": subscription_id,
                    }
                )
            )

        return subscription_id

    async def unsubscribe(
        self, channel: str, subscription_id: int, timeout: Optional[float] = None
    ) -> bool:
        """Unsubscribe from a channel.

        Args:
            channel: The channel to unsubscribe from
            subscription_id: The subscription ID to remove
            timeout: Optional timeout in seconds to wait for connection

        Returns:
            True if the subscription was found and removed, False otherwise

        Raises:
            TimeoutError: If timeout is specified and ws is not ready in time
        """
        start_time = asyncio.get_running_loop().time()

        while not self.ws_ready:
            logger.debug("Websocket is not ready yet, waiting")
            if timeout is not None:
                elapsed = asyncio.get_running_loop().time() - start_time
                if elapsed > timeout:
                    raise TimeoutError("Websocket is not ready after timeout")
            await asyncio.sleep(0.1)

        identifier = channel_to_identifier(channel)
        active_subscriptions = self.active_subscriptions[identifier]

        new_active_subscriptions = [
            x for x in active_subscriptions if x.subscription_id != subscription_id
        ]

        # If removing the last subscriber, send unsubscribe message
        if len(new_active_subscriptions) == 0 and len(active_subscriptions) > 0:
            if self._ws:
                await self._ws.send(
                    json.dumps(
                        {
                            "method": "unsubscribe",
                            "params": {"channels": [channel]},
                            "id": subscription_id,
                        }
                    )
                )

        self.active_subscriptions[identifier] = new_active_subscriptions
        return len(active_subscriptions) != len(new_active_subscriptions)
