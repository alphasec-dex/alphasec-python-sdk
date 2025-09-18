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
    balance = api.get_balance("0x0000000000000000000000000000000000000000")
    assert len(balance) > 0

def test_get_sessions():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    sessions = api.get_sessions("0x0000000000000000000000000000000000000000")
    assert sessions is None

def test_get_open_orders():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    orders = api.get_open_orders("0x0000000000000000000000000000000000000000", "KAIA/USDT")
    assert orders is None

def test_get_filled_canceled_orders():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"])
    orders = api.get_filled_canceled_orders("0x0000000000000000000000000000000000000000", "KAIA/USDT")
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
    expiry = int(time.time() * 1000) + 3600


    result = api.create_session("1", sess_wallet, expiry, nonce)
    assert result is True

def test_update_session():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    # sess_addr = Account.create().address
    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600
    api.create_session("1", sess_wallet, expiry, nonce)

    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600

    result = api.update_session("1", sess_wallet, expiry, nonce)
    assert result is True

def test_delete_session():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    sess_wallet = Account.create()
    nonce = int(time.time() * 1000)
    expiry = int(time.time() * 1000) + 3600
    api.create_session("1", sess_wallet, expiry, nonce)

    result = api.delete_session(sess_wallet)
    assert result is True

def test_value_transfer():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.value_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1)
    assert result is True

def test_token_transfer():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.token_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1, "USDT")
    assert result is True

def test_order():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.order("GRND/USDT", BUY, price=5.00001, quantity=0.2, order_type=LIMIT, order_mode=BASE_MODE)
    assert result is True

def test_cancel():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    api.order("GRND/USDT", BUY, price=3, quantity=20, order_type=LIMIT, order_mode=BASE_MODE)
    result = api.cancel("1")
    assert result is True

def test_cancel_all():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    api.order("GRND/USDT", BUY, price=3, quantity=20, order_type=LIMIT, order_mode=BASE_MODE)
    result = api.cancel_all()
    assert result is True

def test_modify():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    api.order("GRND/USDT", BUY, price=3, quantity=20, order_type=LIMIT, order_mode=BASE_MODE)
    result = api.modify("1", new_price=4, new_qty=20, order_mode=BASE_MODE)
    assert result is True

def test_stop_order():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.stop_order("GRND/USDT", BUY, stop_price=3, price=4, quantity=20, side=BUY, order_type=LIMIT, order_mode=BASE_MODE)
    assert result is True

def test_withdraw_to_kaia():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.withdraw_to_kaia("USDT", int(1e18), "0xac76d4a9985abA068dbae07bf5cC10be06A19f12")
    assert result["status"] == 1

def test_deposit_to_alphasec():
    config = load_config(os.path.dirname(__file__) + "/config")
    api = API(url=config["api_url"], signer=AlphasecSigner(config))

    result = api.deposit_to_alphasec("USDT", int(1e18), "0xac76d4a9985abA068dbae07bf5cC10be06A19f12")
    assert result["status"] == 1