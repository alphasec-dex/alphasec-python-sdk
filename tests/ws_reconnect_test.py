import json
import types

from alphasec.websocket.ws import WebsocketManager, ActiveSubscription


def _mgr():
    m = WebsocketManager("http://example.invalid")   # construction is offline (not connected until run_forever)
    return m


def test_restore_subscriptions_resends_all_channels():
    m = _mgr()
    sent = []
    m.ws = types.SimpleNamespace(send=lambda f: sent.append(json.loads(f)))
    m.active_subscriptions["perp_ticker@1"] = [ActiveSubscription(lambda p: None, 7, "perp_ticker@1")]
    m.active_subscriptions["depth@2"] = [ActiveSubscription(lambda p: None, 9, "depth@2")]
    m._restore_subscriptions()
    chans = sorted(f["params"]["channels"][0] for f in sent)
    assert chans == ["depth@2", "perp_ticker@1"]
    assert all(f["method"] == "subscribe" for f in sent)


def test_on_close_resets_ws_ready():
    m = _mgr()
    m.ws_ready = True
    m.on_close(None)
    assert m.ws_ready is False
