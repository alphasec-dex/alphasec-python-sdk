"""Golden-hex wire-compatibility tests for perp transactions.

The expected hex values are captured from alphasec-rust-sdk (handoff doc section 4).
Python must emit byte-identical wire bytes for the same inputs, which pins the
JSON key order, the int-vs-string typing, the 10^18 truncation scaling, and the
optional-field omission rules. A single wrong byte here means a rejected or
misinterpreted order on the server.
"""

from decimal import Decimal

import pytest

from alphasec.transaction.sign import AlphasecSigner, perp_scale

# Well-known test key (handoff section 4); derives to the lowercase address below.
TEST_KEY = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TEST_ADDR = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"


@pytest.fixture
def signer() -> AlphasecSigner:
    return AlphasecSigner(
        {
            "network": "kairos",
            "l1_address": TEST_ADDR,
            "l1_wallet": TEST_KEY,
            "session_enabled": False,
        }
    )


def test_order_gtc_buy(signer):
    wire = signer.create_perp_order_data(1, 0, Decimal("50000"), Decimal("0.5"), False, 0, None)
    assert wire.hex() == (
        "417b2269735265647563654f6e6c79223a66616c73652c226c316f776e6572223a223078"
        "66333966643665353161616438386636663463653661623838323732373963666666623932"
        "323636222c226d61726b65744964223a312c2273696465223a302c2274696d65496e466f72"
        "6365223a302c227072696365223a35303030303030303030303030303030303030303030302c"
        "227175616e74697479223a3530303030303030303030303030303030307d"
    )


def test_order_market_sell_cid(signer):
    wire = signer.create_perp_order_data(1, 1, Decimal("0.1"), Decimal("2"), True, 3, "cid-1")
    assert wire.hex() == (
        "417b22636c69656e744f726465724964223a226369642d31222c2269735265647563654f6e"
        "6c79223a747275652c226c316f776e6572223a223078663339666436653531616164383866"
        "36663463653661623838323732373963666666623932323636222c226d61726b6574496422"
        "3a312c2273696465223a312c2274696d65496e466f726365223a332c227072696365223a31"
        "30303030303030303030303030303030302c227175616e74697479223a3230303030303030"
        "30303030303030303030307d"
    )


def test_cancel(signer):
    wire = signer.create_perp_cancel_data(1, "0xORDERID01")
    assert wire.hex() == (
        "427b226c316f776e6572223a223078663339666436653531616164383866366634636536"
        "61623838323732373963666666623932323636222c226d61726b65744964223a312c226f72"
        "6465724964223a2230784f5244455249443031227d"
    )


def test_cancel_all(signer):
    wire = signer.create_perp_cancel_all_data(1)
    assert wire.hex() == (
        "437b226c316f776e6572223a223078663339666436653531616164383866366634636536"
        "61623838323732373963666666623932323636222c226d61726b65744964223a317d"
    )


def test_set_leverage(signer):
    wire = signer.create_perp_set_leverage_data(1, 5)
    assert wire.hex() == (
        "457b226c316f776e6572223a223078663339666436653531616164383866366634636536"
        "61623838323732373963666666623932323636222c226d61726b65744964223a312c226c65"
        "766572616765223a357d"
    )


def test_modify_price_only(signer):
    wire = signer.create_perp_modify_data(1, "0xORDERID01", new_price=Decimal("49000"), new_quantity=None, client_order_id=None)
    assert wire.hex() == (
        "4a7b226c316f776e6572223a223078663339666436653531616164383866366634636536"
        "61623838323732373963666666623932323636222c226d61726b65744964223a312c226f72"
        "6465724964223a2230784f5244455249443031222c226e65775072696365223a3439303030"
        "3030303030303030303030303030303030307d"
    )


def test_modify_cid_empty(signer):
    wire = signer.create_perp_modify_data(1, "0xORDERID01", None, None, client_order_id="")
    assert wire.hex() == (
        "4a7b22636c69656e744f726465724964223a22222c226c316f776e6572223a2230786633"
        "3966643665353161616438386636663463653661623838323732373963666666623932323636"
        "222c226d61726b65744964223a312c226f726465724964223a2230784f5244455249443031227d"
    )


def test_deposit(signer):
    wire = signer.create_perp_deposit_data("USDT", Decimal("100.5"))
    assert wire.hex() == (
        "127b226c316f776e6572223a223078663339666436653531616164383866366634636536"
        "61623838323732373963666666623932323636222c22746f6b656e223a2255534454222c22"
        "616d6f756e74223a22313030353030303030303030303030303030303030227d"
    )


def test_withdraw(signer):
    wire = signer.create_perp_withdraw_data("USDT", Decimal("100.5"))
    assert wire.hex() == (
        "447b226c316f776e6572223a223078663339666436653531616164383866366634636536"
        "61623838323732373963666666623932323636222c22746f6b656e223a2255534454222c22"
        "616d6f756e74223a22313030353030303030303030303030303030303030227d"
    )


# perp_scale boundary behavior (ported from rust src/signer/utils.rs tests).
def test_perp_scale_truncates_floor_not_round():
    assert perp_scale(Decimal("1.9999999999999999999")) == 1999999999999999999


def test_perp_scale_below_granularity_is_zero():
    assert perp_scale(Decimal("0.0000000000000000001")) == 0


def test_perp_scale_signed_zero_allowed():
    assert perp_scale(Decimal("-0.0")) == 0


def test_perp_scale_rejects_negative():
    with pytest.raises(ValueError):
        perp_scale(Decimal("-1"))


def test_perp_scale_rejects_float():
    with pytest.raises(TypeError):
        perp_scale(0.1)


def test_perp_scale_overflow_rejected():
    with pytest.raises(ValueError):
        perp_scale(Decimal("8000000000000"))
    # just under the overflow boundary still scales
    assert perp_scale(Decimal("79228162514")) == 79228162514000000000000000000
