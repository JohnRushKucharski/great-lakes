"""Tests for great_lakes.units: unit (m/ft) and datum (IGLD85/NAVD88) conversion."""
import numpy as np
import pytest

from great_lakes import units


def test_convert_units_uses_international_foot():
    assert units.convert_units(0.3048, "m", "ft") == pytest.approx(1.0, abs=1e-12)
    assert units.convert_units(1.0, "ft", "m") == pytest.approx(0.3048, abs=1e-12)


def test_convert_units_same_units_is_identity():
    assert units.convert_units(12.5, "m", "m") == 12.5
    assert units.convert_units(12.5, "ft", "ft") == 12.5


@pytest.mark.parametrize("value", [-30.48, 0.0, 1.0, 178.478688])
def test_convert_units_round_trips(value):
    there = units.convert_units(value, "m", "ft")
    assert units.convert_units(there, "ft", "m") == pytest.approx(value, abs=1e-12)


def test_convert_units_accepts_arrays():
    result = units.convert_units(np.array([0.3048, 0.6096]), "m", "ft")
    assert result == pytest.approx(np.array([1.0, 2.0]))


def test_convert_units_unknown_units_raises():
    with pytest.raises(ValueError, match="yards"):
        units.convert_units(1.0, "m", "yards")  # type: ignore[arg-type]


# Datum offset: NAVD88_ft = IGLD85_ft + 0.44 (USACE team estimate; see
# longtailpoint/longtail_waterlevel.xlsx Sheet2: NAVD88 587 ft -> IGLD85 586.56 ft).
def test_convert_datum_known_pairs_in_feet():
    assert units.convert_datum(586.56, "IGLD85", "NAVD88", "ft") == pytest.approx(587.0)
    assert units.convert_datum(582.0, "NAVD88", "IGLD85", "ft") == pytest.approx(581.56)


def test_convert_datum_offset_is_scaled_for_meters():
    # 0.44 ft expressed in meters, so a 0 m IGLD85 value is 0.44 ft above in NAVD88.
    assert units.convert_datum(0.0, "IGLD85", "NAVD88", "m") == pytest.approx(0.44 * 0.3048)


def test_convert_datum_same_datum_is_identity():
    assert units.convert_datum(100.0, "NAVD88", "NAVD88", "ft") == 100.0


def test_convert_datum_changes_only_the_datum_not_the_units():
    # The offset is a pure shift: differences between two levels are preserved.
    a = units.convert_datum(10.0, "IGLD85", "NAVD88", "ft")
    b = units.convert_datum(12.0, "IGLD85", "NAVD88", "ft")
    assert b - a == pytest.approx(2.0)


def test_convert_datum_unknown_datum_raises():
    with pytest.raises(ValueError, match="NGVD29"):
        units.convert_datum(1.0, "IGLD85", "NGVD29", "ft")  # type: ignore[arg-type]


def test_m_igld85_to_ft_navd88_known_pairs():
    assert units.m_igld85_to_ft_NAVD88(586.56 * 0.3048) == pytest.approx(587.0, abs=1e-9)
    assert units.m_igld85_to_ft_NAVD88(581.56 * 0.3048) == pytest.approx(582.0, abs=1e-9)


def test_m_igld85_to_ft_navd88_zero_is_offset_only():
    assert units.m_igld85_to_ft_NAVD88(0.0) == pytest.approx(0.44)


@pytest.mark.parametrize("value_m", [-30.48, 0.0, 178.478688])
def test_m_igld85_to_ft_navd88_round_trips(value_m):
    ft = units.m_igld85_to_ft_NAVD88(value_m)
    assert units.ft_NAVD88_to_m_igld85(ft) == pytest.approx(value_m, abs=1e-12)


def test_water_level_label_states_units_and_datum():
    assert units.water_level_label("ft", "NAVD88") == "Water level (ft, NAVD88)"
    assert units.water_level_label("m", "IGLD85") == "Water level (m, IGLD85)"


def test_water_level_label_accepts_custom_quantity():
    assert units.water_level_label("ft", "NAVD88", "Elevation Delta") == (
        "Elevation Delta (ft, NAVD88)"
    )
