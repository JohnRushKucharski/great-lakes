"""Tests for great_lakes.ari_constants."""
import pytest

from great_lakes import ari_constants


def test_swl_aris_matches_all_13_workbook_ari_columns():
    assert ari_constants.SWL_ARIS == (
        0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0,
    )


@pytest.mark.parametrize("ari,expected", [
    (0.1, "0.1"),
    (0.2, "0.2"),
    (1.0, "1"),
    (2.0, "2"),
    (1000.0, "1000"),
])
def test_format_ari_drops_superfluous_decimal_on_whole_numbers(ari, expected):
    assert ari_constants.format_ari(ari) == expected
