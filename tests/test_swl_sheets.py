"""Tests for great_lakes.swl.sheets: swl workbook sheet helpers."""
import numpy as np
import pandas as pd
import pytest

from great_lakes import units
from great_lakes.swl import sheets


@pytest.mark.parametrize("name,expected", [
    ("baseline-_0_0", "_0_0"),
    ("moderate_low-_10_5", "_10_5"),
    ("nearterm-_5_1.5", "_5_1.5"),
    ("nodash", None),
    ("-_0_0", None),
    ("label-", None),
])
def test_parse_scenario_sheet_name(name, expected):
    assert sheets.parse_scenario_sheet_name(name) == expected


def test_non_ari_columns():
    assert sheets.NON_ARI_COLUMNS == frozenset({"ID", "lat", "lon"})


def _ari_sheets() -> dict[str, pd.DataFrame]:
    baseline = pd.DataFrame({"ID": [1, 2], "lat": [44.0, 45.0], "lon": [-87.0, -86.0],
                              1: [100.0, 110.0]})
    other = pd.DataFrame({"ID": [1, 2], "lat": [44.0, 45.0], "lon": [-87.0, -86.0],
                           1: [101.0, 111.0]})
    return {"baseline-_0_0": baseline, "nearterm-_5_1.5": other}


def test_build_scenario_ari_grid_shapes_by_coords_and_converts_to_feet():
    coords = {"_0_0": (0.0, 0.0), "_5_1.5": (5.0, 1.5)}
    xs, ys, zs = sheets.build_scenario_ari_grid(coords, _ari_sheets(), save_point_id=1, ari=1)
    assert list(xs) == [0.0, 5.0]
    assert list(ys) == [0.0, 1.5]
    assert zs.shape == (2, 2)
    assert zs[0, 0] == pytest.approx(units.convert_units(100.0, "m", "ft"))
    assert zs[1, 1] == pytest.approx(units.convert_units(101.0, "m", "ft"))


def test_build_scenario_ari_grid_leaves_nan_for_coords_with_no_sheet():
    coords = {"_0_0": (0.0, 0.0), "_5_1.5": (5.0, 1.5), "_10_5": (10.0, 5.0)}
    xs, ys, zs = sheets.build_scenario_ari_grid(coords, _ari_sheets(), save_point_id=1, ari=1)
    assert np.isnan(zs[ys.tolist().index(5.0), xs.tolist().index(10.0)])


def test_build_scenario_ari_grid_ignores_sheets_not_in_coords():
    coords = {"_0_0": (0.0, 0.0)}
    xs, ys, zs = sheets.build_scenario_ari_grid(coords, _ari_sheets(), save_point_id=1, ari=1)
    assert xs.shape == (1,)
    assert ys.shape == (1,)
    assert zs.shape == (1, 1)
    assert zs[0, 0] == pytest.approx(units.convert_units(100.0, "m", "ft"))
