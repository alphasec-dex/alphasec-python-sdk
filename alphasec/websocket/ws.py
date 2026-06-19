from ast import List
import json
import logging
import threading
from collections import defaultdict
import time

from eth_utils.address import is_address
import websocket

from typing import Any, Callable, Dict, NamedTuple, Optional
from typing_extensions import TypeGuard

from .types import Ack, WsMsg, convert_to_snake_case

RECONNECT_INITIAL_DELAY_SECS = 1.0
RECONNECT_MAX_DELAY_SECS = 30.0

ActiveSubscription = NamedTuple(
    "ActiveSubscription",
    [("callback", Callable[[Any], None]), ("subscription_id", int), ("channel", str)],
)

# Perp channel prefix -> identifier stream tag. Perp channels must be matched
# before the generic spot substring checks below, since e.g. "perp_ticker"
# contains the substring "ticker". The identifier is built from the channel
# string alone (not the payload), so channel_to_identifier and
# ws_msg_to_identifier always agree.
_PERP_CHANNEL_PREFIXES = (
    ("perp_ticker", "perp_ticker"),
    ("perp_markPrice", "perp_markPrice"),
    ("perp_aggTrade", "perp_aggTrade"),
    ("perp_aggDepth", "perp_aggDepth"),
    ("perp_candle", "perp_candle"),
)

def _perp_channel_to_identifier(channel: str) -> Optional[str]:
    """Return the routing identifier for a perp market-data channel, else None.

    The suffix after the prefix (e.g. "@1", "@1:1D") keys the identifier so each
    marketId/resolution routes independently. userEvent is intentionally not
    handled here: it is a shared spot/perp channel routed by the existing
    userEvent branch.
    """
    for prefix, tag in _PERP_CHANNEL_PREFIXES:
        if channel.startswith(prefix):
            suffix = channel[len(prefix):].lower()
            return f'{tag}:{suffix}'
    return None

def channel_to_identifier(channel: str) -> str:
    perp_identifier = _perp_channel_to_identifier(channel)
    if perp_identifier is not None:
        return perp_identifier
    if "trade" in channel:
        return f'trade:{channel.split("@")[1].lower()}'
    if "depth" in channel:
        return f'depth:{channel.split("@")[1].lower()}'
    if "ticker" in channel:
        return f'ticker:{channel.split("@")[1].lower()}'
    if "userEvent" in channel:
        return f'userEvent:{channel.split("@")[1].lower()}'
    raise ValueError(f"Unknown channel: {channel}")

def ws_msg_to_identifier(ws_msg: WsMsg) -> Optional[str]:
    channel = None
    if "method" in ws_msg and ws_msg["method"] == "subscription":
        channel = ws_msg["params"]["channel"]
    else:
        return None

    if "pong" in channel:
        return "pong"

    # Perp channels are routed by channel string alone (see
    # _perp_channel_to_identifier), matched before the generic spot substring
    # checks so "perp_ticker" is not mistaken for a spot ticker.
    perp_identifier = _perp_channel_to_identifier(channel)
    if perp_identifier is not None:
        return perp_identifier

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
            return None # or should we raise an error?
        if len(user_event) == 0:
            return None
        else:
            return f'userEvent:{user_address.lower()}'

    logging.error(f"Unknown channel: {channel}")
    return None

