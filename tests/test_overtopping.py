"""Tests for overtopping case-study report helpers."""

import pandas as pd
import pytest
from ltp_fixtures import SAVE_POINT, monthly_avg, write_swl_workbook

from great_lakes import overtopping


def test_presentation_note_names_runup_allowance_only_when_added():
    assert overtopping.presentation_note(0.0).endswith("SWL excludes runup.")
    note = overtopping.presentation_note(2.0)
    assert note.endswith("SWL plus 2 ft runup allowance.")
    assert "excludes runup" not in note


@pytest.fixture
def inputs(tmp_path):
    csv = tmp_path / "michiganhuron_avg.csv"
    monthly_avg().to_csv(csv, index=False)
    write_swl_workbook(tmp_path / "michigan_swl.xlsx")
    return csv, tmp_path / "michigan_swl.xlsx"


def test_run_writes_the_full_memo_figure_set(inputs, tmp_path):
    csv, swl = inputs
    paths = overtopping.run(csv, swl, tmp_path / "out", save_point_id=SAVE_POINT)
    assert [p.name for p in paths] == list(overtopping.REPORT_OUTPUT_NAMES)
    assert all(p.exists() for p in paths)


def test_design_coverage_counts_scenarios_at_or_below_the_design_elevation(inputs, tmp_path):
    from great_lakes.scenario_grid import load_scenario_sheets
    sheets = load_scenario_sheets(inputs[1])
    thresholds = overtopping.write_design_coverage(
        sheets, tmp_path, save_point_id=SAVE_POINT, ari=10.0)
    assert len(thresholds) == 17
    frame = pd.read_csv(tmp_path / "T1_design_coverage.csv")
    assert len(frame) == len(overtopping.DESIGN_ELEVATIONS_FT) * len(
        overtopping.RUNUP_ALLOWANCES_FT) * 2
    row = frame.iloc[0]
    assert row["coverage_pct"] == 100 * row["coverage_count"] / row["scenario_count"]
