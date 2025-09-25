import os
import time
from alphasec.transaction.utils import load_config
from alphasec.websocket.ws import WebsocketManager


def test_trades_subscription():
    config = load_config(os.path.dirname(__file__) + "/config")

    ws = WebsocketManager(config["api_url"])
    ws.start()

    ws.subscribe(channel="trade@5_2", callback=lambda x: print(x), timeout=5)
    ws.subscribe(channel="depth@5_2", callback=lambda x: print(x), timeout=5)
    ws.subscribe(channel="ticker@5_2", callback=lambda x: print(x), timeout=5)
    ws.subscribe(channel="userEvent@0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", callback=lambda x: print(x), timeout=5)

    time.sleep(20)
    ws.stop()