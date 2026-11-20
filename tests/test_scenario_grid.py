"""Tests for the scenario-grid helpers shared by the Long Tail Point figure sets."""
import pandas as pd
import pytest
from ltp_fixtures import SAVE_POINT, monthly_avg, scenario_sheets, write_swl_workbook

from great_lakes import scenario_grid as sg
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES


def test_scenario_status_classifies_all_17_scenarios():
    statuses = [sg.scenario_status(s) for s in ALL_SCENARIO_SUFFIXES]
    assert statuses.count("known") == 5
    assert statuses.count("interpolated") == 7
    assert statuses.count("extrapolated") == 5
    with pytest.raises(ValueError):
        sg.scenario_status("_1_1")


def test_scenario_means_has_every_scenario():
    means = sg.scenario_means(monthly_avg(years=2))
    assert set(means) == set(ALL_SCENARIO_SUFFIXES)


def test_load_scenario_sheets_reads_by_suffix(tmp_path):
    write_swl_workbook(tmp_path / "michigan_swl.xlsx")
    sheets = sg.load_scenario_sheets(tmp_path / "michigan_swl.xlsx")
    assert set(sheets) == set(ALL_SCENARIO_SUFFIXES)


def test_load_scenario_sheets_rejects_a_missing_scenario(tmp_path):
    path = tmp_path / "michigan_swl.xlsx"
    with pd.ExcelWriter(path) as writer:
        scenario_sheets()["_0_0"].to_excel(writer, sheet_name="michigan-_0_0", index=False)
    with pytest.raises(ValueError, match="17-scenario"):
        sg.load_scenario_sheets(path)


def test_scenario_level_ft_interpolates_the_ari_and_converts_to_ft_navd88():
    frame = scenario_sheets()["_0_0"]
    row = frame.loc[frame["ID"] == SAVE_POINT].iloc[0]
    # ARI 1 is a column, so no interpolation: m IGLD85 -> ft NAVD88.
    from great_lakes import units
    assert sg.scenario_level_ft(frame, SAVE_POINT, 1.0) == pytest.approx(
        units.m_igld85_to_ft_NAVD88(float(row[1])))
    with pytest.raises(ValueError, match="one row"):
        sg.scenario_level_ft(frame, 1, 1.0)


def test_save_grid_csv_places_values_by_precip_and_temp(tmp_path):
    out = tmp_path / "grid.csv"
    sg.save_grid_csv({"_0_0": 1.0, "_5_1.5": 2.0}, out, offset_ft=1.0)
    grid = pd.read_csv(out, index_col=0)
    assert grid.loc[0.0, "0.0"] == 2.0
    assert grid.loc[1.5, "5.0"] == 3.0
