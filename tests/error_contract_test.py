"""Offline error-contract tests for API / AsyncAPI.

All HTTP traffic is served in-process: httpx.MockTransport for AsyncAPI and
a fake requests session for the sync API. No network access is required;
signing (where used) is local ECDSA only.
"""
import asyncio
import os

import httpx
import pytest

from alphasec import AlphasecSigner, load_config
from alphasec.api.api import API
from alphasec.api.async_api import AsyncAPI
from alphasec.api.constants import BASE_MODE, BUY, LIMIT
from alphasec.exceptions import AlphasecAPIError

TOKENS_PATH = "/api/v1/market/tokens"
TOKENS_RESULT = [
    {"tokenId": "1", "l2Symbol": "KAIA", "l1Address": "0x" + "11" * 20, "l1Decimal": 18},
    {"tokenId": "2", "l2Symbol": "USDT", "l1Address": "0x" + "22" * 20, "l1Decimal": 6},
]


def make_async_api(handler, signer=None) -> AsyncAPI:
    """Create an AsyncAPI whose HTTP client is backed by httpx.MockTransport.

    The client is assigned directly: lazy init only creates a client when
    ``_client is None``, so the mock client is never replaced.
    """
    api = AsyncAPI(url="http://offline.test", signer=signer)
    api._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Content-Type": "application/json"},
    )
    return api


class FakeResponse:
    """Minimal offline stand-in for requests.Response."""

    def __init__(self, json_data=None, text="", non_json=False):
        self._json_data = json_data
        self._non_json = non_json
        self.text = text

    def json(self):
        if self._non_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._json_data


class FakeSession:
    """Offline stand-in for requests.Session routing GET requests by URL."""

    def __init__(self, route):
        self._route = route
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        return self._route(url)


def patch_sync_session(monkeypatch, route) -> None:
    """Make API() construct with a FakeSession instead of requests.Session."""
    monkeypatch.setattr(
        "alphasec.api.api.requests.Session", lambda: FakeSession(route)
    )


