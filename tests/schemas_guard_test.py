"""Offline unit tests for address validation + deposit/withdraw guards (§3.3).

No network: every guard under test fires before any web3 provider is touched,
so the fake providers below raise loudly if reached. Covers HEX_ADDR_RE
fullmatch semantics, the D1 l1_wallet guard, the L2-endpoint guard, and the
erc20 token-address guard.
"""
import os

import pytest
from pydantic import ValidationError

from alphasec import load_config
from alphasec.transaction.schemas import HEX_ADDR_RE, ValueTransferModel
from alphasec.transaction.sign import AlphasecSigner

CONFIG_DIR = os.path.dirname(__file__) + "/config"
GOOD = "0x" + "a" * 40


class _ProviderTouchRaises:
    """Fake provider that fails loudly if any RPC surface is accessed, proving
    the guard under test fires BEFORE the provider is touched."""

    class _Provider:
        @property
        def endpoint_uri(self):
            raise AssertionError("provider.endpoint_uri touched before guard")

    class _Eth:
        def contract(self, *a, **k):
            raise AssertionError("eth.contract touched before guard")

        def get_transaction_count(self, *a, **k):
            raise AssertionError("eth.get_transaction_count touched before guard")

    provider = _Provider()
    eth = _Eth()


class _ProviderWithEndpoint:
    """Fake provider exposing only provider.endpoint_uri (no eth), to exercise
    the L2-endpoint comparison without any network."""

    def __init__(self, uri):
        self.provider = type("P", (), {"endpoint_uri": uri})()


def test_hex_addr_fullmatch_rejects_trailing_newline_and_boundaries():
    addr_nl = "0x" + "a" * 40 + "\n"
    # fullmatch rejects the trailing newline; bare match() would accept it -
    # asserting both in one place documents WHY fullmatch is required.
    assert HEX_ADDR_RE.fullmatch(addr_nl) is None
    assert HEX_ADDR_RE.match(addr_nl)  # truthy
    with pytest.raises(ValidationError):
        ValueTransferModel(l1owner=addr_nl, to=GOOD, value=1)
    for bad in ["0x" + "a" * 41, "0x" + "a" * 39, "a" * 40, "0X" + "a" * 40, "0x" + "g" * 40, ""]:
        assert HEX_ADDR_RE.fullmatch(bad) is None


def test_withdraw_and_deposit_require_l1_wallet():
    # l2-only signer (no l1_wallet). D1 fixed: the guard raises ValueError (was
    # AttributeError) and does so before the provider is ever accessed.
    cfg = load_config(CONFIG_DIR)
    s = AlphasecSigner({"l1_address": GOOD, "l2_wallet": cfg["l2_wallet"], "network": "kairos"})
    with pytest.raises(ValueError, match="l1_wallet is not set"):
        s.generate_withdraw_transaction(_ProviderTouchRaises(), "1", 1.0)
    with pytest.raises(ValueError, match="l1_wallet is not set"):
        s.generate_deposit_transaction(_ProviderTouchRaises(), "1", 1.0)


def test_withdraw_rejects_non_l2_endpoint():
    # Signer WITH l1_wallet, network=kairos. A provider pointed at the wrong
    # endpoint must be rejected before building any tx.
    s = AlphasecSigner(load_config(CONFIG_DIR))
    with pytest.raises(ValueError, match="withdraw is only available for l2 provider"):
        s.generate_withdraw_transaction(_ProviderWithEndpoint("http://wrong"), "1", 1.0)


def test_deposit_erc20_rejects_invalid_token_address():
    # Non-native token + missing/invalid L1 address is rejected before any
    # contract call (the provider raises if touched).
    s = AlphasecSigner(load_config(CONFIG_DIR))
    with pytest.raises(ValueError, match="token_l1_address is invalid"):
        s.generate_deposit_transaction(_ProviderTouchRaises(), "2", 1.0, None, 6)
    with pytest.raises(ValueError, match="token_l1_address is invalid"):
        s.generate_deposit_transaction(_ProviderTouchRaises(), "2", 1.0, "not-an-address", 6)
