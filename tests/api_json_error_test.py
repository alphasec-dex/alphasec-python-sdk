import httpx
import pytest
from alphasec.api.api import API
from alphasec.api.async_api import AsyncAPI
from alphasec.exceptions import AlphasecAPIError


class _BadResp:
    text = "<html>not json</html>"
    def json(self): raise ValueError("not json")


def test_get_raises_on_nonjson(monkeypatch):
    api = API("http://example.invalid")
    api._initialized = True                       # skip token init
    monkeypatch.setattr(api.session, "get", lambda *a, **k: _BadResp())
    with pytest.raises(AlphasecAPIError):
        api.get("/whatever")


async def test_async_get_raises_on_nonjson():
    api = AsyncAPI("http://example.invalid")
    api._initialized = True                       # skip token init
    api._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(502, text="<html>Bad Gateway</html>")))
    try:
        with pytest.raises(AlphasecAPIError):
            await api.get("/whatever")
    finally:
        await api.close()
