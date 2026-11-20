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

# NAVD88_ft = IGLD85_ft + 0.44: the USACE team estimate, not the computed ~0.4093 ft (see
# longtailpoint/longtail_waterlevel.xlsx, Sheet2 "NAVD88 to IGLD85").
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
        return value / METERS_PER_FOOT
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
    """Convert an elevation in meters, IGLD85, to feet, NAVD88 (units and datum)."""
    return convert_datum(convert_units(value_m_igld85, "m", "ft"), "IGLD85", "NAVD88", "ft")


def ft_NAVD88_to_m_igld85(value_ft_NAVD88: _Num) -> _Num:
    """Inverse of `m_igld85_to_ft_NAVD88`."""
    return convert_units(convert_datum(value_ft_NAVD88, "NAVD88", "IGLD85", "ft"), "ft", "m")


def water_level_label(units: Units, datum: Datum, quantity: str = "Water level") -> str:
    """Axis/column label that always states both units and datum."""
    return f"{quantity} ({units}, {datum})"
