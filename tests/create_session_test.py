from alphasec.api.api import API


def test_create_session_no_enabled_guard(monkeypatch):
    api = API("http://example.invalid")
    api._initialized = True
    sent = {}

    class Signer:
        session_enabled = True
        l1_address = "0xabc"
        def create_session_data(self, *a): return b"data"
        def generate_alphasec_transaction(self, *a, **k): return "0xtx"
    api.signer = Signer()
    monkeypatch.setattr(api, "post", lambda path, params=None: sent.update(params or {}) or {"code": 200, "errMsg": None, "result": "0xhash"})

    wallet = type("W", (), {"address": "0xwallet"})()
    out = api.create_session("sid", wallet, expiry=1, nonce=2)
    assert out["status"] is True                  # passes without the guard
