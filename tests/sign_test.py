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
from alphasec.transaction.utils import normalize_price_quantity

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

    # data = signer.create_session_data(DexCommandSessionCreate, l2_acc.address, timestamp_ms, expires_at)
    data = signer.create_session_data(DexCommandSessionCreate, l2_acc.address, timestamp_ms, expires_at)
    tx = signer.generate_alphasec_transaction(timestamp_ms, data, l2_acc)

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
        "value": "123.0",
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
    assert payload["value"] == "7.0"
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
    data = signer.create_modify_data("tx_hash", order_mode=order_mode_map["base"], new_price=42.0)
    assert data[0] == DexCommandModify
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["newPrice"] == "42.0"
    assert "newQty" not in payload.keys()
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10


def test_modify_with_qty_only():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_modify_data("tx_hash", order_mode=order_mode_map["base"], new_qty=1.0)
    assert data[0] == DexCommandModify
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["newQty"] == "1.0"
    assert "newPrice" not in payload.keys()
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10

def test_modify_with_price_and_qty():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    data = signer.create_modify_data("tx_hash", order_mode=order_mode_map["base"], new_price=42.0, new_qty=1.0)
    assert data[0] == DexCommandModify
    payload = json.loads(data[1:].decode("utf-8"))
    assert payload["newPrice"] == "42.0"
    assert payload["newQty"] == "1.0"

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
    assert payload["stopPrice"] == "950.0"
    tx = signer.generate_alphasec_transaction(int(time.time() * 1000), data)
    assert tx.startswith("0x") and len(tx) > 10

@skip("skip native deposit test")
def test_native_deposit():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    NATIVE_L1_DECIMALS = 18
    raw_tx = signer.generate_deposit_transaction(l1_provider, ALPHASEC_NATIVE_TOKEN_ID, 1.0, None, NATIVE_L1_DECIMALS)
    txHash = l1_provider.eth.send_raw_transaction(raw_tx)
    receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)
    assert receipt.status == 1
    assert raw_tx.startswith("0x") and len(raw_tx) > 10


@skip("skip erc20 deposit test")
def test_erc20_deposit():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    USDT_L1_DECIMALS = 6
    raw_tx = signer.generate_deposit_transaction(l1_provider, symbol_token_id_map["USDT"], 1.0, '0xac76d4a9985abA068dbae07bf5cC10be06A19f12', USDT_L1_DECIMALS)
    txHash = l1_provider.eth.send_raw_transaction(raw_tx)
    receipt = l1_provider.eth.wait_for_transaction_receipt(txHash)
    assert receipt.status == 1
    assert raw_tx.startswith("0x") and len(raw_tx) > 10


@skip("skip native withdraw test")
def test_native_withdraw():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_KAIROS_URL))

    NATIVE_TOKEN_ID = '1'
    raw_tx = signer.generate_withdraw_transaction(l2_provider, NATIVE_TOKEN_ID, 1.0)
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

@skip("skip erc20 withdraw test")
def test_erc20_withdraw():
    config = load_config(os.path.dirname(__file__) + "/config")
    signer = AlphasecSigner(config)
    l1_provider = web3.Web3(web3.HTTPProvider(KAIROS_URL))
    l2_provider = web3.Web3(web3.HTTPProvider(ALPHASEC_KAIROS_URL))

    raw_tx = signer.generate_withdraw_transaction(l2_provider, symbol_token_id_map["USDT"], 1.0, '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')
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


def test_normalize_price_quantity():
    """Test normalize_price_quantity function with various price and quantity values"""
    
    # Test cases: (price, quantity) -> (expected_normalized_price, expected_normalized_quantity)
    test_cases = [
        # High value prices (≥ $10,000) - price: 0 decimals, quantity: 5 decimals
        (15000.0, 0.5, 15000.0, 0.5),
        (25000.123456, 0.000123456, 25000.0, 0.00012),
        (10000.0, 1.0, 10000.0, 1.0),
        
        # Medium-high value prices (≥ $1,000) - price: 1 decimal, quantity: 4 decimals
        (5000.0, 2.0, 5000.0, 2.0),
        (1500.123456, 0.000123456, 1500.1, 0.0001),
        (1000.0, 1.0, 1000.0, 1.0),
        
        # Medium value prices (≥ $100) - price: 2 decimal, quantity: 3 decimals
        (500.0, 10.0, 500.0, 10.0),
        (250.123456, 0.123456, 250.12, 0.123),
        (100.0, 1.0, 100.0, 1.0),
        
        # Low-medium value prices (≥ $10) - price: 3 decimal, quantity: 2 decimals
        (50.0, 100.0, 50.0, 100.0),
        (25.123456, 0.123456, 25.123, 0.12),
        (10.0, 1.0, 10.0, 1.0),
        
        # Low value prices (≥ $1) - price: 4 decimal, quantity: 1 decimal
        (5.0, 1000.0, 5.0, 1000.0),
        (2.5123456, 0.123456, 2.5123, 0.1),
        (1.0, 1.0, 1.0, 1.0),
        
        # Very low value prices (< $1) - price: 8 decimal, quantity: 0 decimals
        (0.5, 10000.0, 0.5, 10000.0),
        (0.25123456, 0.123456, 0.25123456, 0.0),
        (0.1, 1.0, 0.1, 1.0),
        (0.01, 100000.0, 0.01, 100000.0),
        (0.001, 1000000.0, 0.001, 1000000.0),
        (0.0001, 10000000.0, 0.0001, 10000000.0),
    ]
    
    for price, quantity, expected_price, expected_quantity in test_cases:
        normalized_price, normalized_quantity = normalize_price_quantity(price, quantity)
        
        assert normalized_price == expected_price, \
            f"Price {price} -> expected {expected_price}, got {normalized_price}"
        
        assert normalized_quantity == expected_quantity, \
            f"Quantity {quantity} -> expected {expected_quantity}, got {normalized_quantity}"


