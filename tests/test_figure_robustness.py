"""Tests for the F9 robustness chart data prep (habitat memo)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "case-studies/long-tail-point/habitat/scripts"
spec = importlib.util.spec_from_file_location("f9", SCRIPTS / "figure_robustness.py")
assert spec is not None and spec.loader is not None
f9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f9)

ALL = ["_0_0", "_0_1.5", "_5_1.5", "_0_3", "_5_3", "_10_3", "_15_3",
       "_0_5", "_5_5", "_10_5", "_15_5", "_20_5"]


def pcts(good: list[str], value_good: float = 90.0, value_bad: float = 10.0) -> dict[str, float]:
    return {s: (value_good if s in good else value_bad) for s in ALL}


BOTH_15 = ["_0_1.5", "_5_1.5"]
ALL_3C = ["_0_3", "_5_3", "_10_3", "_15_3"]


@pytest.mark.parametrize(
    ("good", "expected"),
    [
        (["_0_0"], "baseline only"),
        (["_0_0", "_5_1.5"], "baseline + one 1.5C"),
        (["_0_0", "_5_1.5", "_10_3", "_15_3"], "baseline + one 1.5C"),
        (["_0_0", *BOTH_15], "1.5C"),
        (["_0_0", *BOTH_15, "_0_3"], "1.5C + part of 3C"),
        (["_0_0", *BOTH_15, *ALL_3C[:3]], "1.5C + part of 3C"),
        (["_0_0", *BOTH_15, *ALL_3C], "3C"),
        (ALL, "3C"),
    ],
)
def test_tier_for_floors_reliable_at_baseline(good, expected):
    assert f9.floor_tier("juvenile_habitat", pcts(good)) == expected


@pytest.mark.parametrize(
    ("good", "expected"),
    [
        ([], "never reliable"),
        (["_0_3"], "lower lake only"),
        (["_0_1.5", "_0_3"], "lower lake only"),
        (["_0_1.5", "_5_3"], "lower lake only"),  # 3C/5 is neutral
        (["_15_3"], "higher lake only"),
        (["_5_1.5", "_15_3"], "higher lake only"),
    ],
)
def test_floors_failing_baseline_are_classed_by_direction(good, expected):
    assert f9.floor_tier("spawning_zones", pcts(good)) == expected


def test_recruitment_uses_its_own_cut():
    low = {s: 9.0 for s in ALL}
    assert f9.floor_tier("recruitment_zones", low) == "3C"
    assert f9.floor_tier("juvenile_habitat", low) == "never reliable"


def test_missing_baseline_value_is_not_run():
    values = pcts(ALL)
    values["_0_0"] = np.nan
    assert f9.floor_tier("juvenile_habitat", values) is None


def test_aim_tier_is_weakest_component_and_none_if_any_not_run():
    assert f9.aim_tier(["3C", "1.5C"]) == "1.5C"
    assert f9.aim_tier(["3C", "never reliable"]) == "never reliable"
    assert f9.aim_tier(["3C", None]) is None


def test_tier_table_has_component_rows_and_floor_columns():
    rows = []
    for floor in (573.0, 574.0):
        for scenario in ALL:
            rows.append(("juvenile_habitat", scenario, 100.0, floor))
    results = pd.DataFrame(
        rows, columns=["Component", "Scenario", "Percentage", "Floor (ft IGLD85)"]
    )
    table = f9.tier_table(results)
    assert list(table.columns) == list(f9.FLOORS_FT)
    assert table.loc["juvenile_habitat", 573.0] == "3C"
    assert pd.isna(table.loc["juvenile_habitat", 571.0])
    assert pd.isna(table.loc["spawning_zones", 573.0])
