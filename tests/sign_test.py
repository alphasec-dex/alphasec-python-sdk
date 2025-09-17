import os
import time
from unittest import skip

from eth_account import Account
import json

import web3
from alphasec.api.constants import ALPHASEC_KAIROS_URL, KAIROS_URL
from alphasec.transaction.sign import (
    AlphasecSigner,
)

from alphasec.transaction.constants import (
    ALPHASEC_NATIVE_TOKEN_ID,
    DexCommandSessionCreate,
    DexCommandTransfer,
    DexCommandTokenTransfer,
    DexCommandOrder,
    DexCommandCancel,
    DexCommandCancelAll,
    DexCommandModify,
    DexCommandStopOrder,
)
from alphasec import load_config

symbol_token_id_map = {
    "BTC": '1',
    "USDT": '2',
    "ETH": '3',
    "USDC": '4',
    "DOGE": '5',
}
side_map = {
    "buy": 0,
    "sell": 1,
}
order_type_map = {
    "limit": 0,
    "market": 1,
}
order_mode_map = {
    "base": 0,
    "quote": 1,
}

def test_session_register():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)

    l2_acc = Account.create()
    l1_addr = config["l1_address"]

    timestamp_ms = int(time.time() * 1000)
    expires_at = int(time.time() * 1000) + 3600
    
    data = signer.create_session_data(DexCommandSessionCreate, l2_acc.address, timestamp_ms, expires_at)
    tx = signer.generate_alphasec_transaction(timestamp_ms, data)

    payload = json.loads(data[1:].decode("utf-8"))

    assert data[0] == DexCommandSessionCreate
    assert payload["publickey"] == l2_acc.address
    assert payload["l1owner"] == l1_addr
    assert isinstance(payload["l1signature"], str) and len(payload["l1signature"]) > 0
    assert tx.startswith("0x")


def test_value_transfer():
    config = load_config(os.path.dirname(__file__) + "/config")
    acc_to = Account.create()
    signer = AlphasecSigner(config)
    data = signer.create_value_transfer_data(acc_to.address, 123)
    assert data[0] == DexCommandTransfer
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload == {
        "l1owner": config["l1_address"],
        "to": acc_to.address,
        "value": "123",
    }
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_token_transfer():
    config = load_config(os.path.dirname(__file__) + "/config")
    acc_to = Account.create()
    signer = AlphasecSigner(config)
    data = signer.create_token_transfer_data(acc_to.address, 7, symbol_token_id_map["USDT"])
    assert data[0] == DexCommandTokenTransfer
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["l1owner"] == config["l1_address"]
    assert payload["to"] == acc_to.address
    assert payload["value"] == "7"
    assert payload["token"] == symbol_token_id_map["USDT"]
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_order_without_tpsl():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_order_data(
        base_token=symbol_token_id_map["BTC"],
        quote_token=symbol_token_id_map["USDT"],
        side=side_map["buy"],
        price=1000,
        quantity=1,
        order_type=order_type_map["limit"],
        order_mode=order_mode_map["base"],
    )
    assert data[0] == DexCommandOrder
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["baseToken"] == symbol_token_id_map["BTC"]
    assert "tpsl" not in payload
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_order_with_tpsl():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_order_data(
        base_token=symbol_token_id_map["ETH"],
        quote_token=symbol_token_id_map["USDT"],
        side=1,
        price=2000,
        quantity=2,
        order_type=order_type_map["limit"],
        order_mode=order_mode_map["base"],
        tp_limit=2500,
        sl_trigger=1500,
        sl_limit=1400,
    )
    assert data[0] == DexCommandOrder
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["tpsl"]["tpLimit"] == "2500"
    assert payload["tpsl"]["slTrigger"] == "1500"
    assert payload["tpsl"]["slLimit"] == "1400"
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_cancel():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_cancel_data("order-123")
    assert data[0] == DexCommandCancel
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload == {"l1owner": config["l1_address"], "orderId": "order-123"}
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_cancel_all():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_cancel_all_data()
    assert data[0] == DexCommandCancelAll
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload == {"l1owner": config["l1_address"]}
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_modify_with_price_only():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_modify_data("order-xyz", new_price=42, new_qty=0, order_mode=order_mode_map["base"])
    assert data[0] == DexCommandModify
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["newPrice"] == "42"
    assert "newQty" not in payload or payload["newQty"] in ("0", 0)
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_stop_order():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_stop_order_data(
        base_token=symbol_token_id_map["BTC"],
        quote_token=symbol_token_id_map["USDT"],
        stop_price=950,
        price=960,
        quantity=1,
        side=side_map["buy"],
        order_type=order_type_map["limit"],
        order_mode=order_mode_map["base"],
    )
    assert data[0] == DexCommandStopOrder
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["stopPrice"] == "950"
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_native_deposit():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    raw_tx = signer.generate_deposit_transaction(l1_provider, ALPHASEC_NATIVE_TOKEN_ID, int(1e18))
    txHash = l1_provider.eth.send_raw_transaction(raw_tx)
    receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)
    assert receipt.status == 1
    assert raw_tx.startswith("0x") and len(raw_tx) > 10


def test_erc20_deposit():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    raw_tx = signer.generate_deposit_transaction(l1_provider, symbol_token_id_map["USDT"], int(1e18), '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')
    txHash = l1_provider.eth.send_raw_transaction(raw_tx)
    receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)
    assert receipt.status == 1
    assert raw_tx.startswith("0x") and len(raw_tx) > 10


def test_native_withdraw():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_KAIROS_URL))

    raw_tx = signer.generate_withdraw_transaction(l2_provider, '1', int(1e18))
    txHash = l2_provider.eth.send_raw_transaction(raw_tx)
    receipt = l2_provider.eth.wait_for_transaction_receipt(txHash)
    assert receipt.status == 1
    assert raw_tx.startswith("0x") and len(raw_tx) > 10

    # _, root, proof, l2_to_l1_event = signer.get_withdraw_info_on_l2(l2_provider, receipt.blockNumber)
    # i = 0
    # while not signer.is_withdraw_proof_registered(l1_provider, root):
    #     i += 1
    #     print("waiting for proof to be registered...", i)
    #     time.sleep(10)

    # raw_tx = signer.generate_withdraw_transaction_on_l1(l1_provider, proof, l2_to_l1_event)
    # txHash = l1_provider.eth.send_raw_transaction(raw_tx)
    # receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)
    # assert receipt.status == 1
    # assert raw_tx.startswith("0x") and len(raw_tx) > 10

def test_erc20_withdraw():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_KAIROS_URL))

    raw_tx = signer.generate_withdraw_transaction(l2_provider, symbol_token_id_map["USDT"], int(1e18), '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')
    txHash = l2_provider.eth.send_raw_transaction(raw_tx)
    receipt = l2_provider.eth.wait_for_transaction_receipt(txHash)
    assert receipt.status == 1
    assert raw_tx.startswith("0x") and len(raw_tx) > 10

    # _, root, proof, l2_to_l1_event = signer.get_withdraw_info_on_l2(l2_provider, receipt.blockNumber)
    # i = 0
    # while not signer.is_withdraw_proof_registered(l1_provider, root):
    #     i += 1
    #     print("waiting for proof to be registered...", i)
    #     time.sleep(10)

    # raw_tx = signer.generate_withdraw_transaction_on_l1(l1_provider, proof, l2_to_l1_event)
    # txHash = l1_provider.eth.send_raw_transaction(raw_tx)
    # receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)

    # assert receipt.status == 1
    # assert raw_tx.startswith("0x") and len(raw_tx) > 10