@pytest.mark.asyncio
async def test_async_non_json_then_recovery_on_same_instance():
    state = {"token_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKENS_PATH:
            state["token_calls"] += 1
            if state["token_calls"] == 1:
                return httpx.Response(502, text="<html>Bad Gateway</html>")
            return httpx.Response(200, json={"result": TOKENS_RESULT})
        if request.url.path == "/api/v1/market":
            return httpx.Response(200, json={"result": [{"marketId": "1_2"}]})
        raise AssertionError(f"unexpected path: {request.url.path}")

    api = make_async_api(handler)
    try:
        with pytest.raises(AlphasecAPIError):
            await api.get_market_list()
        # Failure must not latch the initialized state or partial maps.
        assert api._initialized is False
        assert api.symbol_token_id_map == {}

        # Same instance, next call: must retry token fetch and succeed.
        markets = await api.get_market_list()
        assert markets == [{"marketId": "1_2"}]
        assert api.symbol_token_id_map == {"KAIA": "1", "USDT": "2"}
    finally:
        await api.close()


def test_sync_constructor_non_json_raises_alphasec_api_error(monkeypatch):
    patch_sync_session(
        monkeypatch,
        lambda url: FakeResponse(text="<html>Bad Gateway</html>", non_json=True),
    )

    with pytest.raises(AlphasecAPIError) as exc_info:
        API(url="http://offline.test")
    assert "Failed to fetch token metadata" in str(exc_info.value)


@pytest.mark.asyncio
async def test_missing_result_same_exception_sync_and_async(monkeypatch):
    error_payload = {"code": 500, "error": "boom"}

    patch_sync_session(monkeypatch, lambda url: FakeResponse(json_data=error_payload))
    with pytest.raises(AlphasecAPIError) as sync_exc:
        API(url="http://offline.test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=error_payload)

    api = make_async_api(handler)
    try:
        with pytest.raises(AlphasecAPIError) as async_exc:
            await api.initialize()
    finally:
        await api.close()

    assert type(sync_exc.value) is type(async_exc.value) is AlphasecAPIError
    assert str(sync_exc.value) == str(async_exc.value)


def _sync_order_route(url: str) -> FakeResponse:
    if url.endswith(TOKENS_PATH):
        return FakeResponse(json_data={"result": TOKENS_RESULT})
    if url.endswith("/api/v1/order/notfound"):
        # Real QA shape captured live: a missing order returns app-level
        # code -1001 ("Resource not found"). The HTTP 404 status is discarded
        # by get(), so the dict carries -1001, never 404.
        return FakeResponse(json_data={"code": -1001, "errMsg": "Resource not found"})
    if url.endswith("/api/v1/order/500"):
        return FakeResponse(json_data={"code": 500, "errMsg": "internal error"})
    if url.endswith("/api/v1/order/proxy"):
        return FakeResponse(text="<html>503 Service Unavailable</html>", non_json=True)
    raise AssertionError(f"unexpected url: {url}")


def _async_order_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == TOKENS_PATH:
        return httpx.Response(200, json={"result": TOKENS_RESULT})
    if path == "/api/v1/order/notfound":
        # Real QA emits HTTP 404 + body code -1001; get() returns only the body.
        return httpx.Response(404, json={"code": -1001, "errMsg": "Resource not found"})
    if path == "/api/v1/order/500":
        return httpx.Response(500, json={"code": 500, "errMsg": "internal error"})
    if path == "/api/v1/order/proxy":
        return httpx.Response(503, text="<html>503 Service Unavailable</html>")
    raise AssertionError(f"unexpected path: {path}")


def test_sync_get_order_by_id_notfound_none_other_errors_raise(monkeypatch):
    patch_sync_session(monkeypatch, _sync_order_route)
    api = API(url="http://offline.test")

    assert api.get_order_by_id("notfound") is None
    with pytest.raises(AlphasecAPIError):
        api.get_order_by_id("500")
    with pytest.raises(AlphasecAPIError):
        api.get_order_by_id("proxy")


@pytest.mark.asyncio
async def test_async_get_order_by_id_notfound_none_other_errors_raise():
    api = make_async_api(_async_order_handler)
    try:
        assert await api.get_order_by_id("notfound") is None
        with pytest.raises(AlphasecAPIError):
            await api.get_order_by_id("500")
        with pytest.raises(AlphasecAPIError):
            await api.get_order_by_id("proxy")
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_async_order_response_mapping():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)

    state = {"order_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKENS_PATH:
            return httpx.Response(200, json={"result": TOKENS_RESULT})
        if request.url.path == "/api/v1/order" and request.method == "POST":
            state["order_calls"] += 1
            if state["order_calls"] == 1:
                return httpx.Response(
                    200, json={"code": 200, "errMsg": "", "result": "order-123"}
                )
            return httpx.Response(
                200, json={"code": 400, "errMsg": "insufficient balance"}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    api = make_async_api(handler, signer=signer)
    try:
        accepted = await api.order(
            "KAIA/USDT", BUY, price=1.5, quantity=10,
            order_type=LIMIT, order_mode=BASE_MODE,
        )
        assert accepted == {"status": True, "error": "", "order_id": "order-123"}

        rejected = await api.order(
            "KAIA/USDT", BUY, price=1.5, quantity=10,
            order_type=LIMIT, order_mode=BASE_MODE,
        )
        assert rejected == {
            "status": False,
            "error": "insufficient balance",
            "order_id": None,
        }
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_async_api_concurrent_requests_single_instance():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == TOKENS_PATH:
            return httpx.Response(200, json={"result": TOKENS_RESULT})
        if path == "/api/v1/market/depth":
            return httpx.Response(
                200,
                json={"result": {"marketId": request.url.params["marketId"],
                                 "asks": [], "bids": []}},
            )
        if path == "/api/v1/market":
            return httpx.Response(200, json={"result": [{"marketId": "1_2"}]})
        raise AssertionError(f"unexpected path: {path}")

    api = make_async_api(handler)
    try:
        results = await asyncio.gather(
            *[api.get_depth("KAIA/USDT") for _ in range(10)],
            *[api.get_market_list() for _ in range(10)],
        )
    finally:
        await api.close()

    for depth in results[:10]:
        assert depth["marketId"] == "1_2"
    for markets in results[10:]:
        assert markets == [{"marketId": "1_2"}]
