"""Tests for the Great Lakes raw-data cleaning scripts.

data/raw/clean_lake_levels_all_scenarios.py and clean_still_water_summary.py are
standalone scripts (data/raw/ has no __init__.py), so they're loaded here via
importlib by file path, same as the template-builder scripts.
"""
import datetime
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, RAW_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


clean_avg = _load("clean_lake_levels_all_scenarios", "clean_lake_levels_all_scenarios.py")
clean_twl = _load("clean_still_water_summary", "clean_still_water_summary.py")


# ---- clean_lake_levels_all_scenarios.py: LAKES / DATE_COLUMN -----------------------

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


# ---- clean_still_water_summary.py: source_sheet_name -------------------------------

@pytest.mark.parametrize("scenario,lake_tag,expected", [
    ("baseline", "sup", "baseline (sup TWL BE)"),
    ("lowLL", "mich", "lowLL (mich TWL BE)"),
])
def test_source_sheet_name(scenario, lake_tag, expected):
    assert clean_twl.source_sheet_name(scenario, lake_tag) == expected


# ---- clean_still_water_summary.py: SCENARIOS regression ----------------------------

def test_scenarios_mapping_matches_documented_precip_temp_deltas():
    # Regression guard: this module's own docstring/comment records that an earlier
    # version of this dict had the lowLL/highLL suffixes swapped, which silently
    # mislabeled every known-scenario sheet's precip/temp deltas. lowLL ("low lake
    # level") must map to the dry/hot _0_7 scenario; highLL ("high lake level") must
    # map to the wet _20_5 scenario.
    assert clean_twl.SCENARIOS == {
        "baseline": "baseline-_0_0",
        "modnear": "nearterm-_5_1.5",
        "modfuture_low": "moderate_low-_10_5",
        "lowLL": "extreme_low-_0_7",
        "highLL": "extreme_high-_20_5",
    }


def test_new_header_matches_ari_columns_plus_id_lat_lon():
    assert clean_twl.NEW_HEADER == [
        "ID", "lat", "lon", 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
    ]


# ---- clean_still_water_summary.py: clean_scenario_frame ----------------------------

def test_clean_scenario_frame_drops_blank_id_rows_only():
    raw = pd.DataFrame({
        "ID": [1, None, 3],
        "lat": [46.0, 46.1, 46.2],
        "lon": [-84.0, -84.1, -84.2],
        1: [100.0, 101.0, 102.0],
    })

    cleaned = clean_twl.clean_scenario_frame(raw)

    assert cleaned["ID"].tolist() == [1, 3]
    assert cleaned[1].tolist() == [100.0, 102.0]


def test_clean_scenario_frame_keeps_all_rows_when_no_blank_ids():
    raw = pd.DataFrame({"ID": [1, 2, 3], "lat": [1.0, 2.0, 3.0], "lon": [1.0, 2.0, 3.0]})
    cleaned = clean_twl.clean_scenario_frame(raw)
    assert len(cleaned) == 3
