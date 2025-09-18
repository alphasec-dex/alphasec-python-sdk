from typing import Literal
from eth_utils.address import is_address, to_checksum_address
import requests
import logging
from eth_account import Account
import time
import web3

from alphasec.api.constants import ALPHASEC_KAIROS_URL, ALPHASEC_MAINNET_URL, KAIROS_URL, MAINNET_URL
from alphasec.transaction.constants import (
    DexCommandSessionCreate,
    DexCommandSessionUpdate,
    DexCommandSessionDelete,
)
from alphasec.transaction.sign import AlphasecSigner

from .utils import market_to_market_id, _clean_params

class API:
    def __init__(self, url: str, timeout: int = None, signer: AlphasecSigner = None):
        self.url = url
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update({"Content-Type": "application/json"})
        self._logger = logging.getLogger(__name__)
        self.token_id_symbol_map, self.symbol_token_id_map, self.token_id_address_map = self.map_token_metadata()
        self.signer = signer

    def map_token_metadata(self):
        token_id_symbol_map = {}
        symbol_token_id_map = {}
        token_id_address_map = {}
        tokens = self.get_tokens()
        for token in tokens:
            token_id_symbol_map[token['tokenId']] = token['l1Symbol']
            symbol_token_id_map[token['l1Symbol']] = token['tokenId']
            token_id_address_map[token['tokenId']] = token['l1Address']
        return token_id_symbol_map, symbol_token_id_map, token_id_address_map

    def get(self, path: str, params: dict = None):
        response = self.session.get(self.url + path, params=params, timeout=self.timeout)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    def post(self, path: str, params: dict = None):
        response = self.session.post(self.url + path, json=params, timeout=self.timeout)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    def put(self, path: str, params: dict = None):
        response = self.session.put(self.url + path, json=params, timeout=self.timeout)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    def delete(self, path: str, params: dict = None):
        response = self.session.delete(self.url + path, json=params, timeout=self.timeout)
        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    def get_market_list(self):
        response = self.get("/api/v1/market")
        return response['result']

    def get_ticker(self, market: str):
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        response = self.get(f"/api/v1/market/ticker?marketId={market_id}")
        return response['result'][0]

    def get_tickers(self):
        response = self.get("/api/v1/market/ticker")
        return response['result']

    def get_tokens(self):
        response = self.get("/api/v1/market/tokens")
        return response['result']

    def get_trades(self, market: str, limit: int = 100):
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        response = self.get(f"/api/v1/market/trades?marketId={market_id}&limit={limit}")
        return response['result']

    def get_balance(self, addr: str):
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        response = self.get(f"/api/v1/wallet/balance?address={addr}")
        return response['result']

    def get_sessions(self, addr: str):
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        response = self.get(f"/api/v1/wallet/session?address={addr}")
        return response['result']

    def get_open_orders(self, addr: str, market: str, limit: int = 100, from_msec: int = None, end_msec: int = None):
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        params = _clean_params({
            "address": addr,
            "marketId": market_id,
            "limit": limit,
            "from": from_msec,
            "to": end_msec,
        })
        response = self.get(f"/api/v1/order/open", params=params)
        return response['result']

    def get_filled_canceled_orders(self, addr: str, market: str, limit: int = 100, from_msec: int = None, end_msec: int = None):
        if not is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        addr = to_checksum_address(addr)
        market_id = market_to_market_id(market, self.symbol_token_id_map)
        params = _clean_params({
            "address": addr,
            "marketId": market_id,
            "limit": limit,
            "from": from_msec,
            "to": end_msec,
        })
        response = self.get(f"/api/v1/order/", params=params)
        return response['result']

    def get_order_by_id(self, order_id: str):
        response = self.get(f"/api/v1/order/{order_id}")
        if response['code'] == 404:
            return None
        return response['result']

    def create_session(self, session_id: str, session_wallet: Account, expiry: int, nonce: int):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        if self.signer.session_enabled:
            raise ValueError("Session is already enabled")
        data = self.signer.create_session_data(DexCommandSessionCreate, session_wallet.address, nonce, expiry)
        tx = self.signer.generate_alphasec_transaction(nonce, data, session_wallet)
        response = self.post(f"/api/v1/wallet/session", params={
            "sessionId": session_id,
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def update_session(self, session_id: str, session_wallet: Account, expiry: int, nonce: int):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_session_data(DexCommandSessionUpdate, session_wallet.address, nonce, expiry)
        tx = self.signer.generate_alphasec_transaction(nonce, data, session_wallet)
        response = self.post(f"/api/v1/wallet/session/update", params={
            "sessionId": session_id,
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def delete_session(self, session_wallet: Account):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        # nonce and expiry is not used in blockchain side
        nonce = int(time.time() * 1000) # dummy
        expiry = int(time.time() * 1000) + 3600 # dummy

        data = self.signer.create_session_data(DexCommandSessionDelete, session_wallet.address, nonce, expiry)
        tx = self.signer.generate_alphasec_transaction(nonce, data, session_wallet)
        response = self.post(f"/api/v1/wallet/session/delete", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def value_transfer(self, to: str, value: int):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_value_transfer_data(to, value)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/wallet/transfer", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def token_transfer(self, to: str, value: int, token: str):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_token_transfer_data(to, value, self.symbol_token_id_map[token])
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/wallet/transfer", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def order(self, market: str, side: int, price: int, quantity: int, order_type: int, order_mode: int, tp_limit: int = None, sl_trigger: int = None, sl_limit: int = None):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        base_token, quote_token = market.split("/")
        base_token = self.symbol_token_id_map[base_token]
        quote_token = self.symbol_token_id_map[quote_token]
        data = self.signer.create_order_data(base_token, quote_token, side, price, quantity, order_type, order_mode, tp_limit, sl_trigger, sl_limit)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/order", params={
            "tx": tx,
        })
        print(response)
        if response['code'] != 200:
            return False
        return True

    def cancel(self, order_id: str):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_cancel_data(order_id)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/wallet/order/cancel", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def cancel_all(self):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_cancel_all_data()
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/wallet/order/cancel/all", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def modify(self, order_id: str, new_price: int = None, new_qty: int = None, order_mode: int = None):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_modify_data(order_id, new_price, new_qty, order_mode)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/wallet/order/modify", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    def stop_order(self, base_token: str, quote_token: str, stop_price: int, price: int, quantity: int, side: int, order_type: int, order_mode: int):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        data = self.signer.create_stop_order_data(base_token, quote_token, stop_price, price, quantity, side, order_type, order_mode)
        tx = self.signer.generate_alphasec_transaction(int(time.time() * 1000), data)
        response = self.post(f"/api/v1/wallet/order/stop", params={
            "tx": tx,
        })
        if response['code'] != 200:
            return False
        return True

    # value is in wei
    # symbol should be uppercase
    def withdraw_to_kaia(self, symbol: str, value: int, token_l1_address: str = None):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        l2_provider = None
        if self.signer.network == "mainnet":
            l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_MAINNET_URL))
        else:
            l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_KAIROS_URL))

        token_id = self.symbol_token_id_map[symbol]
        tx = self.signer.generate_withdraw_transaction(l2_provider, token_id, value, token_l1_address)
        txHash = l2_provider.eth.send_raw_transaction(tx)
        receipt = l2_provider.eth.wait_for_transaction_receipt(txHash)
        return receipt

    # value is in wei
    # symbol should be uppercase
    def deposit_to_alphasec(self, symbol: str, value: int, token_l1_address: str = None):
        if self.signer is None:
            raise ValueError("Only read-only API is available when signer is not set")

        l1_provider = None
        if self.signer.network == "mainnet":
            l1_provider = web3.Web3(web3.HTTPProvider(MAINNET_URL))
        else:
            l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))

        token_id = self.symbol_token_id_map[symbol]
        tx = self.signer.generate_deposit_transaction(l1_provider, token_id, value, token_l1_address)
        txHash = l1_provider.eth.send_raw_transaction(tx)
        receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)
        return receipt