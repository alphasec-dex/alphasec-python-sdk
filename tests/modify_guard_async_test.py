import pytest
from alphasec.api.async_api import AsyncAPI


class _Signer:
    # Reaches the price/qty handling so the test exercises the modify None
    # guard itself, not the upstream `signer is None` ValueError.
    l1_address = "0xabc"
    def create_modify_data(self, *a, **k): return b"data"
    def generate_alphasec_transaction(self, *a, **k): return "0xtx"


def _api():
    api = AsyncAPI("http://example.invalid")
    api._initialized = True
    api.signer = _Signer()
    return api


async def test_modify_none_price_raises_valueerror():
    # match= asserts the explicit None guard fired, not the coincidental
    # "Price must be positive" that the old `or 0.0` trick produced.
    with pytest.raises(ValueError, match="required"):
        await _api().modify("oid", new_price=None, new_qty=5.0, order_mode=0)


async def test_modify_none_qty_raises_valueerror():
    with pytest.raises(ValueError, match="required"):
        await _api().modify("oid", new_price=5.0, new_qty=None, order_mode=0)
