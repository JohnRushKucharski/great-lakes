"""Tests for the musky habitat runs (floor-elevation sweep) behind the habitat memo.

Needs hydropattern >= 0.3 (scenarios module); skipped when the installed version is older.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("hydropattern.scenarios")

SCRIPTS = Path(__file__).resolve().parents[1] / "case-studies/long-tail-point/habitat/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("musky_runs", SCRIPTS / "musky_runs.py")
assert spec is not None and spec.loader is not None
musky_runs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(musky_runs)


def test_window_verdicts_need_three_of_five_and_skip_partial_windows():
    annual = pd.Series([1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0], index=range(2000, 2007))
    verdicts = musky_runs.window_verdicts(annual)
    assert verdicts.to_dict() == {2000: 1.0, 2001: 0.0, 2002: 0.0}  # 3 full windows only


def test_run_floor_matches_reviewed_notebook_baseline():
    # musky_matrix.ipynb baseline table at 576 ft: juvenile 99.2, spawning 91.4, recruitment 3.6
    result = musky_runs.run_floor(576.0)
    baseline = result.xs("_0_0", level="Scenario")["Percentage"]
    assert baseline["juvenile_habitat"] == pytest.approx(99.2, abs=0.05)
    assert baseline["spawning_zones"] == pytest.approx(91.4, abs=0.05)
    assert baseline["recruitment_zones"] == pytest.approx(3.6, abs=0.05)
