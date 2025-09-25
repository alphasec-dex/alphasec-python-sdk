import os
import time
from eth_account import Account
from alphasec.api.api import API
from alphasec import load_config, AlphasecSigner
from alphasec.api.constants import BASE_MODE, BUY, LIMIT, QUOTE_MODE

def test_get_market_list():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    markets = api.get_market_list()
    assert len(markets) > 0

def test_get_ticker():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    ticker = api.get_ticker("KAIA/USDT")
    assert ticker['marketId'] == "1_2"

def test_get_tickers():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    tickers = api.get_tickers()
    assert len(tickers) > 0

def test_get_trades():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    trades = api.get_trades("KAIA/USDT")
    assert len(trades) > 0

def test_get_balance():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    balance = api.get_balance("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
    assert len(balance) > 0

def test_get_sessions():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    sessions = api.get_sessions("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
    assert sessions is not None

def test_get_open_orders():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    orders = api.get_open_orders("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", "KAIA/USDT")
    assert orders is None

def test_get_filled_canceled_orders():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    orders = api.get_filled_canceled_orders("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", "KAIA/USDT")
    assert orders is None

def test_get_order_by_id():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    order = api.get_order_by_id("1")
    assert order is None

def test_create_session():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    # sess_addr = Account.create().address
    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 1000


    result = api.create_session("1", sess_wallet, expiry, nonce)
    assert result['status'] is True

def test_update_session():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    # sess_addr = Account.create().address
    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 1000
    api.create_session("1", sess_wallet, expiry, nonce)

    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 10000

    result = api.update_session("1", sess_wallet, expiry, nonce)
    assert result['status'] is True

def test_delete_session():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600 * 1000
    api.create_session("1", sess_wallet, expiry, nonce)

    time.sleep(10)

    result = api.delete_session(sess_wallet)
    assert result['status'] is True

def test_value_transfer():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.value_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1.5)
    assert result['status'] is True, result['error']

def test_token_transfer():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.token_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1.5, "USDT")
    assert result['status'] is True, result['error']

def test_order():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.order("GRND/USDT", BUY, price=9.999, quantity=0.555, order_type=LIMIT, order_mode=BASE_MODE)
    assert result['status'] is True, result['error']

def test_cancel():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    order_result = api.order("GRND/USDT", BUY, price=3, quantity=1, order_type=LIMIT, order_mode=BASE_MODE)
    cancel_result = api.cancel(order_result['order_id'])
    assert cancel_result['status'] is True, cancel_result['error']

def test_cancel_all():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    api.order("GRND/USDT", BUY, price=3, quantity=20, order_type=LIMIT, order_mode=BASE_MODE)
    cancel_result = api.cancel_all()
    assert cancel_result['status'] is True, cancel_result['error']

def test_modify():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    order_result = api.order("GRND/USDT", BUY, price=3, quantity=0.5, order_type=LIMIT, order_mode=BASE_MODE)
    modify_result = api.modify(order_result['order_id'], new_price=4, new_qty=1, order_mode=BASE_MODE)
    assert modify_result['status'] is True, modify_result['error']

def test_stop_order():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    stop_result = api.stop_order("GRND/USDT", stop_price=3, price=4, quantity=1, side=BUY, order_type=LIMIT, order_mode=BASE_MODE)
    assert stop_result['status'] is True, stop_result['error']

def test_withdraw_to_kaia():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.withdraw_to_kaia("USDT", 1.0, "0xac76d4a9985abA068dbae07bf5cC10be06A19f12")
    assert result['status'] is True, result['error']

def test_withdraw_native_to_kaia():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.withdraw_to_kaia("KAIA", 1.0)
    assert result['status'] is True, result['error']

def test_deposit_to_alphasec():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.deposit_to_alphasec("USDT", 1.0, "0xac76d4a9985abA068dbae07bf5cC10be06A19f12")
    assert result['status'] is True, result['error']