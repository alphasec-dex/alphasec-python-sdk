"""Offline unit tests for REST mapping + signer guards (§3.4).

No network: neither constructor calls out (C3 made sync construction lazy); a
minimal in-process fake session keeps any lazy token fetch offline. Covers the
full signer=None write-method guard sweep (sync/async parity) and the base/quote
ordering of market_to_market_id, including that a non-two-segment market is now
rejected (E1 supersedes the old D5 truncation invariant).
"""
import pytest

from alphasec.api.api import API
from alphasec.api.async_api import AsyncAPI
from alphasec.api.utils import market_to_market_id, split_base_quote_token

# Minimal offline token metadata so the SYNC API constructor (which eagerly
# fetches /market/tokens) never hits the network.
_TOKENS = [
    {"tokenId": "1", "l2Symbol": "KAIA", "l1Address": "0x" + "11" * 20, "l1Decimal": 18},
    {"tokenId": "2", "l2Symbol": "USDT", "l1Address": "0x" + "22" * 20, "l1Decimal": 6},
]

GOOD = "0x" + "a" * 40


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        assert url.endswith("/api/v1/market/tokens"), f"unexpected url: {url}"
        return _FakeResponse({"result": _TOKENS})


# (method, args): args are valid in shape so a MISSING guard would reach the
# network or a different validation. stop_order passes side=99 to prove the
# signer guard fires before side validation ("read-only", not "Invalid side").
WRITE_METHODS = [
    ("order", ("KAIA/USDT", 0, 1.0, 1.0, 0, 0)),
    ("cancel", ("o1",)),
    ("cancel_all", ()),
    ("modify", ("o1", 1.0, 1.0, 0)),
    ("stop_order", ("KAIA/USDT", 1.0, 1.0, 1.0, 99, 0, 0)),
    ("value_transfer", (GOOD, 1.0)),
    ("token_transfer", (GOOD, 1.0, "USDT")),
    ("create_session", ("s", object(), 1, 1)),
    ("update_session", ("s", object(), 1, 1)),
    ("delete_session", (object(),)),
    ("withdraw_to_kaia", ("USDT", 1.0)),
    ("deposit_to_alphasec", ("USDT", 1.0)),
]


@pytest.mark.parametrize("name,args", WRITE_METHODS, ids=[m[0] for m in WRITE_METHODS])
async def test_async_write_methods_require_signer(name, args):
    # Constructor must not touch the network when signer is None.
    api = AsyncAPI(url="http://offline.invalid", signer=None)
    try:
        with pytest.raises(ValueError, match="read-only"):
            await getattr(api, name)(*args)
    finally:
        await api.close()


@pytest.mark.parametrize("name,args", WRITE_METHODS, ids=[m[0] for m in WRITE_METHODS])
def test_sync_write_methods_require_signer(monkeypatch, name, args):
    monkeypatch.setattr("alphasec.api.api.requests.Session", lambda: _FakeSession())
    api = API(url="http://offline.invalid", signer=None)
    with pytest.raises(ValueError, match="read-only"):
        getattr(api, name)(*args)


def test_market_to_market_id_preserves_base_quote_order():
    m = {"KAIA": "1", "USDT": "2"}
    assert market_to_market_id("KAIA/USDT", m) == "1_2"
    assert market_to_market_id("USDT/KAIA", m) == "2_1"
    assert split_base_quote_token("USDT/KAIA", m) == ("2", "1")


def test_market_to_market_id_rejects_third_segment():
    m = {"KAIA": "1", "USDT": "2", "EXTRA": "9"}
    # E1 supersedes the old D5 truncation invariant: a market that does not have
    # exactly two slash-segments is now rejected as malformed (fail-fast) instead
    # of being silently truncated to its first two segments.
    with pytest.raises(ValueError):
        market_to_market_id("KAIA/USDT/EXTRA", m)
    with pytest.raises(ValueError):
        split_base_quote_token("KAIA/USDT/EXTRA", m)
