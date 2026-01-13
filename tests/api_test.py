import os
import time
import pytest
from eth_account import Account
from alphasec.api.api import API
from alphasec import load_config, AlphasecSigner
from alphasec.api.constants import BASE_MODE, BUY, LIMIT, QUOTE_MODE


def get_config():
    return load_config(os.path.dirname(__file__) + "/config")


def get_api():
    config = get_config()
    return API(url=config["api_url"])


def get_api_with_signer():
    config = get_config()
    return API(url=config["api_url"], signer=AlphasecSigner(config))


# Read-only tests (no signer required)
def test_get_market_list():
    api = get_api()
    markets = api.get_market_list()
    assert len(markets) > 0


def test_get_depth():
    api = get_api()
    depth = api.get_depth("KAIA/USDT")
    assert len(depth) > 0


def test_get_ticker():
    api = get_api()
    ticker = api.get_ticker("KAIA/USDT")
    assert ticker['marketId'] == "1_2"


def test_get_tickers():
    api = get_api()
    tickers = api.get_tickers()
    assert len(tickers) > 0


def test_get_trades():
    api = get_api()
    trades = api.get_trades("KAIA/USDT")
    assert len(trades) > 0


def test_get_balance():
    api = get_api()
    balance = api.get_balance("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
    assert len(balance) > 0


def test_get_sessions():
    api = get_api()
    sessions = api.get_sessions("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
    # sessions can be None or a list
    assert sessions is None or isinstance(sessions, list)


def test_get_open_orders():
    api = get_api()
    orders = api.get_open_orders("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", "KAIA/USDT")
    assert orders is None or isinstance(orders, list)


def test_get_filled_canceled_orders():
    api = get_api()
    orders = api.get_filled_canceled_orders("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", "KAIA/USDT")
    assert orders is None or isinstance(orders, list)


def test_get_order_by_id():
    api = get_api()
    order = api.get_order_by_id("1")
    # order can be None if not found
    assert order is None or isinstance(order, dict)


# Write tests (require signer and correct chain ID)
# These tests are skipped by default as they require integration environment
# Set ALPHASEC_INTEGRATION_TEST=1 to run these tests

SKIP_INTEGRATION = pytest.mark.skip(reason="Integration test - requires funded wallet and live API")


@SKIP_INTEGRATION
def test_create_session():
    api = get_api_with_signer()
    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 1000

    result = api.create_session("1", sess_wallet, expiry, nonce)
    assert result['status'] is True


@SKIP_INTEGRATION
def test_update_session():
    api = get_api_with_signer()
    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 1000
    api.create_session("1", sess_wallet, expiry, nonce)

    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 10000

    result = api.update_session("1", sess_wallet, expiry, nonce)
    assert result['status'] is True


@SKIP_INTEGRATION
def test_delete_session():
    api = get_api_with_signer()
    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 1000
    api.create_session("1", sess_wallet, expiry, nonce)

    time.sleep(10)

    result = api.delete_session(sess_wallet)
    assert result['status'] is True


@SKIP_INTEGRATION
def test_value_transfer():
    api = get_api_with_signer()
    result = api.value_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1.5)
    assert result['status'] is True, result['error']


@SKIP_INTEGRATION
def test_token_transfer():
    api = get_api_with_signer()
    result = api.token_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1.5, "USDT")
    assert result['status'] is True, result['error']


@SKIP_INTEGRATION
def test_order():
    api = get_api_with_signer()
    result = api.order("GRND/USDT", BUY, price=9.999, quantity=0.555, order_type=LIMIT, order_mode=BASE_MODE)
    assert result['status'] is True, result['error']


@SKIP_INTEGRATION
def test_cancel():
    api = get_api_with_signer()
    order_result = api.order("GRND/USDT", BUY, price=3, quantity=1, order_type=LIMIT, order_mode=BASE_MODE)
    cancel_result = api.cancel(order_result['order_id'])
    assert cancel_result['status'] is True, cancel_result['error']


@SKIP_INTEGRATION
def test_cancel_all():
    api = get_api_with_signer()
    api.order("GRND/USDT", BUY, price=3, quantity=20, order_type=LIMIT, order_mode=BASE_MODE)
    cancel_result = api.cancel_all()
    assert cancel_result['status'] is True, cancel_result['error']


@SKIP_INTEGRATION
def test_modify():
    api = get_api_with_signer()
    order_result = api.order("GRND/USDT", BUY, price=3, quantity=0.5, order_type=LIMIT, order_mode=BASE_MODE)
    modify_result = api.modify(order_result['order_id'], new_price=4, new_qty=1, order_mode=BASE_MODE)
    assert modify_result['status'] is True, modify_result['error']


@SKIP_INTEGRATION
def test_stop_order():
    api = get_api_with_signer()
    stop_result = api.stop_order("GRND/USDT", stop_price=3, price=4, quantity=1, side=BUY, order_type=LIMIT, order_mode=BASE_MODE)
    assert stop_result['status'] is True, stop_result['error']


@SKIP_INTEGRATION
def test_withdraw_to_kaia():
    api = get_api_with_signer()
    result = api.withdraw_to_kaia("USDT", 1.0)
    assert result['status'] is True, result['error']


@SKIP_INTEGRATION
def test_withdraw_native_to_kaia():
    api = get_api_with_signer()
    result = api.withdraw_to_kaia("KAIA", 1.0)
    assert result['status'] is True, result['error']


@SKIP_INTEGRATION
def test_deposit_to_alphasec():
    api = get_api_with_signer()
    result = api.deposit_to_alphasec("USDT", 1.0)
    assert result['status'] is True, result['error']
