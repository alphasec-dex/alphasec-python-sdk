"""Offline unit tests for transaction/utils.py (§3.1 of core-test-design.md).

No network, no refactor; pure logic only. Covers gaps NOT exercised by
sign_test.py::test_normalize_price_quantity* (exact .5 banker boundary, the
"positive -> 0" invariant, and the load_config wallet/session/JSON guards).
"""
import json
import os

import pytest

from alphasec.transaction.utils import load_config, normalize_price_quantity


def _cfg(dir_path, payload=None, raw=None):
    """Write tests config.json into dir_path (created if needed); return dir_path."""
    os.makedirs(dir_path, exist_ok=True)
    with open(os.path.join(dir_path, "config.json"), "w") as f:
        f.write(raw if raw is not None else json.dumps(payload))
    return dir_path


def test_npq_bankers_rounding_half_to_even():
    # price >= 10000 -> 0dp price precision. Force two EXACT .5 inputs, one even
    # one odd, so half-up vs half-even is distinguishable (a single case cannot).
    assert normalize_price_quantity(10000.5, 1.0)[0] == 10000.0  # down to even
    assert normalize_price_quantity(10001.5, 1.0)[0] == 10002.0  # up to even
    # price < 1 -> 0dp quantity precision; same half-to-even on the quantity axis.
    assert normalize_price_quantity(0.5, 2.5)[1] == 2.0  # not 3.0
    assert normalize_price_quantity(0.5, 1.5)[1] == 2.0


def test_npq_positive_quantity_silently_rounds_to_zero():
    # D4: a clearly-positive quantity passes the `quantity > 0` guard, then is
    # rounded to 0.0 with no post-round re-check (a 0-qty order can flow to wire).
    assert normalize_price_quantity(0.5, 0.5)[1] == 0.0   # price<1 -> 0dp -> round(0.5)=0.0
    assert normalize_price_quantity(1.0, 0.04)[1] == 0.0  # price 1..10 -> 1dp -> round(0.04,1)=0.0


def test_npq_quantity_precision_is_governed_by_price_not_magnitude():
    # The quantity precision is chosen from the PRICE tier, not the quantity size.
    assert normalize_price_quantity(15000.0, 0.000004)[1] == 0.0    # price>=10000 -> 5dp
    assert normalize_price_quantity(15000.0, 0.00001)[1] == 1e-05   # one digit up survives


def test_load_config_wallet_guard_is_or_boundary(tmp_path):
    addr = "0x" + "a" * 40
    wallet = "0x" + "ab" * 32
    # Neither wallet present -> rejected.
    with pytest.raises(ValueError, match="l1_wallet, l2_wallet are not set"):
        load_config(_cfg(str(tmp_path / "only_l1"), {"l1_address": addr}))
    # Either wallet alone is accepted, and the value is preserved verbatim.
    c1 = load_config(_cfg(str(tmp_path / "l1w"), {"l1_address": addr, "l1_wallet": wallet}))
    assert c1["l1_wallet"] == wallet
    c2 = load_config(_cfg(str(tmp_path / "l2w"), {"l1_address": addr, "l2_wallet": wallet}))
    assert c2["l2_wallet"] == wallet


def test_load_config_session_enabled_requires_l2_wallet(tmp_path):
    addr = "0x" + "a" * 40
    wallet = "0x" + "ab" * 32
    # session_enabled truthy + no l2_wallet -> rejected.
    with pytest.raises(ValueError, match="session_enabled is set but l2_wallet is not set"):
        load_config(_cfg(str(tmp_path / "se"), {"l1_address": addr, "l1_wallet": wallet, "session_enabled": True}))
    # session_enabled falsy short-circuits the guard.
    ok_false = load_config(_cfg(str(tmp_path / "sef"), {"l1_address": addr, "l1_wallet": wallet, "session_enabled": False}))
    assert ok_false["l1_address"] == addr
    # l2_wallet present satisfies the session guard.
    ok_l2 = load_config(_cfg(str(tmp_path / "sel2"), {"l1_address": addr, "l2_wallet": wallet, "session_enabled": True}))
    assert ok_l2["l1_address"] == addr


def test_load_config_invalid_json_becomes_valueerror(tmp_path):
    with pytest.raises(ValueError, match="Invalid config file"):
        load_config(_cfg(str(tmp_path / "bad"), raw="{not valid json"))
