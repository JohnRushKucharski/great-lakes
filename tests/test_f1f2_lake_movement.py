"""Tests for the merged F1/F2 figure (lake movement + warming plausibility) data prep."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

REPORT_DIR = Path(__file__).resolve().parents[1] / "longtailpoint" / "habitat" / "report"
spec = importlib.util.spec_from_file_location("f1f2", REPORT_DIR / "figure_f1f2.py")
assert spec is not None and spec.loader is not None
f1f2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f1f2)


@pytest.mark.parametrize(
    ("code", "expected"),
    [("_0_0", (0.0, 0.0)), ("_5_1.5", (5.0, 1.5)), ("_20_7", (20.0, 7.0))],
)
def test_parse_scenario_returns_precip_pct_and_warming(code, expected):
    assert f1f2.parse_scenario(code) == expected


def test_change_grid_is_level_minus_baseline_with_nan_for_missing_scenarios():
    levels = {"_0_0": 579.0, "_0_3": 576.0, "_15_3": 581.0}

    grid = f1f2.change_grid(levels)

    assert grid.loc[0.0, 0.0] == 0.0
    assert grid.loc[3.0, 0.0] == pytest.approx(-3.0)
    assert grid.loc[3.0, 15.0] == pytest.approx(2.0)
    assert np.isnan(grid.loc[7.0, 20.0])
    assert list(grid.index) == list(f1f2.WARMING_C)
    assert list(grid.columns) == list(f1f2.PRECIP_PCT)


def test_robust_set_is_the_six_scenarios():
    assert set(f1f2.ROBUST_SET) == {"_0_1.5", "_5_1.5", "_0_3", "_5_3", "_10_3", "_15_3"}