class WebsocketManager(threading.Thread):
    def __init__(self, base_url):
        super().__init__()
        self.subscription_id_counter = 0
        self.ws_ready = False
        self.active_subscriptions: Dict[str, List[ActiveSubscription]] = defaultdict(list)
        self.ws_url = "ws" + base_url[len("http") :] + "/ws"
        self.ws = self._build_app()
        self.ping_sender = threading.Thread(target=self.send_ping, daemon=True)
        self.stop_event = threading.Event()
        self._reconnect_delay = RECONNECT_INITIAL_DELAY_SECS

    def _build_app(self):
        return websocket.WebSocketApp(
            self.ws_url, on_message=self.on_message, on_open=self.on_open,
            on_close=self.on_close, on_error=self.on_error)

    def run(self):
        # Reconnect loop: run_forever() returns on disconnect; back off (interruptible
        # by stop()), rebuild the app, and let on_open restore subscriptions. Mirrors
        # AsyncWebsocketManager. ws_ready=False during the gap parks subscribe/unsubscribe.
        self.ping_sender.start()
        self._reconnect_delay = RECONNECT_INITIAL_DELAY_SECS
        while not self.stop_event.is_set():
            self.ws.run_forever()
            if self.stop_event.is_set():
                break
            self.ws_ready = False
            logging.warning("Websocket disconnected, reconnecting...")
            if self.stop_event.wait(self._reconnect_delay):   # interruptible backoff
                break
            self._reconnect_delay = min(self._reconnect_delay * 2, RECONNECT_MAX_DELAY_SECS)
            self.ws = self._build_app()
        logging.debug("Websocket run loop stopped")

    def send_ping(self):
        # Survives reconnects: sends on the current self.ws; tolerate transient
        # send failures while a socket is mid-reconnect.
        while not self.stop_event.wait(50):
            try:
                self.ws.send(json.dumps({"method": "ping"}))
            except Exception:
                pass
        logging.debug("Websocket ping sender stopped")

    def stop(self):
        self.stop_event.set()
        self.ws.close()
        if self.ping_sender.is_alive():
            self.ping_sender.join()

    def is_ack(self, msg: object) -> TypeGuard[Ack]:
        return (
            isinstance(msg, dict)
            and msg.get("jsonrpc") == "2.0"
            and isinstance(msg.get("id"), int)
            and isinstance(msg.get("result"), str)
        )

    def on_message(self, _ws, message):
        ws_msg: WsMsg = json.loads(message)
        if self.is_ack(ws_msg):
            logging.debug("Websocket was established")
            return
        identifier = ws_msg_to_identifier(ws_msg)
        if identifier == "pong":
            logging.debug("Websocket received pong")
            logging.debug("Websocket message:", message)
            return
        if identifier is None:
            logging.debug("Websocket not handling empty message")
            return

        active_subscriptions = self.active_subscriptions[identifier]
        if len(active_subscriptions) == 0:
            logging.error("Websocket message from an unexpected subscription:", message, identifier)
        else:
            for active_subscription in active_subscriptions:
                ws_msg = convert_to_snake_case(ws_msg)
                active_subscription.callback(ws_msg['params']['result'])

    def on_open(self, _ws):
        logging.debug("on_open")
        self.ws_ready = True
        self._reconnect_delay = RECONNECT_INITIAL_DELAY_SECS   # reset backoff on success
        self._restore_subscriptions()

    def on_close(self, _ws, *args):
        self.ws_ready = False

    def on_error(self, _ws, error):
        logging.warning(f"Websocket error: {error!r}")
        self.ws_ready = False

    def _restore_subscriptions(self):
        # Resend subscribe frames for every registered subscription on (re)connect.
        # Safe to iterate: callers are parked on ws_ready while reconnecting.
        for subs in list(self.active_subscriptions.values()):
            for sub in subs:
                self.ws.send(json.dumps(
                    {"method": "subscribe", "params": {"channels": [sub.channel]}, "id": sub.subscription_id}))

    def subscribe(
        self, channel: str, callback: Callable[[Any], None], subscription_id: Optional[int] = None, timeout: Optional[int] = None
    ) -> int:
        start_time = time.time()
        while not self.ws_ready:
            if self.stop_event.is_set():
                raise RuntimeError("Websocket manager is stopped")
            logging.debug("websocket is not ready yet, waiting")
            if timeout is not None and time.time() - start_time > timeout:
                raise TimeoutError("Websocket is not ready after timeout")
            self.stop_event.wait(0.1)
                
        if subscription_id is None:
            self.subscription_id_counter += 1
            subscription_id = self.subscription_id_counter

        logging.debug("subscribing")
        identifier = channel_to_identifier(channel)
        if identifier.startswith("userEvent:"):
            if len(self.active_subscriptions[identifier]) != 0:
                raise ValueError(f"Already subscribed to {identifier}; only one userEvent subscription per address is allowed")
        self.active_subscriptions[identifier].append(ActiveSubscription(callback, subscription_id, channel))
        self.ws.send(json.dumps({"method": "subscribe", "params": {"channels": [channel]}, "id": subscription_id}))
        return subscription_id

    def unsubscribe(self, channel: str, subscription_id: int, timeout: Optional[int] = None) -> bool:
        start_time = time.time()
        while not self.ws_ready:
            if self.stop_event.is_set():
                raise RuntimeError("Websocket manager is stopped")
            logging.debug("websocket is not ready yet, waiting")
            if timeout is not None and time.time() - start_time > timeout:
                raise TimeoutError("Websocket is not ready after timeout")
            self.stop_event.wait(0.1)

        if not self.ws_ready:
            raise NotImplementedError("Can't unsubscribe before websocket connected")
        identifier = channel_to_identifier(channel)
        active_subscriptions = self.active_subscriptions[identifier]
        new_active_subscriptions = [x for x in active_subscriptions if x.subscription_id != subscription_id]
        if len(new_active_subscriptions) == 0:
            self.ws.send(json.dumps({"method": "unsubscribe", "params": {"channels": [channel]}, "id": subscription_id}))
        self.active_subscriptions[identifier] = new_active_subscriptions
        return len(active_subscriptions) != len(new_active_subscriptions)