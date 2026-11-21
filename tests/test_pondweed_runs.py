"""Tests for the pondweed habitat runs (floor-elevation sweep) behind the habitat memo.

Needs hydropattern >= 0.3 (scenarios module); skipped when the installed version is older.
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("hydropattern.scenarios")

SCRIPTS = Path(__file__).resolve().parents[1] / "case-studies/long-tail-point/habitat/scripts"
spec = importlib.util.spec_from_file_location("pondweed_runs", SCRIPTS / "pondweed_runs.py")
assert spec is not None and spec.loader is not None
pondweed_runs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pondweed_runs)


def test_annual_verdicts_fail_pass_and_unknown():
    index = pd.date_range("2000-01-01", periods=24, freq="MS")
    values = [1.0] * 24
    values[5] = 0.0  # a failed required month settles year 2000 as failed
    outcomes = pd.Series(values, index=index, name="x")

    annual = pondweed_runs.annual_verdicts(outcomes, (5, 6, 7, 8))

    assert annual.to_dict() == {2000: 0.0, 2001: 1.0}


def test_floor_574_baseline_matches_reviewed_notebook():
    summary = pondweed_runs.run_floor(574.0)

    base = summary.xs("_0_0", level="Scenario")
    assert base.loc["winter_survival", "Percentage"] == pytest.approx(100.0)
    assert base.loc["growing_season_habitat", "Percentage"] == pytest.approx(96.505, abs=1e-3)
    assert base.loc["growing_season_habitat", "Complete years"] == 1030


def test_lower_floor_is_never_better_for_winter_survival():
    deep = pondweed_runs.run_floor(571.0)
    shallow = pondweed_runs.run_floor(577.0)

    scenario = "_0_3"
    deep_pct = deep.loc[("winter_survival", scenario), "Percentage"]
    shallow_pct = shallow.loc[("winter_survival", scenario), "Percentage"]
    assert deep_pct >= shallow_pct
