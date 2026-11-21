"""Tests for the F5 WD structure scorecard data prep (habitat memo)."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "case-studies/long-tail-point/habitat/scripts"
spec = importlib.util.spec_from_file_location("f5", SCRIPTS / "figure_wd_scorecard.py")
assert spec is not None and spec.loader is not None
f5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f5)


def test_depth_is_may_aug_median_level_minus_floor_in_ft():
    levels = pd.DataFrame(
        {"s": [100.0, 0.3048, 0.6096, 0.9144, 1.2192, 100.0]},
        index=["2000-04-01", "2000-05-01", "2000-06-01", "2000-07-01", "2000-08-01", "2000-09-01"],
    )
    # May-Aug levels 1,2,3,4 ft -> median 2.5 ft
    assert f5.median_depth_ft(levels, "s", floor_ft=1.0) == pytest.approx(1.5)


@pytest.mark.parametrize(
    "depth, expected",
    [
        (0.5, "too shallow"),
        (0.98, "spawning + recruitment"),
        (1.5, "spawning + recruitment"),
        (3.0, "spawning only"),
        (4.92, "spawning only"),
        (5.5, "too deep"),
    ],
)
def test_depth_class_follows_jenny_t7_ranges(depth, expected):
    assert f5.depth_class(depth) == expected


def test_scenarios_match_f3_columns_and_all_six_structure_ends_scored():
    assert list(f5.SCENARIOS.values()) == ["_0_3", "_0_1.5", "_0_0", "_5_1.5", "_15_3"]
    assert list(f5.WD_FLOORS_FT) == ["1w", "1e", "2w", "2e", "3w", "3e"]


def test_scorecard_has_one_row_per_structure_end_and_column_per_scenario():
    idx = [f"2000-{m:02d}-01" for m in range(1, 13)]
    levels = pd.DataFrame({code: [175.0] * 12 for code in f5.SCENARIOS.values()}, index=idx)
    card = f5.scorecard(levels)
    assert list(card.index) == list(f5.WD_FLOORS_FT)
    assert list(card.columns) == list(f5.SCENARIOS)
