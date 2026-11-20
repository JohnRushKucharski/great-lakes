"""Tests for great_lakes.cleaning (raw workbooks -> data/avg and data/swl/clean)."""
import datetime

import pandas as pd
import pytest

from great_lakes.cleaning import avg as clean_avg
from great_lakes.cleaning import swl as clean_swl

# ---- cleaning.avg: LAKES / DATE_COLUMN ------------------------------------------

def test_lakes_maps_all_five_sheets_to_expected_avg_csv_names():
    assert clean_avg.LAKES == {
        "Superior": "superior_avg.csv",
        "MichiganHuron": "michiganhuron_avg.csv",
        "StClair": "stclair_avg.csv",
        "Erie": "erie_avg.csv",
        "Ontario": "ontario_avg.csv",
    }


# ---- clean_lake_levels_all_scenarios.py: clean_lake_frame --------------------------

def test_clean_lake_frame_drops_month_and_renames_date_column():
    raw = pd.DataFrame({
        "Unnamed: 0": [datetime.datetime(1970, 1, 1), datetime.datetime(1970, 2, 1)],
        "month": [1, 2],
        "_0_0": [183.43, 183.50],
        "_20_7": [182.10, 182.05],
    })

    cleaned = clean_avg.clean_lake_frame(raw)

    assert list(cleaned.columns) == ["time", "_0_0", "_20_7"]
    assert cleaned["time"].tolist() == ["1970-01-01", "1970-02-01"]
    # Scenario values pass through unchanged.
    assert cleaned["_0_0"].tolist() == [183.43, 183.50]
    assert cleaned["_20_7"].tolist() == [182.10, 182.05]


def test_clean_lake_frame_formats_dates_beyond_datetime64_range():
    # The real synthetic record runs 1970-2999, past pandas' nanosecond datetime64
    # ceiling (~2262) -- clean_lake_frame must format these directly rather than
    # round-tripping through pd.to_datetime, which would overflow/raise.
    raw = pd.DataFrame({
        "Unnamed: 0": [datetime.datetime(2999, 12, 1)],
        "month": [12],
        "_0_0": [180.0],
    })
    cleaned = clean_avg.clean_lake_frame(raw)
    assert cleaned["time"].tolist() == ["2999-12-01"]


# ---- clean_swl_summary.py: source_sheet_name -------------------------------

@pytest.mark.parametrize("scenario,lake_tag,expected", [
    ("baseline", "sup", "baseline (sup TWL BE)"),
    ("lowLL", "mich", "lowLL (mich TWL BE)"),
])
def test_source_sheet_name(scenario, lake_tag, expected):
    assert clean_swl.source_sheet_name(scenario, lake_tag) == expected


# ---- clean_swl_summary.py: SCENARIOS regression ----------------------------

def test_scenarios_mapping_matches_documented_precip_temp_deltas():
    # Regression guard: this module's own docstring/comment records that an earlier
    # version of this dict had the lowLL/highLL suffixes swapped, which silently
    # mislabeled every known-scenario sheet's precip/temp deltas. lowLL ("low lake
    # level") must map to the dry/hot _0_7 scenario; highLL ("high lake level") must
    # map to the wet _20_5 scenario.
    assert clean_swl.SCENARIOS == {
        "baseline": "baseline-_0_0",
        "modnear": "nearterm-_5_1.5",
        "modfuture_low": "moderate_low-_10_5",
        "lowLL": "extreme_low-_0_7",
        "highLL": "extreme_high-_20_5",
    }


def test_new_header_matches_ari_columns_plus_id_lat_lon():
    assert clean_swl.NEW_HEADER == [
        "ID", "lat", "lon", 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
    ]


# ---- clean_swl_summary.py: clean_scenario_frame ----------------------------

def test_clean_scenario_frame_drops_blank_id_rows_only():
    raw = pd.DataFrame({
        "ID": [1, None, 3],
        "lat": [46.0, 46.1, 46.2],
        "lon": [-84.0, -84.1, -84.2],
        1: [100.0, 101.0, 102.0],
    })

    cleaned = clean_swl.clean_scenario_frame(raw)

    assert cleaned["ID"].tolist() == [1, 3]
    assert cleaned[1].tolist() == [100.0, 102.0]


