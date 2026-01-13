"""Async WebSocket Manager Tests.

Tests for AsyncWebsocketManager using pytest-asyncio.
Uses mock websocket server for unit testing.
"""
import asyncio
import json
import os
from collections import defaultdict
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from alphasec.transaction.utils import load_config
from alphasec.websocket.async_ws import AsyncWebsocketManager


class MockWebSocket:
    """Mock websocket for testing without real server connection."""

    def __init__(self):
        self.sent_messages: List[str] = []
        self.closed = False
        self._recv_queue: asyncio.Queue = asyncio.Queue()
        self._close_event = asyncio.Event()

    async def send(self, message: str) -> None:
        if self.closed:
            raise Exception("WebSocket is closed")
        self.sent_messages.append(message)

    async def recv(self) -> str:
        try:
            # Use wait_for with the close event to allow interruption
            while not self._close_event.is_set():
                try:
                    return await asyncio.wait_for(self._recv_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
            raise Exception("WebSocket closed")
        except asyncio.CancelledError:
            raise

    async def close(self) -> None:
        self.closed = True
        self._close_event.set()

    async def add_message(self, message: Dict[str, Any]) -> None:
        """Add a message to be received by the websocket."""
        await self._recv_queue.put(json.dumps(message))

    @property
    def open(self) -> bool:
        return not self.closed


@pytest.fixture
def mock_ws():
    """Create a mock websocket instance."""
    return MockWebSocket()


@pytest_asyncio.fixture
async def async_ws_manager():
    """Create an AsyncWebsocketManager instance for testing."""
    manager = AsyncWebsocketManager("http://localhost:8080")
    yield manager
    if manager.ws_ready:
        await manager.stop()


class TestAsyncWebsocketManagerInit:
    """Tests for AsyncWebsocketManager initialization."""

    def test_init_creates_correct_ws_url(self):
        """Test that ws_url is correctly derived from base_url."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        assert manager.ws_url == "ws://localhost:8080/ws"

    def test_init_with_https_creates_wss_url(self):
        """Test that https base_url creates wss ws_url."""
        manager = AsyncWebsocketManager("https://api.example.com")
        assert manager.ws_url == "wss://api.example.com/ws"

    def test_init_sets_default_state(self):
        """Test that initial state is correctly set."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        assert manager.ws_ready is False
        assert manager.subscription_id_counter == 0
        assert len(manager.active_subscriptions) == 0


class TestAsyncWebsocketManagerConnection:
    """Tests for connection handling."""

    @pytest.mark.asyncio
    async def test_connect_sets_ws_ready(self, mock_ws):
        """Test that connect sets ws_ready to True."""
        manager = AsyncWebsocketManager("http://localhost:8080")

        with patch("websockets.connect", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_ws))):
            # We need to use a context manager mock
            async def mock_connect(*args, **kwargs):
                return mock_ws

            with patch("websockets.connect", mock_connect):
                await manager.connect()
                assert manager.ws_ready is True

    @pytest.mark.asyncio
    async def test_stop_closes_connection(self, mock_ws):
        """Test that stop gracefully closes the connection."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        await manager.stop()

        assert mock_ws.closed is True
        assert manager.ws_ready is False


class TestAsyncWebsocketManagerSubscription:
    """Tests for subscription handling."""

    @pytest.mark.asyncio
    async def test_subscribe_sends_correct_message(self, mock_ws):
        """Test that subscribe sends the correct JSON message."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        callback = MagicMock()
        subscription_id = await manager.subscribe("trade@5_2", callback)

        assert subscription_id == 1
        assert len(mock_ws.sent_messages) == 1

        sent_msg = json.loads(mock_ws.sent_messages[0])
        assert sent_msg["method"] == "subscribe"
        assert sent_msg["params"]["channels"] == ["trade@5_2"]
        assert sent_msg["id"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_increments_subscription_id(self, mock_ws):
        """Test that subscription_id increments with each subscription."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        callback = MagicMock()
        id1 = await manager.subscribe("trade@5_2", callback)
        id2 = await manager.subscribe("depth@5_2", callback)
        id3 = await manager.subscribe("ticker@5_2", callback)

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    @pytest.mark.asyncio
    async def test_subscribe_stores_active_subscription(self, mock_ws):
        """Test that subscribe stores the callback in active_subscriptions."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        callback = MagicMock()
        await manager.subscribe("trade@5_2", callback)

        identifier = "trade:5_2"
        assert identifier in manager.active_subscriptions
        assert len(manager.active_subscriptions[identifier]) == 1
        assert manager.active_subscriptions[identifier][0].callback == callback

    @pytest.mark.asyncio
    async def test_subscribe_waits_for_ws_ready(self, mock_ws):
        """Test that subscribe waits until ws_ready is True."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = False
        manager._stop_event = asyncio.Event()

        callback = MagicMock()

        # Set ws_ready after a short delay
        async def set_ready():
            await asyncio.sleep(0.1)
            manager.ws_ready = True

        asyncio.create_task(set_ready())

        subscription_id = await manager.subscribe("trade@5_2", callback, timeout=1.0)
        assert subscription_id == 1

    @pytest.mark.asyncio
    async def test_subscribe_timeout_raises_error(self, mock_ws):
        """Test that subscribe raises TimeoutError when ws not ready."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = False
        manager._stop_event = asyncio.Event()

        callback = MagicMock()

        with pytest.raises(TimeoutError):
            await manager.subscribe("trade@5_2", callback, timeout=0.1)


class TestAsyncWebsocketManagerUnsubscribe:
    """Tests for unsubscription handling."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self, mock_ws):
        """Test that unsubscribe removes the subscription from active_subscriptions."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        callback = MagicMock()
        subscription_id = await manager.subscribe("trade@5_2", callback)

        result = await manager.unsubscribe("trade@5_2", subscription_id)

        assert result is True
        identifier = "trade:5_2"
        assert len(manager.active_subscriptions[identifier]) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_sends_message_when_last_subscriber(self, mock_ws):
        """Test that unsubscribe sends unsubscribe message when removing last subscriber."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        callback = MagicMock()
        subscription_id = await manager.subscribe("trade@5_2", callback)
        mock_ws.sent_messages.clear()  # Clear the subscribe message

        await manager.unsubscribe("trade@5_2", subscription_id)

        assert len(mock_ws.sent_messages) == 1
        sent_msg = json.loads(mock_ws.sent_messages[0])
        assert sent_msg["method"] == "unsubscribe"
        assert sent_msg["params"]["channels"] == ["trade@5_2"]

    @pytest.mark.asyncio
    async def test_unsubscribe_does_not_send_message_when_other_subscribers(self, mock_ws):
        """Test that unsubscribe does not send message when other subscribers remain."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        callback1 = MagicMock()
        callback2 = MagicMock()
        id1 = await manager.subscribe("trade@5_2", callback1)
        await manager.subscribe("trade@5_2", callback2)
        mock_ws.sent_messages.clear()

        await manager.unsubscribe("trade@5_2", id1)

        # No unsubscribe message should be sent
        assert len(mock_ws.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_returns_false_for_unknown_id(self, mock_ws):
        """Test that unsubscribe returns False for unknown subscription_id."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        result = await manager.unsubscribe("trade@5_2", 999)
        assert result is False


class TestAsyncWebsocketManagerMessageHandling:
    """Tests for message handling."""

    @pytest.mark.asyncio
    async def test_on_message_calls_callback_for_trade(self, mock_ws):
        """Test that on_message calls the registered callback for trade messages."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        received_data = []
        callback = lambda x: received_data.append(x)
        await manager.subscribe("trade@5_2", callback)

        trade_msg = {
            "jsonrpc": "2.0",
            "method": "subscription",
            "params": {
                "channel": "trade@5_2",
                "result": [
                    {
                        "hash": "0x123",
                        "marketId": "5_2",
                        "side": 0,
                        "px": "100.00",
                        "sz": 10,
                        "tid": "trade1",
                        "time": 1234567890,
                        "users": ["0x123", "0x456"],
                    }
                ],
            },
        }

        manager.on_message(json.dumps(trade_msg))

        assert len(received_data) == 1
        # Check snake_case conversion
        assert "market_id" in received_data[0][0]

    @pytest.mark.asyncio
    async def test_on_message_handles_ack(self, mock_ws):
        """Test that on_message handles ACK messages without error."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        ack_msg = {"jsonrpc": "2.0", "id": 1, "result": "success"}

        # Should not raise
        manager.on_message(json.dumps(ack_msg))

    @pytest.mark.asyncio
    async def test_on_message_handles_pong(self, mock_ws):
        """Test that on_message handles pong messages without error."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True
        manager._stop_event = asyncio.Event()

        pong_msg = {
            "jsonrpc": "2.0",
            "method": "subscription",
            "params": {"channel": "pong", "result": {}},
        }

        # Should not raise
        manager.on_message(json.dumps(pong_msg))


class TestAsyncWebsocketManagerPing:
    """Tests for ping functionality."""

    @pytest.mark.asyncio
    async def test_send_ping_sends_ping_message(self, mock_ws):
        """Test that send_ping sends a ping message."""
        manager = AsyncWebsocketManager("http://localhost:8080")
        manager._ws = mock_ws
        manager.ws_ready = True

        await manager.send_ping()

        assert len(mock_ws.sent_messages) == 1
        sent_msg = json.loads(mock_ws.sent_messages[0])
        assert sent_msg["method"] == "ping"


class TestAsyncWebsocketManagerChannelIdentifiers:
    """Tests for channel to identifier conversion."""

    def test_channel_to_identifier_trade(self):
        """Test trade channel identifier conversion."""
        from alphasec.websocket.async_ws import channel_to_identifier

        assert channel_to_identifier("trade@5_2") == "trade:5_2"
        assert channel_to_identifier("trade@ETH_USDC") == "trade:eth_usdc"

    def test_channel_to_identifier_depth(self):
        """Test depth channel identifier conversion."""
        from alphasec.websocket.async_ws import channel_to_identifier

        assert channel_to_identifier("depth@5_2") == "depth:5_2"

    def test_channel_to_identifier_ticker(self):
        """Test ticker channel identifier conversion."""
        from alphasec.websocket.async_ws import channel_to_identifier

        assert channel_to_identifier("ticker@5_2") == "ticker:5_2"

    def test_channel_to_identifier_user_event(self):
        """Test userEvent channel identifier conversion."""
        from alphasec.websocket.async_ws import channel_to_identifier

        assert (
            channel_to_identifier("userEvent@0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
            == "userevent:0x70dbb395af2edcc2833d803c03abbe56ece7c25c"
        )

    def test_channel_to_identifier_unknown_raises(self):
        """Test that unknown channel raises ValueError."""
        from alphasec.websocket.async_ws import channel_to_identifier

        with pytest.raises(ValueError):
            channel_to_identifier("unknown@channel")


# Integration test - requires real server
@pytest.mark.skip(reason="Integration test - requires real server")
class TestAsyncWebsocketManagerIntegration:
    """Integration tests with real server."""

    @pytest.mark.asyncio
    async def test_full_subscription_flow(self):
        """Test full subscription flow with real server."""
        config = load_config(os.path.dirname(__file__) + "/config")

        manager = AsyncWebsocketManager(config["api_url"])

        received_messages = []

        async def run_test():
            await manager.connect()

            # Start the message loop in background
            run_task = asyncio.create_task(manager.run())

            try:
                await manager.subscribe(
                    channel="trade@5_2",
                    callback=lambda x: received_messages.append(x),
                    timeout=5,
                )
                await manager.subscribe(
                    channel="depth@5_2",
                    callback=lambda x: received_messages.append(x),
                    timeout=5,
                )
                await manager.subscribe(
                    channel="ticker@5_2",
                    callback=lambda x: received_messages.append(x),
                    timeout=5,
                )
                await manager.subscribe(
                    channel="userEvent@0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c",
                    callback=lambda x: received_messages.append(x),
                    timeout=5,
                )

                # Wait for some messages
                await asyncio.sleep(20)
            finally:
                await manager.stop()
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass

        await run_test()
        print(f"Received {len(received_messages)} messages")
