import pytest
from alphasec.api.utils import market_to_market_id, split_base_quote_token

MAP = {"BTC": 1, "USDT": 2}


def test_market_missing_slash_raises_valueerror():
    with pytest.raises(ValueError):
        market_to_market_id("BTCUSDT", MAP)


def test_market_unknown_symbol_raises_valueerror():
    with pytest.raises(ValueError):
        market_to_market_id("BTC/KRW", MAP)


def test_valid_market_ok():
    assert market_to_market_id("BTC/USDT", MAP) == "1_2"
    assert split_base_quote_token("BTC/USDT", MAP) == (1, 2)
