import os
import time
import pytest
from eth_account import Account
from alphasec.api.async_api import AsyncAPI
from alphasec import load_config, AlphasecSigner
from alphasec.api.constants import BASE_MODE, BUY, LIMIT

# Whole file hits the live exchange backend; excluded by default, run with -m live.
pytestmark = pytest.mark.live


def get_config():
    return load_config(os.path.dirname(__file__) + "/config")


# Read-only tests (no signer required)
@pytest.mark.asyncio
async def test_get_market_list():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        markets = await api.get_market_list()
        assert len(markets) > 0


@pytest.mark.asyncio
async def test_get_depth():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        depth = await api.get_depth("KAIA/USDT")
        assert len(depth) > 0


@pytest.mark.asyncio
async def test_get_ticker():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        ticker = await api.get_ticker("KAIA/USDT")
        assert ticker['marketId'] == "1_2"


@pytest.mark.asyncio
async def test_get_tickers():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        tickers = await api.get_tickers()
        assert len(tickers) > 0


@pytest.mark.asyncio
async def test_get_trades():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        trades = await api.get_trades("KAIA/USDT")
        assert isinstance(trades, list)


@pytest.mark.asyncio
async def test_get_balance():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        balance = await api.get_balance("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
        assert len(balance) > 0


@pytest.mark.asyncio
async def test_get_sessions():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        sessions = await api.get_sessions("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c")
        # sessions can be None or a list
        assert sessions is None or isinstance(sessions, list)


@pytest.mark.asyncio
async def test_get_open_orders():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        orders = await api.get_open_orders("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", "KAIA/USDT")
        assert orders is None or isinstance(orders, list)


@pytest.mark.asyncio
async def test_get_filled_canceled_orders():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        orders = await api.get_filled_canceled_orders("0x70dBb395AF2eDCC2833D803C03AbBe56ECe7c25c", "KAIA/USDT")
        assert orders is None or isinstance(orders, list)


@pytest.mark.asyncio
async def test_get_order_by_id():
    config = get_config()
    async with AsyncAPI(url=config["api_url"]) as api:
        order = await api.get_order_by_id("1")
        # order can be None if not found
        assert order is None or isinstance(order, dict)


# Write tests (require signer and correct chain ID)


@pytest.mark.asyncio
async def test_create_session():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        sess_wallet = Account.create()
        nonce = int(time.time() * 1000)
        expiry = int(time.time() * 1000) + 3600 * 1000

        result = await api.create_session("1", sess_wallet, expiry, nonce)
        assert result['status'] is True


@pytest.mark.asyncio
async def test_update_session():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        sess_wallet = Account.create()
        nonce = int(time.time() * 1000)
        expiry = int(time.time() * 1000) + 3600 * 1000
        await api.create_session("1", sess_wallet, expiry, nonce)

        nonce = int(time.time() * 1000)
        expiry = int(time.time() * 1000) + 3600 * 10000

        result = await api.update_session("1", sess_wallet, expiry, nonce)
        assert result['status'] is True


@pytest.mark.asyncio
async def test_delete_session():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        sess_wallet = Account.create()
        nonce = int(time.time() * 1000)
        expiry = int(time.time() * 1000) + 3600 * 1000
        await api.create_session("1", sess_wallet, expiry, nonce)

        import asyncio
        await asyncio.sleep(10)

        result = await api.delete_session(sess_wallet)
        assert result['status'] is True


@pytest.mark.asyncio
async def test_value_transfer():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        result = await api.value_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1.5)
        assert result['status'] is True, result['error']


@pytest.mark.asyncio
async def test_token_transfer():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        result = await api.token_transfer("0x4D3cF56fB96c287387606862df55005d52FEa89b", 1.5, "USDT")
        assert result['status'] is True, result['error']


@pytest.mark.asyncio
async def test_order():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        result = await api.order("GRND/USDT", BUY, price=9.999, quantity=0.555, order_type=LIMIT, order_mode=BASE_MODE)
        assert result['status'] is True, result['error']


@pytest.mark.asyncio
async def test_cancel():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        order_result = await api.order("GRND/USDT", BUY, price=3, quantity=1, order_type=LIMIT, order_mode=BASE_MODE)
        cancel_result = await api.cancel(order_result['order_id'])
        assert cancel_result['status'] is True, cancel_result['error']


@pytest.mark.asyncio
async def test_cancel_all():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        await api.order("GRND/USDT", BUY, price=3, quantity=20, order_type=LIMIT, order_mode=BASE_MODE)
        cancel_result = await api.cancel_all()
        assert cancel_result['status'] is True, cancel_result['error']


@pytest.mark.asyncio
async def test_modify():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        order_result = await api.order("GRND/USDT", BUY, price=3, quantity=0.5, order_type=LIMIT, order_mode=BASE_MODE)
        modify_result = await api.modify(order_result['order_id'], new_price=4, new_qty=1, order_mode=BASE_MODE)
        assert modify_result['status'] is True, modify_result['error']


@pytest.mark.asyncio
async def test_stop_order():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        stop_result = await api.stop_order("GRND/USDT", stop_price=3, price=4, quantity=1, side=BUY, order_type=LIMIT, order_mode=BASE_MODE)
        assert stop_result['status'] is True, stop_result['error']


@pytest.mark.asyncio
async def test_withdraw_to_kaia():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        result = await api.withdraw_to_kaia("USDT", 1.0)
        assert result['status'] is True, result['error']


@pytest.mark.asyncio
async def test_withdraw_native_to_kaia():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        result = await api.withdraw_to_kaia("KAIA", 1.0)
        assert result['status'] is True, result['error']


@pytest.mark.asyncio
async def test_deposit_to_alphasec():
    config = get_config()
    async with AsyncAPI(url=config["api_url"], signer=AlphasecSigner(config)) as api:
        result = await api.deposit_to_alphasec("USDT", 1.0)
        assert result['status'] is True, result['error']
