"""Tests for the F3 Elevation Ladder data prep (habitat memo)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPORT_DIR = Path(__file__).resolve().parents[1] / "longtailpoint" / "habitat" / "report"
spec = importlib.util.spec_from_file_location("f3", REPORT_DIR / "figure_f3.py")
assert spec is not None and spec.loader is not None
f3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f3)


def test_level_bands_convert_m_to_ft_and_pool_scenarios():
    levels = pd.DataFrame({"_0_1.5": [0.3048, 0.6096], "_5_1.5": [0.9144, 1.2192]})
    bands = f3.level_bands_ft(levels, ["_0_1.5", "_5_1.5"])
    assert bands["median"] == pytest.approx(2.5)  # pooled 1,2,3,4 ft
    assert bands["mean"] == pytest.approx(2.5)
    assert bands["p10"] == pytest.approx(np.percentile([1, 2, 3, 4], 10))
    assert bands["p90"] == pytest.approx(np.percentile([1, 2, 3, 4], 90))


def test_each_column_is_a_single_scenario():
    assert all(len(s) == 1 for s in f3.SCENARIO_GROUPS.values())
    assert "_0_1.5" in sum(f3.SCENARIO_GROUPS.values(), []) and "_5_1.5" in sum(
        f3.SCENARIO_GROUPS.values(), []
    )


def test_columns_run_dry_to_wet_like_f5():
    codes = [s[0] for s in f3.SCENARIO_GROUPS.values()]
    assert codes == ["_0_3", "_0_1.5", "_0_0", "_5_1.5", "_15_3"]


def test_zone_elevations_are_level_minus_depth_range():
    zones = f3.zone_elevations(579.0)
    shallow_marsh = zones.set_index("zone").loc["Shallow marsh"]
    assert (shallow_marsh["low"], shallow_marsh["high"]) == (577.0, 578.5)  # depth 0.5-2 ft


def test_zone_elevations_exclude_unrooted_floating():
    assert "Unrooted floating" not in f3.zone_elevations(579.0)["zone"].tolist()


def test_save_point_elevations_drop_missing(tmp_path):
    path = tmp_path / "survey.xlsx"
    pd.DataFrame({"Estimated Bottom elevation (ft)": [575.5, None, 576.0]}).to_excel(
        path, sheet_name="depth_analysis", index=False
    )
    assert f3.save_point_elevations(path).tolist() == [575.5, 576.0]


def test_wd_floors_match_jenny_t8_and_plan_lwd():
    floors = f3.WD_FLOORS_FT
    assert min(floors.values()) == 575.01
    assert max(floors.values()) == 576.46
    assert f3.PLAN_LWD_FT == 576.15
