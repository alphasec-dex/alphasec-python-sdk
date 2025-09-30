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

ActiveSubscription = NamedTuple("ActiveSubscription", [("callback", Callable[[Any], None]), ("subscription_id", int)])

def channel_to_identifier(channel: str) -> str:
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
        ws_url = "ws" + base_url[len("http") :] + "/ws"
        self.ws = websocket.WebSocketApp(ws_url, on_message=self.on_message, on_open=self.on_open)
        self.ping_sender = threading.Thread(target=self.send_ping)
        self.stop_event = threading.Event()

    def run(self):
        self.ping_sender.start()
        self.ws.run_forever()

    def send_ping(self):
        while not self.stop_event.wait(50):
            if not self.ws.keep_running:
                break
            logging.debug("Websocket sending ping")
            self.ws.send(json.dumps({"method": "ping"}))
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

    def subscribe(
        self, channel: str, callback: Callable[[Any], None], subscription_id: Optional[int] = None, timeout: Optional[int] = None
    ) -> int:
        start_time = time.time()
        while not self.ws_ready:
            logging.debug("websocket is not ready yet, waiting")
            if timeout is not None and time.time() - start_time > timeout:
                raise TimeoutError("Websocket is not ready after timeout")
            time.sleep(0.1)
                
        if subscription_id is None:
            self.subscription_id_counter += 1
            subscription_id = self.subscription_id_counter

        logging.debug("subscribing")
        identifier = channel_to_identifier(channel)
        if identifier == "userEvent":
            if len(self.active_subscriptions[identifier]) != 0:
                raise NotImplementedError(f"Cannot subscribe to {identifier} multiple times")
        self.active_subscriptions[identifier].append(ActiveSubscription(callback, subscription_id))
        self.ws.send(json.dumps({"method": "subscribe", "params": {"channels": [channel]}, "id": subscription_id}))
        return subscription_id

    def unsubscribe(self, channel: str, subscription_id: int, timeout: Optional[int] = None) -> bool:
        start_time = time.time()
        while not self.ws_ready:
            logging.debug("websocket is not ready yet, waiting")
            if timeout is not None and time.time() - start_time > timeout:
                raise TimeoutError("Websocket is not ready after timeout")
            time.sleep(0.1)

        if not self.ws_ready:
            raise NotImplementedError("Can't unsubscribe before websocket connected")
        identifier = channel_to_identifier(channel)
        active_subscriptions = self.active_subscriptions[identifier]
        new_active_subscriptions = [x for x in active_subscriptions if x.subscription_id != subscription_id]
        if len(new_active_subscriptions) == 0:
            self.ws.send(json.dumps({"method": "unsubscribe", "params": {"channels": [channel]}, "id": subscription_id}))
        self.active_subscriptions[identifier] = new_active_subscriptions
        return len(active_subscriptions) != len(new_active_subscriptions)