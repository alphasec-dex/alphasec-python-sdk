import json
import pytest
from decimal import Decimal
from eth_account import Account
from alphasec.transaction.sign import AlphasecSigner
from alphasec.transaction.utils import resolve_spot_order_price_quantity
from alphasec.perp.constants import MARKET, GTC


def _signer():
    key = Account.create().key.hex()
    return AlphasecSigner({"network": "kairos", "l1_address": Account.from_key(key).address,
                           "l1_wallet": key, "chain_id": 41001, "session_enabled": False})


def test_perp_market_order_forces_zero_price():
    data = _signer().create_perp_order_data(
        market_id=1, side=0, price=None, quantity=Decimal("0.001"),
        reduce_only=False, time_in_force=MARKET)
    wire = json.loads(data[1:].decode("utf-8"))   # strip 1-byte command
    assert wire["price"] == 0


# spot pure helper
def test_spot_market_skips_price_validation():
    assert resolve_spot_order_price_quantity(True, None, 5) == (0.0, 5)

def test_spot_market_requires_positive_quantity():
    with pytest.raises(ValueError):
        resolve_spot_order_price_quantity(True, None, 0)

def test_spot_limit_normalizes():
    p, q = resolve_spot_order_price_quantity(False, 12345.678, 1.23456)
    assert p == 12346.0 and q == 1.23456

def test_spot_limit_none_raises_valueerror():
    with pytest.raises(ValueError):
        resolve_spot_order_price_quantity(False, None, 1.0)
    with pytest.raises(ValueError):
        resolve_spot_order_price_quantity(False, 10.0, None)
