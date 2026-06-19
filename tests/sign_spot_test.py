"""Offline unit tests for transaction/sign.py spot builders (§3.2).

No network: local ECDSA signing + local RLP decode only. Covers gaps NOT in
sign_test.py (which checks command bytes / happy-path tpsl / integer transfer):
the sl_limit-only drop, str(float) precision leak, that the session signature
is computed over the right fields, the expiry/nonce truncation + L2 chainId
(D2/D3), and a full RLP round-trip of the locally signed tx.
"""
import base64
import json
import os

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_account.typed_transactions import TypedTransaction
from hexbytes import HexBytes

from alphasec import load_config
from alphasec.transaction.constants import ALPHASEC_ORDER_CONTRACT_ADDR, DexCommandSessionCreate
from alphasec.transaction.sign import AlphasecSigner

CONFIG_DIR = os.path.dirname(__file__) + "/config"


def _signer():
    return AlphasecSigner(load_config(CONFIG_DIR))


def _register_typed_data(session_addr, nonce, expiry, chain_id):
    """Independent literal reconstruction of the RegisterSessionWallet EIP-712
    message — deliberately NOT calling signer.session_register_typed_data, so a
    swap/typo inside the builder body is caught by signature recovery."""
    return {
        "domain": {
            "name": "DEXSignTransaction",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        },
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "RegisterSessionWallet": [
                {"name": "sessionWallet", "type": "address"},
                {"name": "expiry", "type": "uint64"},
                {"name": "nonce", "type": "uint64"},
            ],
        },
        "primaryType": "RegisterSessionWallet",
        "message": {
            "sessionWallet": session_addr,
            "expiry": str(expiry),
            "nonce": str(nonce),
        },
    }


def test_order_tpsl_guard_silently_drops_sl_limit_only():
    s = _signer()
    # Guard is `tp_limit is not None or sl_trigger is not None`; an order with
    # ONLY sl_limit builds no tpsl block at all -> the stop-limit price is lost.
    payload = json.loads(s.create_order_data("1", "2", 0, 100.0, 1.0, 0, 0, sl_limit=1400)[1:].decode())
    assert "tpsl" not in payload
    # sl_trigger alone DOES build tpsl, carrying only slTrigger.
    payload = json.loads(s.create_order_data("1", "2", 0, 100.0, 1.0, 0, 0, sl_trigger=1500)[1:].decode())
    assert payload["tpsl"] == {"slTrigger": "1500"}


def test_str_float_precision_leaks_into_wire():
    s = _signer()
    to = Account.create().address
    # 0.1 + 0.2 == 0.30000000000000004; str() leaks all 17 digits onto the wire.
    payload = json.loads(s.create_value_transfer_data(to, 0.1 + 0.2)[1:].decode())
    assert payload["value"] == "0.30000000000000004"
    payload = json.loads(s.create_order_data("1", "2", 0, 0.1 + 0.2, 1.0, 0, 0)[1:].decode())
    assert payload["price"] == "0.30000000000000004"
    assert type(payload["price"]) is str   # price is a quoted string ...
    assert type(payload["side"]) is int    # ... while side stays a bare int


def test_create_session_data_signs_over_correct_fields():
    s = _signer()
    l1 = load_config(CONFIG_DIR)["l1_address"]
    sess = Account.create()
    payload = json.loads(s.create_session_data(DexCommandSessionCreate, sess.address, 1700000, 1800000)[1:].decode())
    assert payload["nonce"] == 1700000      # the `nonce` field carries timestamp_ms
    assert payload["expiresAt"] == 1800000
    # Recover against an INDEPENDENT typed-data reconstruction (literal dict, not
    # s.session_register_typed_data) so a mis-wired call in create_session_data
    # AND a swap inside the builder body both flip the recovered signer.
    expected = _register_typed_data(sess.address, nonce=1700000, expiry=1800000, chain_id=s.chain_id)
    recovered = Account.recover_message(encode_typed_data(full_message=expected), signature=base64.b64decode(payload["l1signature"]))
    assert recovered == l1
    # Negative control: the same signature must NOT verify once nonce/expiry are swapped.
    swapped = _register_typed_data(sess.address, nonce=1800000, expiry=1700000, chain_id=s.chain_id)
    assert Account.recover_message(encode_typed_data(full_message=swapped), signature=base64.b64decode(payload["l1signature"])) != l1


def test_session_register_typed_data_truncation_and_l2_chainid():
    s = _signer()
    msg = s.session_register_typed_data("0x" + "1" * 40, nonce=5, expiry=1700.9)
    assert msg["message"]["expiry"] == "1700"  # D3: str(int(1700.9)) truncation, no ms/sec scaling
    assert msg["message"]["nonce"] == "5"
    assert all(isinstance(v, str) for v in msg["message"].values())  # uint64 quoted as strings
    # D2: currently signs over the L2 chain id (tests/config -> 101). If corrected
    # to the KAIA L1 id this assertion fails, flagging exactly when D2 is fixed.
    assert msg["domain"]["chainId"] == s.chain_id == 101


def test_generate_alphasec_transaction_rlp_roundtrip():
    s = _signer()
    data = bytes([0x21]) + b'{"x":1}'
    decoded = TypedTransaction.from_bytes(HexBytes(s.generate_alphasec_transaction(1700000000123, data)[2:])).as_dict()
    assert decoded["chainId"] == 101                                   # tests/config override honored (not default 41001)
    assert HexBytes(decoded["to"]) == HexBytes(ALPHASEC_ORDER_CONTRACT_ADDR)
    assert decoded["value"] == 0
    assert decoded["nonce"] == 1700000000123                           # passed timestamp used verbatim
    assert HexBytes(decoded["data"]) == HexBytes(data)                 # input bytes preserved 1:1
    # None timestamp -> nonce 0 fallback.
    decoded0 = TypedTransaction.from_bytes(HexBytes(s.generate_alphasec_transaction(None, data)[2:])).as_dict()
    assert decoded0["nonce"] == 0
