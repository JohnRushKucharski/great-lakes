"""Unit (m <-> ft) and vertical-datum (IGLD85 <-> NAVD88) conversion.

The two are independent steps: convert units only, datum only, or both. Source data is
meters, IGLD85. Helpers that apply both are named for it (`m_igld85_to_ft_NAVD88`).
"""

from typing import Literal, TypeVar

import numpy as np

Units = Literal["m", "ft"]
Datum = Literal["IGLD85", "NAVD88"]

_Num = TypeVar("_Num", float, np.ndarray)

# International foot, exact by definition.
METERS_PER_FOOT = 0.3048

# Scale used only by the combined m_igld85 <-> ft_NAVD88 helpers: the long-tail-point
# worksheets' magnitude_value was populated with 1 m = 3.281 ft, not the exact foot.
# Differs by ~1.5e-5 per ft (a few hundredths of a ft at these elevations); keep distinct
# from `convert_units`, which is exact.
CASE_STUDY_METERS_PER_FOOT = 1.0 / 3.281

# NAVD88_ft = IGLD85_ft + 0.44: the USACE team estimate, not the computed ~0.4093 ft (see
# Sheet2 "NAVD88 to IGLD85" of the long-tail-point overtopping inputs/longtail_waterlevel.xlsx).
IGLD85_TO_NAVD88_OFFSET_FT = 0.44

_UNITS = ("m", "ft")
_DATUMS = ("IGLD85", "NAVD88")


def _check(value: str, allowed: tuple[str, ...], kind: str) -> None:
    if value not in allowed:
        raise ValueError(f"Unknown {kind} {value!r}; expected one of {list(allowed)}.")


def convert_units(value: _Num, from_units: Units, to_units: Units) -> _Num:
    """Convert a length (or a difference between lengths) between meters and feet."""
    _check(from_units, _UNITS, "units")
    _check(to_units, _UNITS, "units")
    if from_units == to_units:
        return value
    if from_units == "m":
        return value * (1.0 / METERS_PER_FOOT)
    return value * METERS_PER_FOOT


def convert_datum(value: _Num, from_datum: Datum, to_datum: Datum, units: Units) -> _Num:
    """Shift an elevation between IGLD85 and NAVD88. `units` are those of `value`
    (the offset is applied in them); the units themselves are not changed.
    """
    _check(from_datum, _DATUMS, "datum")
    _check(to_datum, _DATUMS, "datum")
    if from_datum == to_datum:
        return value
    offset = convert_units(IGLD85_TO_NAVD88_OFFSET_FT, "ft", units)
    return value + offset if to_datum == "NAVD88" else value - offset


def m_igld85_to_ft_NAVD88(value_m_igld85: _Num) -> _Num:
    """Convert an elevation in meters, IGLD85, to feet, NAVD88 (units and datum).

    Uses the case-study scale (1 m = 3.281 ft), not the exact foot, so results match
    how the worksheets' magnitude_value column was populated and the original outputs.
    """
    return value_m_igld85 / CASE_STUDY_METERS_PER_FOOT + IGLD85_TO_NAVD88_OFFSET_FT


def m_delta_to_ft(delta_m: _Num) -> _Num:
    """Convert a difference of IGLD85 levels in meters to feet (case-study scale, no datum)."""
    return m_igld85_to_ft_NAVD88(delta_m) - m_igld85_to_ft_NAVD88(0.0)


def ft_NAVD88_to_m_igld85(value_ft_NAVD88: _Num) -> _Num:
    """Inverse of `m_igld85_to_ft_NAVD88`."""
    return (value_ft_NAVD88 - IGLD85_TO_NAVD88_OFFSET_FT) * CASE_STUDY_METERS_PER_FOOT


def water_level_label(units: Units, datum: Datum, quantity: str = "Water level") -> str:
    """Axis/column label that always states both units and datum."""
    return f"{quantity} ({units}, {datum})"
