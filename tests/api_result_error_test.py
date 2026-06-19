import pytest
from alphasec.api.api import API
from alphasec.exceptions import AlphasecAPIError


def test_extract_result_missing_raises():
    with pytest.raises(AlphasecAPIError):
        API._extract_result({"code": 500, "errMsg": "boom"})


def test_extract_result_present_returns():
    assert API._extract_result({"result": [1, 2]}) == [1, 2]


def test_get_order_by_id_non_dict_raises_api_error(monkeypatch):
    api = API("http://example.invalid")
    api._initialized = True

    class _ListResp:
        def json(self): return ["unexpected"]

    monkeypatch.setattr(api.session, "get", lambda *a, **k: _ListResp())
    with pytest.raises(AlphasecAPIError):
        api.get_order_by_id("x")
