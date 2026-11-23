"""Tests for the F6 reliability heatmap data prep (habitat memo)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "case-studies/long-tail-point/habitat/scripts"
spec = importlib.util.spec_from_file_location("f6", SCRIPTS / "figure_reliability.py")
assert spec is not None and spec.loader is not None
f6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f6)


@pytest.mark.parametrize(
    ("pct", "expected"),
    [(75.0, "reliable"), (74.9, "marginal"), (50.0, "marginal"), (49.9, "unreliable")],
)
def test_reliability_class_standard_cuts(pct, expected):
    assert f6.reliability_class("juvenile_habitat", pct) == expected


@pytest.mark.parametrize(
    ("pct", "expected"),
    [(8.0, "reliable"), (7.9, "marginal"), (4.0, "marginal"), (3.9, "unreliable")],
)
def test_recruitment_uses_baseline_relative_cuts(pct, expected):
    assert f6.reliability_class("recruitment_zones", pct) == expected


def test_missing_value_has_no_class():
    assert f6.reliability_class("juvenile_habitat", np.nan) is None


def test_matrix_has_row_per_component_and_nan_outside_native_floor_range():
    musky = pd.DataFrame(
        {
            "Component": ["juvenile_habitat", "juvenile_habitat"],
            "Scenario": ["_0_0", "_0_0"],
            "Percentage": [100.0, 50.0],
            "Floor (ft IGLD85)": [573.0, 574.0],
        }
    )
    pond = pd.DataFrame(
        {
            "Component": ["winter_survival"],
            "Scenario": ["_0_0"],
            "Percentage": [90.0],
            "Floor (ft IGLD85)": [571.0],
        }
    )
    matrix = f6.scenario_matrix(pd.concat([musky, pond]), "_0_0")
    assert list(matrix.index) == [key for key, _ in f6.ROWS]
    assert list(matrix.columns) == list(f6.FLOORS_FT)
    assert matrix.loc["juvenile_habitat", 574.0] == 50.0
    assert np.isnan(matrix.loc["juvenile_habitat", 571.0])  # musky not run at 571
    assert matrix.loc["winter_survival", 571.0] == 90.0
