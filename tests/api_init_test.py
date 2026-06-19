import pytest
from alphasec.api.api import API


def test_api_construction_is_offline(monkeypatch):
    calls = {"n": 0}
    def fake_map(self):
        calls["n"] += 1
        return ({1: "BTC"}, {"BTC": 1}, {1: "0xabc"}, {1: 18})
    monkeypatch.setattr(API, "map_token_metadata", fake_map)

    api = API("http://example.invalid")          # no network in constructor
    assert calls["n"] == 0
    assert api.symbol_token_id_map == {} and api._initialized is False

    api._ensure_initialized()                     # init on first use
    assert calls["n"] == 1 and api._initialized is True
    assert api.symbol_token_id_map == {"BTC": 1}


def test_empty_token_response_is_not_latched(monkeypatch):
    seq = [({}, {}, {}, {}), ({1: "BTC"}, {"BTC": 1}, {1: "0xabc"}, {1: 18})]
    monkeypatch.setattr(API, "map_token_metadata", lambda self: seq.pop(0))
    api = API("http://example.invalid")
    api._ensure_initialized()                     # empty response -> not latched
    assert api._initialized is False
    api._ensure_initialized()                     # retry -> populated
    assert api._initialized is True and api.symbol_token_id_map == {"BTC": 1}
