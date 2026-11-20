"""Tests for the F7/F8 cycle counting (habitat memo)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPORT_DIR = Path(__file__).resolve().parents[1] / "longtailpoint" / "habitat" / "report"
spec = importlib.util.spec_from_file_location("f8", REPORT_DIR / "figure_f8.py")
assert spec is not None and spec.loader is not None
f8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f8)


def _runs(*lengths: int) -> pd.Series:
    """Level 1 for each run length, separated by 12 months at level 0."""
    parts: list[np.ndarray] = [np.zeros(12)]
    for length in lengths:
        parts += [np.ones(length), np.zeros(12)]
    return pd.Series(np.concatenate(parts))


@pytest.mark.parametrize(
    ("min_months", "max_months", "expected"),
    [(24, None, 3), (36, None, 2), (24, 60, 2), (36, 60, 1)],
)
def test_events_are_whole_runs_within_duration_bounds(min_months, max_months, expected):
    series = _runs(24, 40, 61)
    count = f8.count_cycle_events(series, 1.0, None, 1, min_months, max_months)
    assert count == expected


def test_magnitude_band_and_trailing_mean_are_applied():
    # Trailing 1-month mean = the level itself; a 2.0 spike is outside the 0.5-1.5 band.
    series = pd.Series([0, 1, 1, 2, 1, 1, 0.0])
    assert f8.count_cycle_events(series, 0.5, 1.5, 1, 2, None) == 2
    assert f8.count_cycle_events(series, 0.5, None, 1, 2, None) == 1


def test_unavailable_first_months_do_not_count():
    series = pd.Series(np.ones(30))
    # 12-month trailing mean starts at month 12: 19 qualifying months < 24.
    assert f8.count_cycle_events(series, 0.5, None, 12, 24, None) == 0


def test_rate_is_events_per_100_years():
    series = _runs(24, 24)
    years = len(series) / 12
    assert f8.cycle_rate(series, 1.0, None, 1, 24, None) == pytest.approx(200 / years)


def test_scenario_grid_places_rates_by_precip_and_warming():
    rates = {"_0_0": 1.0, "_0_3": 2.0, "_15_3": 3.0}
    grid = f8.rate_grid(rates)
    assert grid.loc[3.0, 15.0] == 3.0
    assert grid.loc[0.0, 0.0] == 1.0
    assert np.isnan(grid.loc[0.0, 15.0])
