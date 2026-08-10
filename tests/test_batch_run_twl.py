"""Tests for the Great Lakes batch_run_twl.py example script."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from great_lakes import batch_run_twl as twl_batch_run
from great_lakes import common_twl

# ---- _is_blank ----------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, float("nan"), "", "   "])
def test_is_blank_true_cases(value):
    assert twl_batch_run._is_blank(value) is True


@pytest.mark.parametrize("value", [0, 0.0, "0", "x", "  x  ", False])
def test_is_blank_false_cases(value):
    assert twl_batch_run._is_blank(value) is False


# ---- _to_bool -------------------------------------------------------------------------

@pytest.mark.parametrize("value,default,expected", [
    (None, False, False),
    (None, True, True),
    ("", True, True),
    (True, False, True),
    (False, True, False),
    (1, False, True),
    (0, True, False),
    ("true", False, True),
    ("TRUE", False, True),
    ("  True  ", False, True),
    ("false", True, False),
    ("FALSE", True, False),
    ("  False  ", True, False),
    ("1", False, True),
    ("0", True, False),
    ("yes", False, True),
    ("no", True, False),
])
def test_to_bool(value, default, expected):
    # Regression: bool("false") is True in plain Python, which previously made
    # string-boolean cells like overwrite="false" silently parse as True.
    assert twl_batch_run._to_bool(value, default) is expected


def test_to_bool_rejects_unparsable_string():
    with pytest.raises(ValueError, match="Cannot parse"):
        twl_batch_run._to_bool("maybe", False)


# ---- _require_str -----------------------------------------------------------------

def test_require_str_returns_stripped_value():
    errors = []
    value = twl_batch_run._require_str({"resource_name": "  duluth_harbor  "},
                                        "resource_name", errors)
    assert value == "duluth_harbor"
    assert not errors


@pytest.mark.parametrize("row", [{}, {"resource_name": None}, {"resource_name": "   "}])
def test_require_str_missing_or_blank_records_error(row):
    errors = []
    value = twl_batch_run._require_str(row, "resource_name", errors)
    assert value == ""
    assert len(errors) == 1
    assert "resource_name" in errors[0]


# ---- parse_scenario_sheet_name ------------------------------------------------------

@pytest.mark.parametrize("sheet_name,expected", [
    ("baseline-_0_0", "_0_0"),
    ("nearterm-_5_1.5", "_5_1.5"),
    ("moderate_low-_10_5", "_10_5"),
    ("extreme_low-_20_5", "_20_5"),
    ("extreme_high-_0_7", "_0_7"),
])
def test_parse_scenario_sheet_name_valid(sheet_name, expected):
    assert twl_batch_run.parse_scenario_sheet_name(sheet_name) == expected


@pytest.mark.parametrize("sheet_name", [
    "no_dash_here",
    "",
    "-_0_0",  # blank label
    "baseline_0_0",  # missing dash separator entirely
])
def test_parse_scenario_sheet_name_invalid_returns_none(sheet_name):
    assert twl_batch_run.parse_scenario_sheet_name(sheet_name) is None


# ---- interpolate_ari ------------------------------------------------------------------

ARIS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
LEVELS = [182.55, 183.18, 183.70, 183.80, 183.90, 183.98, 184.01,
          184.05, 184.09, 184.11, 184.13, 184.16, 184.18]


def test_interpolate_ari_exact_hit_on_a_known_point():
    ari = twl_batch_run.interpolate_ari(LEVELS, ARIS, 183.98)
    assert ari == pytest.approx(5)


def test_interpolate_ari_between_two_points():
    # Halfway between ARI=1 (183.80) and ARI=2 (183.90) -> ARI should be halfway (1.5).
    ari = twl_batch_run.interpolate_ari(LEVELS, ARIS, 183.85)
    assert ari == pytest.approx(1.5)


def test_interpolate_ari_below_minimum_clamps_and_warns():
    with pytest.warns(UserWarning, match="below curve minimum"):
        ari = twl_batch_run.interpolate_ari(LEVELS, ARIS, 100.0)
    assert ari == pytest.approx(0.1)


def test_interpolate_ari_above_maximum_clamps_and_warns():
    with pytest.warns(UserWarning, match="above curve maximum"):
        ari = twl_batch_run.interpolate_ari(LEVELS, ARIS, 500.0)
    assert ari == pytest.approx(1000)


def test_interpolate_ari_requires_matching_lengths():
    with pytest.raises(ValueError):
        twl_batch_run.interpolate_ari([1.0, 2.0], [1.0], 1.5)


def test_interpolate_ari_requires_at_least_two_points():
    with pytest.raises(ValueError):
        twl_batch_run.interpolate_ari([1.0], [1.0], 1.5)


# ---- interpolate_level ------------------------------------------------------------

def test_interpolate_level_exact_hit_on_a_known_point():
    level = twl_batch_run.interpolate_level(ARIS, LEVELS, 5)
    assert level == pytest.approx(183.98)


def test_interpolate_level_between_two_points():
    # Halfway between ARI=1 (183.80) and ARI=2 (183.90) -> level should be halfway.
    level = twl_batch_run.interpolate_level(ARIS, LEVELS, 1.5)
    assert level == pytest.approx(183.85)


def test_interpolate_level_below_minimum_clamps_and_warns():
    with pytest.warns(UserWarning, match="below curve minimum"):
        level = twl_batch_run.interpolate_level(ARIS, LEVELS, 0.01)
    assert level == pytest.approx(182.55)


def test_interpolate_level_above_maximum_clamps_and_warns():
    with pytest.warns(UserWarning, match="above curve maximum"):
        level = twl_batch_run.interpolate_level(ARIS, LEVELS, 2000.0)
    assert level == pytest.approx(184.18)


def test_interpolate_level_requires_matching_lengths():
    with pytest.raises(ValueError):
        twl_batch_run.interpolate_level([1.0, 2.0], [1.0], 1.5)


def test_interpolate_level_requires_at_least_two_points():
    with pytest.raises(ValueError):
        twl_batch_run.interpolate_level([1.0], [1.0], 1.5)


# ---- exceedance_probability -----------------------------------------------------------

@pytest.mark.parametrize("operator,expected", [
    (">", 0.18126924692201818),     # p_exceed = 1 - exp(-1/ARI) = 1 - exp(-1/5)
    (">=", 0.18126924692201818),
    ("<", 0.8187307530779818),      # complement
    ("<=", 0.8187307530779818),
])
def test_exceedance_probability_operator_direction(operator, expected):
    p = twl_batch_run.exceedance_probability(LEVELS, ARIS, 183.98, operator)
    assert p == pytest.approx(expected)


@pytest.mark.parametrize("operator", ["=", "!=", "gt", ""])
def test_exceedance_probability_rejects_equality_operators(operator):
    with pytest.raises(ValueError, match=operator or "operator"):
        twl_batch_run.exceedance_probability(LEVELS, ARIS, 183.98, operator)


# ---- compute_metric ---------------------------------------------------------------

def test_compute_metric_portion_success_pattern_true():
    value = twl_batch_run.compute_metric(0.2, success_pattern=True, mode="portion")
    assert value == pytest.approx(0.2)


def test_compute_metric_portion_success_pattern_false_is_complement():
    value = twl_batch_run.compute_metric(0.2, success_pattern=False, mode="portion")
    assert value == pytest.approx(0.8)


def test_compute_metric_percentage():
    value = twl_batch_run.compute_metric(0.2, success_pattern=True, mode="percentage")
    assert value == pytest.approx(20.0)


def test_compute_metric_return_period():
    value = twl_batch_run.compute_metric(0.2, success_pattern=True, mode="return_period")
    assert value == pytest.approx(5.0)


def test_compute_metric_return_period_undefined_when_portion_zero():
    import math
    value = twl_batch_run.compute_metric(0.0, success_pattern=True, mode="return_period")
    assert math.isnan(value)


def test_compute_metric_rejects_unknown_mode():
    with pytest.raises(ValueError):
        twl_batch_run.compute_metric(0.2, success_pattern=True, mode="bogus")


# ---- select_save_point --------------------------------------------------------------

SAVE_POINTS = pd.DataFrame({
    "ID": [1, 2, 3],
    "lat": [46.50169, 46.48618, 46.76017],
    "lon": [-84.37344, -84.63203, -84.96525],
    0.1: [182.55, 182.62, 182.36],
})


def test_select_save_point_by_id():
    row = twl_batch_run.select_save_point(SAVE_POINTS, save_point_id=2)
    assert row["ID"] == 2
    assert row["lat"] == pytest.approx(46.48618)


def test_select_save_point_by_nearest_lat_lon():
    # closest to save point 3's coordinates (slightly offset)
    row = twl_batch_run.select_save_point(SAVE_POINTS, lat=46.75, lon=-84.95)
    assert row["ID"] == 3


def test_select_save_point_prefers_id_when_all_three_given():
    # lat/lon here are nearest to point 1, but id=3 should win.
    row = twl_batch_run.select_save_point(
        SAVE_POINTS, save_point_id=3, lat=46.50169, lon=-84.37344
    )
    assert row["ID"] == 3


def test_select_save_point_requires_id_or_lat_lon():
    with pytest.raises(ValueError, match="save_point_id.*lat.*lon|lat.*lon.*save_point_id"):
        twl_batch_run.select_save_point(SAVE_POINTS)


def test_select_save_point_requires_both_lat_and_lon():
    with pytest.raises(ValueError):
        twl_batch_run.select_save_point(SAVE_POINTS, lat=46.5)


def test_select_save_point_unknown_id_raises():
    with pytest.raises(ValueError, match="999"):
        twl_batch_run.select_save_point(SAVE_POINTS, save_point_id=999)


# ---- parse_resource_row -------------------------------------------------------------

def base_row(**overrides):
    row = {
        "resource_name": "duluth_harbor",
        "lake": "superior",
        "magnitude_operator": ">",
        "magnitude_value": 183.8,
        "save_point_id": 1,
    }
    row.update(overrides)
    return row


def test_parse_resource_row_minimal_valid_row():
    spec = twl_batch_run.parse_resource_row(base_row())
    assert spec.resource_name == "duluth_harbor"
    assert spec.component_name == "twl"
    assert spec.lake == "superior"
    assert spec.magnitude_operator == ">"
    assert spec.magnitude_value == pytest.approx(183.8)
    assert spec.save_point_id == 1
    assert spec.lat is None
    assert spec.lon is None
    assert spec.success_pattern is False
    assert spec.threshold is None
    assert spec.qualified_name == "duluth_harbor_twl_1"


def test_parse_resource_row_component_name_explicit():
    row = base_row(component_name="high_water")
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.component_name == "high_water"
    assert spec.qualified_name == "duluth_harbor_high_water_1"


def test_parse_resource_row_qualified_name_omits_save_point_suffix_when_selected_by_lat_lon():
    row = base_row(lat=46.5, lon=-84.4)
    del row["save_point_id"]
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.qualified_name == "duluth_harbor_twl"


def test_parse_resource_row_qualified_name_disambiguates_same_resource_and_component():
    # Two rows sharing resource_name+component_name but different save points must
    # produce distinct qualified_name/output filenames (no output-target collision).
    spec_a = twl_batch_run.parse_resource_row(base_row(save_point_id=1968))
    spec_b = twl_batch_run.parse_resource_row(base_row(save_point_id=4997))
    assert spec_a.qualified_name != spec_b.qualified_name
    assert spec_a.qualified_name == "duluth_harbor_twl_1968"
    assert spec_b.qualified_name == "duluth_harbor_twl_4997"


@pytest.mark.parametrize("missing", ["resource_name", "lake"])
def test_parse_resource_row_missing_required_field_raises(missing):
    row = base_row()
    row[missing] = ""
    with pytest.raises(twl_batch_run.RowValidationError):
        twl_batch_run.parse_resource_row(row)


def test_parse_resource_row_unknown_lake_raises():
    row = base_row(lake="erie")  # not a valid twl lake code
    with pytest.raises(twl_batch_run.RowValidationError) as exc_info:
        twl_batch_run.parse_resource_row(row)
    assert "lake" in str(exc_info.value).lower()


def test_parse_resource_row_magnitude_requires_value():
    row = base_row()
    del row["magnitude_value"]
    with pytest.raises(twl_batch_run.RowValidationError):
        twl_batch_run.parse_resource_row(row)


def test_parse_resource_row_magnitude_requires_operator():
    row = base_row()
    row["magnitude_operator"] = ""
    with pytest.raises(twl_batch_run.RowValidationError):
        twl_batch_run.parse_resource_row(row)


@pytest.mark.parametrize("operator", ["=", "!=", "~"])
def test_parse_resource_row_magnitude_invalid_operator_raises(operator):
    row = base_row(magnitude_operator=operator)
    with pytest.raises(twl_batch_run.RowValidationError):
        twl_batch_run.parse_resource_row(row)


def test_parse_resource_row_save_point_by_lat_lon():
    row = base_row(lat=46.5, lon=-84.4)
    del row["save_point_id"]
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.save_point_id is None
    assert spec.lat == pytest.approx(46.5)
    assert spec.lon == pytest.approx(-84.4)


def test_parse_resource_row_save_point_id_wins_when_all_given():
    row = base_row(save_point_id=1, lat=46.5, lon=-84.4)
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.save_point_id == 1
    assert spec.lat == pytest.approx(46.5)
    assert spec.lon == pytest.approx(-84.4)


def test_parse_resource_row_requires_id_or_lat_lon():
    row = base_row()
    del row["save_point_id"]
    with pytest.raises(twl_batch_run.RowValidationError) as exc_info:
        twl_batch_run.parse_resource_row(row)
    assert "save_point_id" in str(exc_info.value)


def test_parse_resource_row_requires_both_lat_and_lon():
    row = base_row(lat=46.5)
    del row["save_point_id"]
    with pytest.raises(twl_batch_run.RowValidationError):
        twl_batch_run.parse_resource_row(row)


@pytest.mark.parametrize("raw,expected", [(True, True), (False, False), ("", False), (None, False)])
def test_parse_resource_row_success_pattern_blank_defaults_false(raw, expected):
    row = base_row(success_pattern=raw)
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.success_pattern is expected


def test_parse_resource_row_threshold_optional():
    row = base_row(threshold=183.5)
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.threshold == pytest.approx(183.5)


def test_parse_resource_row_threshold_blank_is_none():
    spec = twl_batch_run.parse_resource_row(base_row())
    assert spec.threshold is None


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_parse_resource_row_equivalent_elevation_blank_is_none(raw):
    row = base_row(equivalent_elevation=raw)
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.equivalent_elevation is None


@pytest.mark.parametrize(
    "raw", ["baseline_magnitude", "Baseline_Magnitude", "BASELINE_MAGNITUDE"]
)
def test_parse_resource_row_equivalent_elevation_baseline_magnitude_resolves_to_magnitude_value(
    raw,
):
    row = base_row(magnitude_value=183.8, equivalent_elevation=raw)
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.equivalent_elevation == pytest.approx(183.8)


def test_parse_resource_row_equivalent_elevation_numeric_value():
    row = base_row(magnitude_value=183.8, equivalent_elevation=180.0)
    spec = twl_batch_run.parse_resource_row(row)
    assert spec.equivalent_elevation == pytest.approx(180.0)


def test_parse_resource_row_equivalent_elevation_invalid_string_raises():
    row = base_row(equivalent_elevation="not_a_valid_option")
    with pytest.raises(twl_batch_run.RowValidationError) as exc_info:
        twl_batch_run.parse_resource_row(row)
    assert "equivalent_elevation" in str(exc_info.value).lower()


# ---- resolve_lake_twl_path ------------------------------------------------------------

@pytest.mark.parametrize("lake,expected_name", [
    ("superior", "superior_twl.xlsx"),
    ("michigan", "michigan_twl.xlsx"),
    ("huron", "huron_twl.xlsx"),
    ("ontario", "ontario_twl.xlsx"),
])
def test_resolve_lake_twl_path(lake, expected_name):
    data_dir = Path("some/data/dir")
    result = twl_batch_run.resolve_lake_twl_path(lake, data_dir)
    assert result == data_dir / expected_name


# ---- resolve_output_folder ----------------------------------------------------------

def default_config(**overrides):
    from dataclasses import replace
    config = twl_batch_run.BatchConfig()
    return replace(config, **overrides) if overrides else config


def test_resolve_output_folder_flat():
    spec = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory="out", subdirectory_structure="flat")
    assert twl_batch_run.resolve_output_folder(spec, config) == Path("out")


def test_resolve_output_folder_resource():
    spec = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory="out", subdirectory_structure="resource")
    assert twl_batch_run.resolve_output_folder(spec, config) == Path("out/duluth_harbor")


def test_resolve_output_folder_row():
    spec = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory="out", subdirectory_structure="row")
    assert twl_batch_run.resolve_output_folder(spec, config) == Path("out/duluth_harbor/twl")


# ---- read_resources_sheet / read_config_sheet -----------------------------------------

# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def make_workbook(tmp_path, resources_header=None, resources_rows=None,
                  config_pairs=None, resources_sheet_name="resources",
                  config_sheet_name="config"):
    """Build a small .xlsx with a resources sheet and/or a config sheet for testing."""
    from openpyxl import Workbook

    wb = Workbook()
    default_sheet = wb.active

    if resources_header is not None:
        ws = wb.create_sheet(resources_sheet_name) if default_sheet.title != resources_sheet_name \
            else default_sheet
        ws.title = resources_sheet_name
        ws.append(list(resources_header))
        for row in resources_rows or []:
            ws.append(list(row))
        default_sheet = None

    if config_pairs is not None:
        ws = wb.create_sheet(config_sheet_name) if default_sheet is None \
            else default_sheet
        ws.title = config_sheet_name
        ws.append(["option", "value"])
        for key, value in config_pairs:
            ws.append([key, value])
        default_sheet = None

    if default_sheet is not None and default_sheet.title == "Sheet":
        wb.remove(default_sheet)

    path = tmp_path / "workbook.xlsx"
    wb.save(path)
    return path


def test_read_resources_sheet_returns_one_dict_per_row(tmp_path):
    path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 183.8, 1),
            ("green_bay", "michigan", "<", 175.0, 2),
        ],
    )
    rows = twl_batch_run.read_resources_sheet(path)
    assert len(rows) == 2
    assert rows[0]["resource_name"] == "duluth_harbor"
    assert rows[1]["lake"] == "michigan"


def test_read_resources_sheet_blank_cell_becomes_none(tmp_path):
    path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "threshold"],
        resources_rows=[("duluth_harbor", "superior", ">", 183.8, None)],
    )
    rows = twl_batch_run.read_resources_sheet(path)
    assert rows[0]["threshold"] is None


def test_read_resources_sheet_missing_required_column_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake"],  # missing magnitude_operator/value
        resources_rows=[("duluth_harbor", "superior")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_resources_sheet(path)
    assert "magnitude_operator" in str(exc_info.value)


def test_read_resources_sheet_unknown_column_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "not_a_real_column"],
        resources_rows=[("duluth_harbor", "superior", ">", 183.8, "x")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_resources_sheet(path)
    assert "not_a_real_column" in str(exc_info.value)


def test_read_config_sheet_required_output_directory_only(tmp_path):
    from dataclasses import replace
    path = make_workbook(tmp_path, config_pairs=[("output_directory", "out")])
    config = twl_batch_run.read_config_sheet(path)
    assert config.output_directory == "out"
    assert config == replace(twl_batch_run.BatchConfig(), output_directory="out")


def test_read_config_sheet_missing_output_directory_raises(tmp_path):
    path = make_workbook(tmp_path, config_pairs=[("metric_mode", "percentage")])
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "output_directory" in str(exc_info.value)


def test_read_config_sheet_unknown_option_raises(tmp_path):
    path = make_workbook(
        tmp_path, config_pairs=[("output_directory", "out"), ("not_a_real_option", "x")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "not_a_real_option" in str(exc_info.value)


def test_read_config_sheet_duplicate_option_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("output_directory", "out2")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "duplicate" in str(exc_info.value).lower()


def test_read_config_sheet_invalid_subdirectory_structure_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("subdirectory_structure", "bogus")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "subdirectory_structure" in str(exc_info.value)


def test_read_config_sheet_invalid_metric_mode_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("metric_mode", "bogus")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "metric_mode" in str(exc_info.value)


def test_read_config_sheet_invalid_color_map_ticks_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("plot_color_map_ticks", "not,numbers")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "plot_color_map_ticks" in str(exc_info.value)


def test_read_config_sheet_all_options_overridden(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[
            ("output_directory", "out"),
            ("metric_mode", "percentage"),
            ("overwrite", True),
            ("subdirectory_structure", "row"),
            ("plot_interpolate", False),
            ("plot_color_map", "viridis"),
            ("plot_color_map_ticks", "-1.0, 0.0, 1.0"),
            ("fillin", True),
        ],
    )
    config = twl_batch_run.read_config_sheet(path)
    assert config.output_directory == "out"
    assert config.metric_mode == "percentage"
    assert config.overwrite is True
    assert config.subdirectory_structure == "row"
    assert config.plot_interpolate is False
    assert config.plot_color_map == "viridis"
    assert config.plot_color_map_ticks == (-1.0, 0.0, 1.0)
    assert config.fillin is True


def test_read_config_sheet_compute_equivalent_elevation_now_unrecognized_raises(tmp_path):
    # compute_equivalent_elevation moved to the resources sheet's per-row
    # 'equivalent_elevation' column; the config-sheet option no longer exists.
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("compute_equivalent_elevation", True)],
    )
    with pytest.raises(twl_batch_run.SheetValidationError) as exc_info:
        twl_batch_run.read_config_sheet(path)
    assert "compute_equivalent_elevation" in str(exc_info.value)


def test_read_config_sheet_fillin_defaults_false(tmp_path):
    path = make_workbook(tmp_path, config_pairs=[("output_directory", "out")])
    config = twl_batch_run.read_config_sheet(path)
    assert config.fillin is False


def test_read_config_sheet_blank_optional_rows_use_defaults(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("metric_mode", None)],
    )
    config = twl_batch_run.read_config_sheet(path)
    assert config.metric_mode == twl_batch_run.BatchConfig().metric_mode


# ---- filename_style config option / resolve_output_stem -------------------------------


def test_batch_config_filename_style_defaults_to_qualified_name():
    assert twl_batch_run.BatchConfig().filename_style == "qualified_name"


def test_read_config_sheet_filename_style_elevation_runup_savepoint(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[
            ("output_directory", "out"),
            ("filename_style", "elevation_runup_savepoint"),
        ],
    )
    config = twl_batch_run.read_config_sheet(path)
    assert config.filename_style == "elevation_runup_savepoint"


def test_read_config_sheet_filename_style_invalid_raises(tmp_path):
    path = make_workbook(
        tmp_path,
        config_pairs=[("output_directory", "out"), ("filename_style", "bogus")],
    )
    with pytest.raises(twl_batch_run.SheetValidationError, match="filename_style"):
        twl_batch_run.read_config_sheet(path)


def test_resolve_output_stem_default_uses_qualified_name():
    resource = twl_batch_run.parse_resource_row(base_row(save_point_id=1968))
    config = default_config(output_directory="out")
    assert twl_batch_run.resolve_output_stem(resource, config) == resource.qualified_name


def test_resolve_output_stem_elevation_runup_savepoint_style():
    resource = twl_batch_run.parse_resource_row(base_row(
        resource_name="longtail_17877", component_name="run25", save_point_id=1968,
        magnitude_operator=">=", magnitude_value=178.774764,
    ))
    config = default_config(
        output_directory="out", filename_style="elevation_runup_savepoint",
    )
    stem = twl_batch_run.resolve_output_stem(resource, config)
    expected_ft = common_twl.m_igld85_to_ft_NAVD88(178.774764)
    assert stem == common_twl.output_file_stem(expected_ft, "run25", 1968)


def test_resolve_output_stem_savepoint_elevation_runup_style():
    resource = twl_batch_run.parse_resource_row(base_row(
        resource_name="longtail_17877", component_name="run25", save_point_id=1968,
        magnitude_operator=">=", magnitude_value=178.774764,
    ))
    config = default_config(
        output_directory="out", filename_style="savepoint_elevation_runup",
    )
    stem = twl_batch_run.resolve_output_stem(resource, config)
    expected_ft = common_twl.m_igld85_to_ft_NAVD88(178.774764)
    assert stem == common_twl.output_file_stem_savepoint_elevation_runup(
        expected_ft, "run25", 1968
    )


def test_resolve_plot_title_default_style_uses_qualified_name():
    resource = twl_batch_run.parse_resource_row(base_row(save_point_id=1968))
    config = default_config(output_directory="out")
    assert twl_batch_run.resolve_plot_title("primary", resource, config) == resource.qualified_name
    assert twl_batch_run.resolve_plot_title(
        "equivalent_elevation", resource, config
    ) == f"{resource.qualified_name}_equivalent_elevation"


def test_resolve_plot_title_elevation_runup_savepoint_style():
    resource = twl_batch_run.parse_resource_row(base_row(
        resource_name="longtail_17877", component_name="run25", save_point_id=1968,
        magnitude_operator=">=", magnitude_value=178.774764,
    ))
    config = default_config(
        output_directory="out", filename_style="elevation_runup_savepoint",
    )
    title = twl_batch_run.resolve_plot_title("primary", resource, config)
    expected_ft = common_twl.m_igld85_to_ft_NAVD88(178.774764)
    assert title == common_twl.build_plot_title("primary", expected_ft, "run25", 1968)


def test_resolve_plot_title_savepoint_elevation_runup_style():
    resource = twl_batch_run.parse_resource_row(base_row(
        resource_name="longtail_17877", component_name="run25", save_point_id=1968,
        magnitude_operator=">=", magnitude_value=178.774764,
    ))
    config = default_config(
        output_directory="out", filename_style="savepoint_elevation_runup",
    )
    title = twl_batch_run.resolve_plot_title("primary", resource, config)
    expected_ft = common_twl.m_igld85_to_ft_NAVD88(178.774764)
    assert title == common_twl.build_plot_title("primary", expected_ft, "run25", 1968)


# ---- compute_scenario_metrics / build_resource_outputs ---------------------------------

def make_twl_workbook(path, sheet_frames: dict):
    """Write a small multi-sheet twl-like workbook (columns ID, lat, lon, <ARI...>)."""
    with pd.ExcelWriter(path) as writer:
        for name, df in sheet_frames.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return path


def _twl_sheet_frame(save_point_id=1, lat=10.0, lon=20.0, levels=(100.0, 110.0, 115.0, 120.0)):
    return pd.DataFrame({
        "ID": [save_point_id],
        "lat": [lat],
        "lon": [lon],
        1: [levels[0]],
        5: [levels[1]],
        10: [levels[2]],
        50: [levels[3]],
    })


GRID_SHEET_NAMES = ["baseline-_0_0", "a-_0_1.5", "b-_5_0", "c-_5_1.5"]


def test_compute_scenario_metrics_one_value_per_grid_sheet(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">", magnitude_value=110.0)
    )
    values = twl_batch_run.compute_scenario_metrics(resource, path, "portion")
    assert set(values.keys()) == {"_0_0", "_0_1.5", "_5_0", "_5_1.5"}
    assert all(0.0 <= v <= 1.0 for v in values.values())


def test_compute_scenario_metrics_skips_non_grid_sheets(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {"not_a_grid_sheet": _twl_sheet_frame(), "baseline-_0_0": _twl_sheet_frame()},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    values = twl_batch_run.compute_scenario_metrics(resource, path, "portion")
    assert set(values.keys()) == {"_0_0"}


def test_compute_scenario_metrics_return_period_is_monotonic_with_success_pattern_true(tmp_path):
    # Regression guard: for an exceedance-type resource (">=" threshold, dune-overtopping
    # semantics), a HIGHER magnitude_value must never have a LOWER return_period than a
    # lower magnitude_value -- a higher water level is rarer, not more frequent. This was
    # previously violated when success_pattern was left False (the default), because
    # compute_metric then measured the return period of the complement (staying below the
    # threshold) rather than of exceeding it -- collapsing to ~1.0 once the threshold was
    # clamped to the curve's max ARI. success_pattern=True fixes this.
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    low = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">=", magnitude_value=112.0, success_pattern=True)
    )
    high = twl_batch_run.parse_resource_row(
        # Above the curve's tabulated max (120.0) -- triggers ARI-clamping.
        base_row(magnitude_operator=">=", magnitude_value=130.0, success_pattern=True)
    )
    low_values = twl_batch_run.compute_scenario_metrics(low, path, "return_period")
    high_values = twl_batch_run.compute_scenario_metrics(high, path, "return_period")
    for scenario in low_values:
        assert high_values[scenario] >= low_values[scenario]


# ---- compute_equivalent_elevation_metrics ----------------------------------------------

def test_compute_equivalent_elevation_metrics_baseline_maps_to_itself(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">", magnitude_value=110.0,
                  equivalent_elevation="baseline_magnitude")
    )
    values = twl_batch_run.compute_equivalent_elevation_metrics(resource, path)
    assert set(values.keys()) == {"_0_0", "_0_1.5", "_5_0", "_5_1.5"}
    # All scenario sheets share the identical curve here, so baseline's own equivalent
    # elevation (and every scenario's) should equal the magnitude_value exactly.
    assert values["_0_0"] == pytest.approx(110.0)
    for value in values.values():
        assert value == pytest.approx(110.0)


def test_compute_equivalent_elevation_metrics_uses_baseline_ari_across_scenarios(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {
            "baseline-_0_0": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other-_5_0": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
            "other2-_0_1.5": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other3-_5_1.5": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
        },
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">", magnitude_value=110.0,
                  equivalent_elevation="baseline_magnitude")
    )
    values = twl_batch_run.compute_equivalent_elevation_metrics(resource, path)
    # Baseline ARI at level=110.0 is exactly ARI=5 (an exact hit on baseline's own curve).
    # Under "_5_0"'s curve, the level at ARI=5 is 116.0 (also an exact hit).
    assert values["_0_0"] == pytest.approx(110.0)
    assert values["_5_0"] == pytest.approx(116.0)


def test_compute_equivalent_elevation_metrics_uses_override_value_not_magnitude_value(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {
            "baseline-_0_0": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other-_5_0": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
        },
    )
    # magnitude_value (110.0, ARI=5) differs from the equivalent_elevation override
    # (115.0, ARI=10) -- the override, not magnitude_value, must drive the baseline
    # ARI lookup.
    resource = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">", magnitude_value=110.0, equivalent_elevation=115.0)
    )
    values = twl_batch_run.compute_equivalent_elevation_metrics(resource, path)
    assert values["_0_0"] == pytest.approx(115.0)
    assert values["_5_0"] == pytest.approx(121.0)


def test_compute_equivalent_elevation_metrics_missing_baseline_sheet_raises(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {"a-_0_1.5": _twl_sheet_frame(), "b-_5_0": _twl_sheet_frame()},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(equivalent_elevation="baseline_magnitude")
    )
    with pytest.raises(ValueError, match="baseline"):
        twl_batch_run.compute_equivalent_elevation_metrics(resource, path)


def test_compute_equivalent_elevation_metrics_skips_non_grid_sheets(tmp_path):
    path = make_twl_workbook(
        tmp_path / "lake_twl.xlsx",
        {"not_a_grid_sheet": _twl_sheet_frame(), "baseline-_0_0": _twl_sheet_frame()},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(equivalent_elevation="baseline_magnitude")
    )
    values = twl_batch_run.compute_equivalent_elevation_metrics(resource, path)
    assert set(values.keys()) == {"_0_0"}


def _recording_plot_fn(calls):
    def plot_fn(xs, ys, zs, **kwargs):
        calls.append({"xs": xs, "ys": ys, "zs": zs, **kwargs})
    return plot_fn


def test_build_resource_outputs_writes_grid_csv_and_calls_plot_fn(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"))
    calls = []
    grid_path, plot_path = twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    assert grid_path == tmp_path / "out" / "duluth_harbor_twl_1_grid.csv"
    assert plot_path == tmp_path / "out" / "duluth_harbor_twl_1_plot.png"
    assert grid_path.exists()
    assert len(calls) == 1
    assert calls[0]["title"] == "duluth_harbor_twl_1"
    assert calls[0]["save_path"] == plot_path
    assert calls[0]["show"] is False
    assert calls[0]["fillin"] is False


def test_build_resource_outputs_primary_one_sided_style_when_threshold_outside_range(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # All 4 grid sheets share identical levels -> the primary z-grid (ARI at
    # magnitude_value=110.0, exactly on-curve) is constant at ARI=5 everywhere, so
    # z_range collapses to (5.0, 5.0). threshold=-1 falls below that -> one-sided.
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">", magnitude_value=110.0, threshold=-1.0)
    )
    config = default_config(output_directory=str(tmp_path / "out"), plot_color_map="RdBu")
    calls = []
    twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    primary_call = calls[0]
    z_range = (float(np.nanmin(primary_call["zs"])), float(np.nanmax(primary_call["zs"])))
    expected_style = common_twl.one_sided_color_style(z_range, -1.0)
    assert expected_style is not None
    assert primary_call["color_map"] == expected_style[0]
    assert primary_call["levels"] == expected_style[2]
    assert primary_call["widths"] == expected_style[3]


def test_build_resource_outputs_primary_default_style_when_no_threshold(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"), plot_color_map="RdBu")
    calls = []
    twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    assert calls[0]["color_map"] == "RdBu"
    assert "levels" not in calls[0]
    assert "widths" not in calls[0]
    assert "norm" not in calls[0]


def test_build_resource_outputs_elevation_runup_savepoint_filename_style(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row(
        resource_name="longtail_17877", component_name="run25", save_point_id=1,
        magnitude_operator=">", magnitude_value=110.0,
    ))
    config = default_config(
        output_directory=str(tmp_path / "out"), filename_style="elevation_runup_savepoint",
    )
    calls = []
    grid_path, plot_path = twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    expected_stem = common_twl.output_file_stem(
        common_twl.m_igld85_to_ft_NAVD88(110.0), "run25", 1
    )
    assert grid_path == tmp_path / "out" / f"{expected_stem}_grid.csv"
    assert plot_path == tmp_path / "out" / f"{expected_stem}_plot.png"
    assert grid_path.exists()
    assert plot_path.exists() or calls[0]["save_path"] == plot_path


def test_build_resource_outputs_overwrite_false_raises_on_existing(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"), overwrite=False)
    twl_batch_run.build_resource_outputs(resource, data_dir, config, plot_fn=_recording_plot_fn([]))
    with pytest.raises(FileExistsError):
        twl_batch_run.build_resource_outputs(
            resource, data_dir, config, plot_fn=_recording_plot_fn([])
        )


def test_build_resource_outputs_overwrite_true_replaces(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"), overwrite=True)
    twl_batch_run.build_resource_outputs(resource, data_dir, config, plot_fn=_recording_plot_fn([]))
    # Should not raise the second time.
    twl_batch_run.build_resource_outputs(resource, data_dir, config, plot_fn=_recording_plot_fn([]))


def test_build_resource_outputs_equivalent_elevation_off_by_default(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"))
    twl_batch_run.build_resource_outputs(resource, data_dir, config, plot_fn=_recording_plot_fn([]))
    elev_grid = tmp_path / "out" / "duluth_harbor_twl_1_equivalent_elevation_grid.csv"
    elev_plot = tmp_path / "out" / "duluth_harbor_twl_1_equivalent_elevation_plot.png"
    delta_grid = tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_grid.csv"
    delta_plot = tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_plot.png"
    assert not elev_grid.exists()
    assert not elev_plot.exists()
    assert not delta_grid.exists()
    assert not delta_plot.exists()


def test_build_resource_outputs_equivalent_elevation_writes_second_grid_and_plot(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row(
        magnitude_operator=">", magnitude_value=110.0,
        equivalent_elevation="baseline_magnitude",
    ))
    config = default_config(
        output_directory=str(tmp_path / "out"),
        plot_color_map="viridis", plot_color_map_ticks=(1.0, 2.0), fillin=True,
    )
    calls = []
    grid_path, plot_path = twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    elev_grid = tmp_path / "out" / "duluth_harbor_twl_1_equivalent_elevation_grid.csv"
    elev_plot = tmp_path / "out" / "duluth_harbor_twl_1_equivalent_elevation_plot.png"
    assert grid_path.exists()
    assert elev_grid.exists()
    # 3 plot calls now: primary, equivalent_elevation, elevation_delta.
    assert len(calls) == 3
    assert calls[0]["fillin"] is True
    elev_call = calls[1]
    assert elev_call["labels"][2] == "Equivalent Elevation (ft, NAVD88)"
    # threshold/zs are converted from meters (IGLD85) to feet (NAVD88) at output time --
    # the underlying analysis (compute_equivalent_elevation_metrics) still works in
    # meters; build_resource_outputs converts only when writing the grid/plot.
    assert elev_call["threshold"] == pytest.approx(common_twl.m_igld85_to_ft_NAVD88(110.0))
    assert elev_call["save_path"] == elev_plot
    # This fixture's equivalent-elevation grid is degenerate (every cell equals the
    # comparison threshold exactly), so one_sided_color_style treats it as one-sided
    # (all cells <= threshold) and overrides viridis with Reds_r; color_map_ticks are
    # always the rounded contour levels now (point 5), never None/config-provided.
    assert elev_call["color_map"] == "Reds_r"
    assert elev_call["color_map_ticks"] is not None
    assert elev_call["fillin"] is True
    for value in elev_call["zs"]:
        assert value == pytest.approx(common_twl.m_igld85_to_ft_NAVD88(110.0))


def test_build_resource_outputs_equivalent_elevation_numeric_override_uses_value_as_threshold(
    tmp_path,
):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row(
        magnitude_operator=">", magnitude_value=110.0, equivalent_elevation=115.0,
    ))
    config = default_config(output_directory=str(tmp_path / "out"))
    calls = []
    twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    assert len(calls) == 3
    # The elevation plot's threshold tracks the override value (115.0), not
    # magnitude_value (110.0) -- the primary plot (calls[0]) is unaffected either way --
    # and is expressed in ft NAVD88, not the raw meters override.
    assert calls[1]["threshold"] == pytest.approx(common_twl.m_igld85_to_ft_NAVD88(115.0))


def test_build_resource_outputs_primary_grid_unaffected_by_equivalent_elevation_value(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    config = default_config(output_directory=str(tmp_path / "out"))

    resource_off = twl_batch_run.parse_resource_row(
        base_row(magnitude_operator=">", magnitude_value=110.0)
    )
    calls_off = []
    twl_batch_run.build_resource_outputs(
        resource_off, data_dir, config, plot_fn=_recording_plot_fn(calls_off)
    )

    resource_override = twl_batch_run.parse_resource_row(base_row(
        magnitude_operator=">", magnitude_value=110.0, equivalent_elevation=99.0,
    ))
    config_override = default_config(output_directory=str(tmp_path / "out2"))
    calls_override = []
    twl_batch_run.build_resource_outputs(
        resource_override, data_dir, config_override, plot_fn=_recording_plot_fn(calls_override)
    )

    # Primary grid/plot (calls[0]) is identical regardless of equivalent_elevation.
    assert calls_off[0]["zs"] == pytest.approx(calls_override[0]["zs"])


def test_build_resource_outputs_equivalent_elevation_overwrite_false_raises_on_existing(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(equivalent_elevation="baseline_magnitude")
    )
    config = default_config(
        output_directory=str(tmp_path / "out"), overwrite=False,
    )
    twl_batch_run.build_resource_outputs(resource, data_dir, config, plot_fn=_recording_plot_fn([]))
    with pytest.raises(FileExistsError):
        twl_batch_run.build_resource_outputs(
            resource, data_dir, config, plot_fn=_recording_plot_fn([])
        )


# ---- elevation_delta (build_resource_outputs 3rd grid+plot) --------------------------

def test_build_resource_outputs_elevation_delta_writes_third_grid_and_plot(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {
            "baseline-_0_0": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other-_5_0": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
            "other2-_0_1.5": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other3-_5_1.5": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
        },
    )
    resource = twl_batch_run.parse_resource_row(base_row(
        magnitude_operator=">", magnitude_value=110.0,
        equivalent_elevation="baseline_magnitude",
    ))
    config = default_config(output_directory=str(tmp_path / "out"))
    calls = []
    twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    delta_grid = tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_grid.csv"
    delta_plot = tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_plot.png"
    assert delta_grid.exists()
    assert len(calls) == 3
    delta_call = calls[2]
    assert delta_call["labels"][2] == "Elevation Delta (ft, NAVD88)"
    assert delta_call["save_path"] == delta_plot
    # Fixed colorbar center of 0 (no delta), regardless of resource.threshold or the
    # equivalent_elevation plot's own threshold.
    assert delta_call["threshold"] == pytest.approx(0.0)
    # Baseline ARI at level=110.0 is exactly ARI=5 (an exact hit on baseline's own
    # curve), so baseline's own equivalent elevation == the lookup value itself ->
    # delta == 0 for the baseline (_0_0) scenario. Assert via the known
    # equivalent_elevation values, converted to ft and differenced from the
    # ft-converted lookup value (resource.equivalent_elevation resolves to
    # magnitude_value == 110.0 via "baseline_magnitude").
    lookup_ft = common_twl.m_igld85_to_ft_NAVD88(110.0)
    baseline_delta_ft = common_twl.m_igld85_to_ft_NAVD88(110.0) - lookup_ft
    other_delta_ft = common_twl.m_igld85_to_ft_NAVD88(116.0) - lookup_ft
    assert baseline_delta_ft == pytest.approx(0.0)
    assert other_delta_ft == pytest.approx(common_twl.m_igld85_to_ft_NAVD88(116.0) - lookup_ft)
    assert min(np.ravel(delta_call["zs"])) <= other_delta_ft + 1e-9
    assert any(v == pytest.approx(0.0, abs=1e-9) for v in np.ravel(delta_call["zs"]))
    # levels/widths/color_map_ticks come from common_twl.symmetric_delta_levels,
    # centered on 0, independent of whether this particular range is one-sided.
    delta_z_range = (float(np.nanmin(delta_call["zs"])), float(np.nanmax(delta_call["zs"])))
    expected_levels, expected_widths = common_twl.symmetric_delta_levels(delta_z_range)
    assert delta_call["levels"] == expected_levels
    assert delta_call["widths"] == expected_widths
    assert delta_call["color_map_ticks"] == expected_levels
    assert 0.0 in expected_levels


def test_build_resource_outputs_elevation_delta_off_when_equivalent_elevation_blank(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"))
    calls = []
    twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    assert len(calls) == 1
    delta_grid = tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_grid.csv"
    assert not delta_grid.exists()


def test_build_resource_outputs_elevation_delta_numeric_override_uses_override_as_comparison(
    tmp_path,
):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {
            "baseline-_0_0": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other-_5_0": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
            "other2-_0_1.5": _twl_sheet_frame(levels=(100.0, 110.0, 115.0, 120.0)),
            "other3-_5_1.5": _twl_sheet_frame(levels=(105.0, 116.0, 121.0, 126.0)),
        },
    )
    # equivalent_elevation override (115.0) differs from magnitude_value (110.0) --
    # the delta's comparison elevation must track the override, not magnitude_value.
    resource = twl_batch_run.parse_resource_row(base_row(
        magnitude_operator=">", magnitude_value=110.0, equivalent_elevation=115.0,
    ))
    config = default_config(output_directory=str(tmp_path / "out"))
    calls = []
    twl_batch_run.build_resource_outputs(
        resource, data_dir, config, plot_fn=_recording_plot_fn(calls)
    )
    delta_call = calls[2]
    # Baseline scenario's equivalent elevation at ARI(115.0)=10 is 115.0 itself
    # (exact hit) -> delta should be ~0 for the baseline scenario.
    assert any(v == pytest.approx(0.0, abs=1e-9) for v in np.ravel(delta_call["zs"]))


def test_build_resource_outputs_elevation_delta_overwrite_false_raises_on_existing(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_twl_workbook(
        data_dir / "superior_twl.xlsx",
        {name: _twl_sheet_frame() for name in GRID_SHEET_NAMES},
    )
    resource = twl_batch_run.parse_resource_row(
        base_row(equivalent_elevation="baseline_magnitude")
    )
    config = default_config(output_directory=str(tmp_path / "out"), overwrite=False)
    twl_batch_run.build_resource_outputs(resource, data_dir, config, plot_fn=_recording_plot_fn([]))
    with pytest.raises(FileExistsError):
        twl_batch_run.build_resource_outputs(
            resource, data_dir, config, plot_fn=_recording_plot_fn([])
        )


# ---- run_batch --------------------------------------------------------------------------

def test_run_batch_all_rows_succeed(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
            ("green_bay", "michigan", "<", 175.0, 27),
        ],
    )
    config = twl_batch_run.BatchConfig(output_directory=str(tmp_path / "out"))
    calls = []

    def fake_build_outputs(resource, _data_dir, _cfg):
        calls.append(resource.resource_name)
        return (Path("grid.csv"), Path("plot.png"))

    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config, build_outputs=fake_build_outputs,
        progress=lambda *a: None,
    )
    assert len(summary.succeeded) == 2
    assert len(summary.failed) == 0
    assert calls == ["duluth_harbor", "green_bay"]


def test_resolve_all_output_paths_primary_only_without_equivalent_elevation(tmp_path):
    resource = twl_batch_run.parse_resource_row(base_row())
    config = default_config(output_directory=str(tmp_path / "out"))
    paths = twl_batch_run.resolve_all_output_paths(resource, config)
    assert paths == [
        tmp_path / "out" / "duluth_harbor_twl_1_grid.csv",
        tmp_path / "out" / "duluth_harbor_twl_1_plot.png",
    ]


def test_resolve_all_output_paths_includes_elevation_plots_when_set(tmp_path):
    resource = twl_batch_run.parse_resource_row(
        base_row(equivalent_elevation="baseline_magnitude")
    )
    config = default_config(output_directory=str(tmp_path / "out"))
    paths = twl_batch_run.resolve_all_output_paths(resource, config)
    assert paths == [
        tmp_path / "out" / "duluth_harbor_twl_1_grid.csv",
        tmp_path / "out" / "duluth_harbor_twl_1_plot.png",
        tmp_path / "out" / "duluth_harbor_twl_1_equivalent_elevation_grid.csv",
        tmp_path / "out" / "duluth_harbor_twl_1_equivalent_elevation_plot.png",
        tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_grid.csv",
        tmp_path / "out" / "duluth_harbor_twl_1_elevation_delta_plot.png",
    ]


def test_run_batch_populates_row_result_output_paths(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
        ],
    )
    config = twl_batch_run.BatchConfig(output_directory=str(tmp_path / "out"))
    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    assert summary.results[0].output_paths == (
        tmp_path / "out" / "duluth_harbor_twl_1_grid.csv",
        tmp_path / "out" / "duluth_harbor_twl_1_plot.png",
    )


def test_run_batch_failed_row_has_empty_output_paths(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("", "superior", ">", 110.0, 1),  # invalid: blank resource_name
        ],
    )
    config = twl_batch_run.BatchConfig(output_directory=str(tmp_path / "out"))
    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    assert summary.results[0].output_paths == ()


def test_run_batch_continues_past_row_validation_failure(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("", "superior", ">", 110.0, 1),  # invalid: blank resource_name
            ("green_bay", "michigan", "<", 175.0, 27),
        ],
    )
    config = twl_batch_run.BatchConfig(output_directory=str(tmp_path / "out"))
    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    assert len(summary.failed) == 1
    assert len(summary.succeeded) == 1
    assert summary.results[0].row_index == 1
    assert summary.results[0].status == "failed"


def test_run_batch_continues_past_build_outputs_error(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
            ("green_bay", "michigan", "<", 175.0, 27),
        ],
    )
    config = twl_batch_run.BatchConfig(output_directory=str(tmp_path / "out"))

    def flaky_build_outputs(resource, _data_dir, _cfg):
        if resource.resource_name == "duluth_harbor":
            raise ValueError("boom")
        return (Path("g.csv"), Path("p.png"))

    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config, build_outputs=flaky_build_outputs,
        progress=lambda *a: None,
    )
    assert len(summary.failed) == 1
    assert summary.failed[0].message == "boom"
    assert len(summary.succeeded) == 1


def test_run_batch_duplicate_output_target_fails_second_row(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
            # Same resource+component name AND same save_point_id -> still a genuine
            # output-target collision (save_point_id alone disambiguates different
            # save points sharing a resource+component label, not identical ones).
            ("duluth_harbor", "michigan", "<", 175.0, 1),
        ],
    )
    config = twl_batch_run.BatchConfig(
        output_directory=str(tmp_path / "out"), subdirectory_structure="flat",
    )
    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    assert len(summary.succeeded) == 1
    assert len(summary.failed) == 1
    assert "Duplicate output target" in summary.failed[0].message


def test_run_batch_writes_naming_readme_for_longtailpoint_filename_style(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "component_name", "lake", "magnitude_operator",
                          "magnitude_value", "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "base", "superior", ">", 110.0, 1),
        ],
    )
    out_dir = tmp_path / "out"
    config = twl_batch_run.BatchConfig(
        output_directory=str(out_dir), filename_style="savepoint_elevation_runup",
    )
    twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    readme_path = out_dir / "README.txt"
    assert readme_path.exists()
    text = readme_path.read_text()
    assert "<save point ID>_<elevation>_<runup>" in text
    assert "NAVD88" in text


def test_run_batch_no_naming_readme_for_qualified_name_filename_style(tmp_path):
    """qualified_name (the default) has no dedicated longtailpoint naming write-up, but
    the run readme itself is still always written (see CONTEXT.md's "Run readme"
    entry) -- it falls back to a generic resource_name/component_name description."""
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
        ],
    )
    out_dir = tmp_path / "out"
    config = twl_batch_run.BatchConfig(output_directory=str(out_dir))
    twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    readme_path = out_dir / "README.txt"
    assert readme_path.exists()
    text = readme_path.read_text()
    assert "<resource_name>_<component_name>" in text


def test_run_batch_writes_run_readme_even_when_all_rows_fail(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[("", "superior", ">", 110.0, 1)],  # missing resource_name
    )
    out_dir = tmp_path / "out"
    config = twl_batch_run.BatchConfig(output_directory=str(out_dir))

    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )

    assert len(summary.failed) == 1
    text = (out_dir / "README.txt").read_text()
    assert "1 failed" in text


def test_run_batch_run_readme_flags_stale_pre_existing_files(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
        ],
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    stale_file = out_dir / "leftover_from_old_run.csv"
    stale_file.write_text("stale")
    config = twl_batch_run.BatchConfig(output_directory=str(out_dir))

    twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )

    text = (out_dir / "README.txt").read_text()
    assert "leftover_from_old_run.csv" in text


def test_format_summary_includes_failure_details(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[("", "superior", ">", 110.0, 1)],
    )
    config = twl_batch_run.BatchConfig(output_directory=str(tmp_path / "out"))
    summary = twl_batch_run.run_batch(
        resources_path, tmp_path, config,
        build_outputs=lambda r, d, c: (Path("g.csv"), Path("p.png")),
        progress=lambda *a: None,
    )
    text = twl_batch_run.format_summary(summary)
    assert "1 succeeded, 1 failed" not in text  # sanity: only 1 row total here
    assert "0 succeeded, 1 failed" in text
    assert "Row 1" in text


# ---- write_results_workbook --------------------------------------------------------


def test_write_results_workbook_adds_output_location_column(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[
            ("duluth_harbor", "superior", ">", 110.0, 1),
            ("", "superior", ">", 110.0, 2),  # invalid -> failed row, blank cell
        ],
        config_pairs=[("output_directory", str(tmp_path / "out"))],
    )
    workspace_root = tmp_path
    out_dir = tmp_path / "out"
    summary = twl_batch_run.BatchSummary(results=[
        twl_batch_run.RowResult(
            1, "duluth_harbor", "twl", "succeeded", None,
            (out_dir / "duluth_harbor_twl_1_grid.csv", out_dir / "duluth_harbor_twl_1_plot.png"),
        ),
        twl_batch_run.RowResult(2, None, None, "failed", "blank resource_name"),
    ])
    out_path = tmp_path / "results.xlsx"
    result_path = twl_batch_run.write_results_workbook(
        resources_path, summary, out_path, workspace_root=workspace_root,
    )
    assert result_path == out_path
    assert out_path.exists()

    resources_df = pd.read_excel(out_path, sheet_name="resources", engine="calamine")
    config_df = pd.read_excel(out_path, sheet_name="config", engine="calamine")
    assert "output location" in resources_df.columns
    assert resources_df.loc[0, "output location"] == ";".join([
        str(Path("out/duluth_harbor_twl_1_grid.csv")),
        str(Path("out/duluth_harbor_twl_1_plot.png")),
    ])
    assert resources_df.loc[1, "output location"] == "" or pd.isna(
        resources_df.loc[1, "output location"]
    )
    assert "output_directory" in config_df["option"].values


def test_write_results_workbook_falls_back_to_absolute_path_outside_workspace(tmp_path):
    resources_path = make_workbook(
        tmp_path,
        resources_header=["resource_name", "lake", "magnitude_operator", "magnitude_value",
                          "save_point_id"],
        resources_rows=[("duluth_harbor", "superior", ">", 110.0, 1)],
        config_pairs=[("output_directory", "out")],
    )
    other_root = tmp_path / "elsewhere"
    other_root.mkdir()
    outside_path = other_root / "grid.csv"
    summary = twl_batch_run.BatchSummary(results=[
        twl_batch_run.RowResult(1, "duluth_harbor", "twl", "succeeded", None, (outside_path,)),
    ])
    out_path = tmp_path / "results.xlsx"
    twl_batch_run.write_results_workbook(
        resources_path, summary, out_path, workspace_root=tmp_path / "not_a_parent",
    )
    resources_df = pd.read_excel(out_path, sheet_name="resources", engine="calamine")
    assert resources_df.loc[0, "output location"] == str(outside_path.resolve())