def test_clean_scenario_frame_keeps_all_rows_when_no_blank_ids():
    raw = pd.DataFrame({"ID": [1, 2, 3], "lat": [1.0, 2.0, 3.0], "lon": [1.0, 2.0, 3.0]})
    cleaned = clean_swl.clean_scenario_frame(raw)
    assert len(cleaned) == 3


def test_clean_scenario_frame_drops_save_points_without_any_water_level():
    raw = pd.DataFrame({
        "ID": [1, 2, 3],
        "lat": [46.0, 4.3, 46.2],
        "lon": [-84.0, -8.4, -84.2],
        1: [100.0, None, 102.0],
        10: [101.0, None, None],  # partial NaN is kept: it still has a water level
    })

    cleaned = clean_swl.clean_scenario_frame(raw)

    assert cleaned["ID"].tolist() == [1, 3]


def test_check_same_save_points_rejects_sheets_that_disagree():
    a = pd.DataFrame({"ID": [1, 2]})
    clean_swl.check_same_save_points("sup", {"x": a, "y": a.copy()})
    with pytest.raises(ValueError, match="sup"):
        clean_swl.check_same_save_points("sup", {"x": a, "y": pd.DataFrame({"ID": [1]})})


# ---- clean_workbook: raw workbook -> output files ----------------------------------

def _write_raw_avg(path):
    frame = pd.DataFrame({
        "month": [1, 2],
        "_0_0": [183.0, 183.5],
    }, index=[datetime.datetime(1970, 1, 1), datetime.datetime(1970, 2, 1)])
    with pd.ExcelWriter(path) as writer:
        for sheet in clean_avg.LAKES:
            frame.to_excel(writer, sheet_name=sheet)


def _write_raw_swl(path):
    rows = pd.DataFrame(
        [["hdr"] * 16, ["hdr"] * 16,
         [1, 46.0, -84.0] + [float(i) for i in range(13)],
         [None, None, None] + [0.0] * 13],
    )
    with pd.ExcelWriter(path) as writer:
        for tag in clean_swl.LAKES:
            for scenario in clean_swl.SCENARIOS:
                name = clean_swl.source_sheet_name(scenario, tag)
                rows.to_excel(writer, sheet_name=name, index=False, header=False)


def test_clean_avg_workbook_writes_one_csv_per_lake(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_raw_avg(raw / clean_avg.SOURCE_FILE)
    out = tmp_path / "avg"

    clean_avg.clean_workbook(raw, out)

    for filename in clean_avg.LAKES.values():
        frame = pd.read_csv(out / filename)
        assert list(frame.columns) == ["time", "_0_0"]
        assert frame["time"].tolist() == ["1970-01-01", "1970-02-01"]


def test_clean_swl_workbook_writes_one_workbook_per_lake_with_five_sheets(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_raw_swl(raw / clean_swl.SOURCE_FILE)
    out = tmp_path / "swl" / "clean"

    clean_swl.clean_workbook(raw, out)

    for filename in clean_swl.LAKES.values():
        sheets = pd.read_excel(out / filename, sheet_name=None)
        assert list(sheets) == list(clean_swl.SCENARIOS.values())
        assert sheets["baseline-_0_0"]["ID"].tolist() == [1]


@pytest.mark.parametrize("module,writer", [
    (clean_avg, _write_raw_avg), (clean_swl, _write_raw_swl),
])
def test_clean_workbook_refuses_to_overwrite_unless_asked(tmp_path, module, writer):
    raw = tmp_path / "raw"
    raw.mkdir()
    writer(raw / module.SOURCE_FILE)
    out = tmp_path / "out"
    module.clean_workbook(raw, out)

    with pytest.raises(FileExistsError):
        module.clean_workbook(raw, out)
    module.clean_workbook(raw, out, overwrite=True)