def test_normalize_price_quantity_edge_cases():
    """Test edge cases for normalize_price_quantity function"""
    
    # Test exact threshold values
    test_cases = [
        (10000.0, 1.0, 10000.0, 1.0),  # Exactly $10,000
        (1000.0, 1.0, 1000.0, 1.0),    # Exactly $1,000
        (100.0, 1.0, 100.0, 1.0),      # Exactly $100
        (10.0, 1.0, 10.0, 1.0),        # Exactly $10
        (1.0, 1.0, 1.0, 1.0),          # Exactly $1
    ]
    
    for price, quantity, expected_price, expected_quantity in test_cases:
        normalized_price, normalized_quantity = normalize_price_quantity(price, quantity)
        assert normalized_price == expected_price and normalized_quantity == expected_quantity, \
            f"Threshold test failed: ({price}, {quantity}) -> ({normalized_price}, {normalized_quantity})"
    
    # Test rounding behavior
    rounding_cases = [
        (5000.0, 0.123456, 5000.0, 0.1235),  # 4 decimals for quantity
        (50.0, 0.123456, 50.0, 0.12),        # 2 decimals for quantity
        (0.5, 0.123456, 0.5, 0.0),           # 0 decimals for quantity
        (15000.123456, 1.0, 15000.0, 1.0),   # 0 decimals for price
        (5000.123456, 1.0, 5000.1, 1.0),     # 1 decimal for price
        (500.123456, 1.0, 500.12, 1.0),      # 2 decimals for price
    ]
    
    for price, quantity, expected_price, expected_quantity in rounding_cases:
        normalized_price, normalized_quantity = normalize_price_quantity(price, quantity)
        assert normalized_price == expected_price and normalized_quantity == expected_quantity, \
            f"Rounding test failed: ({price}, {quantity}) -> ({normalized_price}, {normalized_quantity})"


def test_normalize_price_quantity_validation():
    """Test validation in normalize_price_quantity function"""
    
    # Test negative price
    try:
        normalize_price_quantity(-100.0, 1.0)
        assert False, "Should raise ValueError for negative price"
    except ValueError as e:
        assert "Price must be positive" in str(e)
    
    # Test negative quantity
    try:
        normalize_price_quantity(100.0, -1.0)
        assert False, "Should raise ValueError for negative quantity"
    except ValueError as e:
        assert "Quantity must be positive" in str(e)
    
    # Test zero price
    try:
        normalize_price_quantity(0.0, 1.0)
        assert False, "Should raise ValueError for zero price"
    except ValueError as e:
        assert "Price must be positive" in str(e)
    
    # Test zero quantity
    try:
        normalize_price_quantity(100.0, 0.0)
        assert False, "Should raise ValueError for zero quantity"
    except ValueError as e:
        assert "Quantity must be positive" in str(e)


def test_normalize_price_quantity_comprehensive():
    """Comprehensive test with various price ranges and quantities"""
    
    # Test cases covering all price ranges with specific expected outputs
    comprehensive_cases = [
        # High value prices (≥ $10,000)
        (15000.0, 0.5, 15000.0, 0.5),
        (25000.123456, 0.000123456, 25000.0, 0.00012),
        (99999.999999, 0.000001, 100000.0, 0.00000),
        
        # Medium-high value prices (≥ $1,000)
        (5000.0, 2.0, 5000.0, 2.0),
        (1500.123456, 0.000123456, 1500.1, 0.0001),
        (9999.999999, 0.0001, 10000.0, 0.0001),
        
        # Medium value prices (≥ $100)
        (500.0, 10.0, 500.0, 10.0),
        (250.123456, 0.123456, 250.12, 0.123),
        (999.999999, 0.001, 1000.0, 0.001),
        
        # Low-medium value prices (≥ $10)
        (50.0, 100.0, 50.0, 100.0),
        (25.123456, 0.123456, 25.123, 0.12),
        (99.999999, 0.01, 100.0, 0.01),
        
        # Low value prices (≥ $1)
        (5.0, 1000.0, 5.0, 1000.0),
        (2.5123456, 0.123456, 2.5123, 0.1),
        (9.999999, 0.1, 10.0, 0.1),
        
        # Very low value prices (< $1)
        (0.5, 10000.0, 0.5, 10000.0),
        (0.25123456, 0.123456, 0.25123456, 0.0),
        (0.999999999, 1.0, 1.0, 1.0),
        (0.01, 100000.0, 0.01, 100000.0),
        (0.001, 1000000.0, 0.001, 1000000.0),
        (0.0001, 10000000.0, 0.0001, 10000000.0),
        (0.00001, 100000000.0, 0.00001, 100000000.0),
    ]
    
    for price, quantity, expected_price, expected_quantity in comprehensive_cases:
        normalized_price, normalized_quantity = normalize_price_quantity(price, quantity)
        
        assert normalized_price == expected_price, \
            f"Price {price} -> expected {expected_price}, got {normalized_price}"
        
        assert normalized_quantity == expected_quantity, \
            f"Quantity {quantity} -> expected {expected_quantity}, got {normalized_quantity}"
