"""Async WebSocket Manager for AlphaSec DEX.

Provides asynchronous websocket connection management with subscription handling
using the websockets library and asyncio.
"""
import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

from eth_utils.address import is_address
from typing_extensions import TypeGuard
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from .types import Ack, WsMsg, convert_to_snake_case

logger = logging.getLogger(__name__)

# Reconnection backoff parameters (aligned with the Rust SDK manager):
# infinite retries, exponential backoff starting at 1s, capped at 30s.
RECONNECT_INITIAL_DELAY_SECS = 1.0
RECONNECT_MAX_DELAY_SECS = 30.0

ActiveSubscription = NamedTuple(
    "ActiveSubscription",
    [
        ("callback", Callable[[Any], Any]),
        ("subscription_id", int),
        ("channel", str),
    ],
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

    The message loop reconnects automatically when the connection drops
    (exponential backoff, infinite retries) and restores all registered
    subscriptions on reconnect. The loop only terminates via stop().

    Callbacks may be sync or async. Sync callbacks are invoked directly on
    the event loop and must be non-blocking. Async callbacks are scheduled
    as tasks; their exceptions are logged and pending tasks are cancelled
    on stop().

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

        self._ws: Optional[ClientConnection] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._ping_task: Optional[asyncio.Task] = None
        self._run_task: Optional[asyncio.Task] = None
        self._callback_tasks: Set[asyncio.Task] = set()

    async def connect(self) -> None:
        """Establish the websocket connection.

        This method connects to the websocket server and sets ws_ready to True
        once the connection is established.

        Raises:
            Exception: If the connection fails
        """
        # Recreate the stop event so the manager can be restarted after a
        # previous stop() (an asyncio.Event stays set once triggered).
        self._stop_event = asyncio.Event()
        logger.debug(f"Connecting to websocket at {self.ws_url}")
        self._ws = await connect(self.ws_url)
        self.ws_ready = True
        logger.debug("Websocket connection established")

    async def run(self) -> None:
        """Run the message loop with automatic reconnection.

        This method starts the ping sender task and continuously receives
        messages from the websocket, dispatching them to registered callbacks.

        When the connection drops, it reconnects automatically with
        exponential backoff (1s initial, doubled per failure, capped at 30s,
        retrying forever) and restores all registered subscriptions. The
        loop only terminates when stop() is called.

        Should be run as a task in the background:
            run_task = asyncio.create_task(manager.run())
        """
        if self._ws is None:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        while not self._stop_event.is_set():
            # The ping task is managed per connection: started after each
            # (re)connect and cleaned up when the connection ends.
            self._ping_task = asyncio.create_task(self._ping_loop())
            try:
                async for message in self._ws:
                    if self._stop_event.is_set():
                        break
                    # Convert bytes to str if needed
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    self.on_message(message)
                # A clean server-side close exits the loop without raising;
                # treat it as a disconnect unless stop() was requested.
            except ConnectionClosed:
                pass
            finally:
                await self._cleanup_ping_task()

            if self._stop_event.is_set():
                break

            self.ws_ready = False
            logger.warning("WebSocket disconnected, reconnecting...")
            if not await self._reconnect():
                break

    async def _reconnect(self) -> bool:
        """Reconnect with exponential backoff and restore subscriptions.

        Retries forever until the connection is re-established or stop() is
        called. The backoff wait is interruptible by stop().

        Returns:
            True if reconnected, False if stop() was requested first.
        """
        delay = RECONNECT_INITIAL_DELAY_SECS
        while not self._stop_event.is_set():
            try:
                self._ws = await connect(self.ws_url)
                restored = await self._restore_subscriptions()
            except Exception as exc:
                logger.warning(
                    f"WebSocket reconnect failed ({exc!r}), retrying in {delay:.0f}s"
                )
                try:
                    # Backoff wait that stop() can interrupt immediately.
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                    return False  # stop() requested during backoff
                except asyncio.TimeoutError:
                    delay = min(delay * 2, RECONNECT_MAX_DELAY_SECS)
                continue

            # stop() may have completed while connect/restore were in
            # flight: it only closed the old socket and left ws_ready
            # False. Close the fresh socket here instead of leaking it
            # and re-marking the manager ready after shutdown.
            if self._stop_event.is_set():
                await self._ws.close()
                return False

            self.ws_ready = True
            logger.warning(f"WebSocket reconnected, {restored} subscriptions restored")
            return True
        return False

    async def _restore_subscriptions(self) -> int:
        """Resend subscribe frames for all registered subscriptions.

        Iterating without a copy is safe: subscribe()/unsubscribe() are
        parked on ws_ready (False during reconnection), so
        active_subscriptions cannot change while this method awaits.

        Returns:
            The number of subscriptions restored.
        """
        count = 0
        for subscriptions in self.active_subscriptions.values():
            for subscription in subscriptions:
                await self._ws.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "params": {"channels": [subscription.channel]},
                            "id": subscription.subscription_id,
                        }
                    )
                )
                count += 1
        return count

    async def _cleanup_ping_task(self) -> None:
        """Cancel the per-connection ping task and retrieve its exception."""
        task = self._ping_task
        if task is None:
            return
        self._ping_task = None
        if task.done():
            if not task.cancelled() and task.exception() is not None:
                logger.error(f"Ping task failed: {task.exception()!r}")
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Ping task failed: {exc!r}")

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

        This method signals the stop event, cancels the ping task and any
        pending async callback tasks, and closes the websocket connection.
        """
        logger.debug("Stopping websocket manager")
        self._stop_event.set()

        # Cancel ping task
        await self._cleanup_ping_task()

        # Cancel pending async callback tasks
        pending_callbacks = [t for t in self._callback_tasks if not t.done()]
        for task in pending_callbacks:
            task.cancel()
        if pending_callbacks:
            await asyncio.gather(*pending_callbacks, return_exceptions=True)

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
        it to the appropriate callbacks. Parsing/conversion failures are
        logged and the message is skipped; callback failures are isolated
        per subscriber so one faulty callback cannot stop the receive loop.

        This method is intentionally synchronous (no await points), so the
        iteration over active_subscriptions stays lock-free safe on the
        single event loop.

        Args:
            message: The raw JSON message string
        """
        try:
            ws_msg: WsMsg = json.loads(message)

            if self.is_ack(ws_msg):
                logger.debug("Websocket received acknowledgment")
                return

            identifier = ws_msg_to_identifier(ws_msg)
        except Exception:
            logger.error(f"Failed to parse websocket message: {message!r}", exc_info=True)
            return

        if identifier == "pong":
            logger.debug("Websocket received pong")
            return

        if identifier is None:
            logger.debug("Websocket not handling empty message")
            return

        active_subscriptions = self.active_subscriptions.get(identifier, [])

        if len(active_subscriptions) == 0:
            logger.error(f"Websocket message from unexpected subscription: {identifier}")
            return

        for active_subscription in active_subscriptions:
            try:
                # Converted per subscriber so each callback gets its own copy.
                converted_msg = convert_to_snake_case(ws_msg)
                payload = converted_msg["params"]["result"]
            except Exception:
                # Conversion failure is message-level: skip this message.
                logger.error(
                    f"Failed to convert websocket message: {message!r}", exc_info=True
                )
                return
            self._dispatch_callback(active_subscription.callback, payload)

    def _dispatch_callback(self, callback: Callable[[Any], Any], payload: Any) -> None:
        """Invoke a single subscription callback with exception isolation.

        Sync callbacks are called directly and must be non-blocking (they
        run on the event loop). Async callbacks are scheduled as tasks
        tracked in _callback_tasks; their exceptions are retrieved and
        logged when the task completes. CancelledError is deliberately not
        caught so cancellation propagates.
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                task = asyncio.create_task(callback(payload))
                self._callback_tasks.add(task)
                task.add_done_callback(self._on_callback_task_done)
            else:
                callback(payload)
        except Exception:
            logger.error("Websocket subscription callback raised", exc_info=True)

    def _on_callback_task_done(self, task: "asyncio.Task") -> None:
        """Reap a finished async callback task and log its exception."""
        self._callback_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(f"Websocket async callback task failed: {exc!r}")

    def _check_userevent_guard(self, identifier: str) -> None:
        """Reject a second userEvent subscription for the same address."""
        if identifier.startswith("userevent:") and self.active_subscriptions.get(identifier):
            raise ValueError(
                f"Already subscribed to {identifier}; "
                f"only one userEvent subscription per address is allowed"
            )

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], Any],
        subscription_id: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> int:
        """Subscribe to a channel with a callback.

        The callback may be sync or async. Sync callbacks are invoked
        directly on the event loop and must be non-blocking. Async callbacks
        (``async def``) are executed as tasks; exceptions they raise are
        logged, and pending tasks are cancelled on stop().

        Args:
            channel: The channel to subscribe to (e.g., "trade@5_2")
            callback: The sync or async callback to call when messages arrive
            subscription_id: Optional custom subscription ID
            timeout: Optional timeout in seconds to wait for connection

        Returns:
            The subscription ID

        Raises:
            TimeoutError: If timeout is specified and ws is not ready in time
            ValueError: If a userEvent subscription already exists for the address
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

        self._check_userevent_guard(identifier)

        # Send the subscribe frame first; register locally only after the
        # send succeeds so a failed send does not leave a phantom
        # subscription in active_subscriptions.
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

        # Re-check after the await: a concurrent subscribe() may have
        # registered the same userEvent identifier while we were sending.
        self._check_userevent_guard(identifier)

        self.active_subscriptions[identifier].append(
            ActiveSubscription(callback, subscription_id, channel)
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
