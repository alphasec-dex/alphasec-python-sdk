import pytest
from decimal import Decimal
from alphasec.transaction.sign import perp_scale


@pytest.mark.parametrize("bad", ["", "abc", None, "nan", "inf", "-inf"])
def test_perp_scale_rejects_nonnumeric(bad):
    with pytest.raises((ValueError, TypeError)):
        perp_scale(bad)


def test_perp_scale_valid_unchanged():
    assert perp_scale(Decimal("1.5")) == 1_500_000_000_000_000_000
    assert perp_scale("0") == 0
