import os
import time
from alphasec.transaction.utils import load_config
from alphasec.websocket.types import TradesSubscription
from alphasec.websocket.ws import WebsocketManager


def test_trades_subscription():
    config = load_config(os.path.dirname(__file__))

    ws = WebsocketManager(config["api_url"])
    ws.start()

    ws.subscribe(TradesSubscription(channels=["trades@5_2"]), lambda x: print(x), timeout=5)
    ws.subscribe(TradesSubscription(channels=["depth@5_2"]), lambda x: print(x), timeout=5)
    ws.subscribe(TradesSubscription(channels=["ticker@5_2"]), lambda x: print(x), timeout=5)
    ws.subscribe(TradesSubscription(channels=["userEvents@0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c"]), lambda x: print(x), timeout=5)

    time.sleep(20)
    ws.stop()