"""Tests for the Great Lakes common_twl.py shared helpers."""
import pytest
from matplotlib.colors import Normalize

from great_lakes import common_twl

# ---- m_igld85_to_ft_NAVD88 -------------------------------------------------------------

# Known conversion pairs from longtailpoint/longtail_waterlevel.xlsx Sheet2's "NAVD88
# to IGLD85" table: NAVD88 587ft -> IGLD85 586.56ft, NAVD88 582ft -> IGLD85 581.56ft --
# i.e. a flat -0.44ft offset (IGLD85_ft = NAVD88_ft - 0.44), the "USACE team estimate"
# noted in that workbook's conversion_ex sheet (not the slightly different computed
# ~0.4093ft offset, which the workbook explicitly says was not used).
# Meters here are exact (offset ft) / 3.281, not the workbook's own separately-sourced
# "Full Set of Elevations" ft->m column, which carries its own independent rounding
# noise (~0.01ft) from an external survey-based conversion, and not the exact 0.3048
# m/ft SI conversion either -- 1/3.281 matches how the longtailpoint resources sheets'
# magnitude_value column was actually populated, so this module's factor is kept
# consistent with that source data instead of the more "exact" SI figure.
@pytest.mark.parametrize("meters,expected_ft_NAVD88", [
    (586.56 / 3.281, 587.0),
    (581.56 / 3.281, 582.0),
])
def test_m_igld85_to_ft_NAVD88_known_pairs(meters, expected_ft_NAVD88):
    assert common_twl.m_igld85_to_ft_NAVD88(meters) == pytest.approx(expected_ft_NAVD88, abs=1e-6)


def test_m_igld85_to_ft_NAVD88_zero():
    # 0m IGLD85 -> 0ft IGLD85 -> +0.44ft NAVD88 (offset only, no scale error).
    assert common_twl.m_igld85_to_ft_NAVD88(0.0) == pytest.approx(0.44)


def test_m_igld85_to_ft_NAVD88_negative_value():
    assert common_twl.m_igld85_to_ft_NAVD88(-30.48) == pytest.approx(-99.56488)


def test_m_igld85_to_ft_NAVD88_round_trips_with_ft_NAVD88_to_m_igld85():
    original = 178.478688
    converted = common_twl.m_igld85_to_ft_NAVD88(original)
    assert common_twl.ft_NAVD88_to_m_igld85(converted) == pytest.approx(original)


def test_ft_NAVD88_to_m_igld85_known_value():
    # 586ft NAVD88 -> 585.56ft IGLD85 -> /3.281 -> 178.4699786650411m IGLD85.
    assert common_twl.ft_NAVD88_to_m_igld85(586.0) == pytest.approx(178.4699786650411)


# ---- resolve_lake_avg_path -----------------------------------------------------------


def test_resolve_lake_avg_path_michigan_and_huron_share_same_file(tmp_path):
    michigan_path = common_twl.resolve_lake_avg_path("michigan", tmp_path)
    huron_path = common_twl.resolve_lake_avg_path("huron", tmp_path)
    assert michigan_path == huron_path == tmp_path / "michiganhuron_avg.csv"


def test_resolve_lake_avg_path_superior(tmp_path):
    assert common_twl.resolve_lake_avg_path("superior", tmp_path) == tmp_path / "superior_avg.csv"


def test_resolve_lake_avg_path_ontario(tmp_path):
    assert common_twl.resolve_lake_avg_path("ontario", tmp_path) == tmp_path / "ontario_avg.csv"


# ---- read_avg_scenario_means ----------------------------------------------------------

# A tiny, hand-computable avg csv: 3 monthly rows, 2 scenario columns.
#   _0_0:  183.0, 183.2, 183.4  -> mean = 183.2
#   _0_7:  182.0, 182.5, 182.5  -> mean = 182.333...
_TINY_AVG_ROWS = (
    "time,_0_0,_0_7\n"
    "1970-01-01,183.0,182.0\n"
    "1970-02-01,183.2,182.5\n"
    "1970-03-01,183.4,182.5\n"
)


def _write_tiny_avg_csv(tmp_path, filename="superior_avg.csv"):
    path = tmp_path / filename
    path.write_text(_TINY_AVG_ROWS)
    return path


def test_read_avg_scenario_means_computes_mean_per_scenario_column(tmp_path):
    _write_tiny_avg_csv(tmp_path)
    means = common_twl.read_avg_scenario_means("superior", tmp_path)
    assert means["_0_0"] == pytest.approx(183.2)
    assert means["_0_7"] == pytest.approx(182.333333, rel=1e-6)


def test_read_avg_scenario_means_excludes_time_column(tmp_path):
    _write_tiny_avg_csv(tmp_path)
    means = common_twl.read_avg_scenario_means("superior", tmp_path)
    assert "time" not in means


def test_read_avg_scenario_means_michigan_and_huron_read_same_file(tmp_path):
    _write_tiny_avg_csv(tmp_path, filename="michiganhuron_avg.csv")
    michigan_means = common_twl.read_avg_scenario_means("michigan", tmp_path)
    huron_means = common_twl.read_avg_scenario_means("huron", tmp_path)
    assert michigan_means == huron_means == {"_0_0": pytest.approx(183.2),
                                              "_0_7": pytest.approx(182.333333, rel=1e-6)}


def test_read_avg_scenario_means_uses_full_record_not_a_subset(tmp_path):
    # 12 rows instead of 3 -- mean must reflect all of them, not e.g. just the first 3.
    rows = "time,_0_0\n" + "\n".join(f"1970-{m:02d}-01,{100.0 + m}" for m in range(1, 13)) + "\n"
    (tmp_path / "superior_avg.csv").write_text(rows)
    means = common_twl.read_avg_scenario_means("superior", tmp_path)
    expected = sum(100.0 + m for m in range(1, 13)) / 12
    assert means["_0_0"] == pytest.approx(expected)


# ---- RUNUP_FT_BY_COMPONENT / output_file_stem ------------------------------------------

# Per CONTEXT.md's "Runup allowance" definition: base=0ft, run2=2ft, run25=2.5ft, run3=3ft.


def test_runup_ft_by_component_known_values():
    assert common_twl.RUNUP_FT_BY_COMPONENT == {
        "base": 0.0, "run2": 2.0, "run25": 2.5, "run3": 3.0,
    }


@pytest.mark.parametrize("magnitude_ft,component_name,save_point_id,expected", [
    (586.47, "base", 1968, "586d47ft_plus0ft-runup_savepoint1968"),
    (586.47, "run2", 1968, "586d47ft_plus2ft-runup_savepoint1968"),
    (586.47, "run25", 1968, "586d47ft_plus2d5ft-runup_savepoint1968"),
    (586.47, "run3", 4997, "586d47ft_plus3ft-runup_savepoint4997"),
    # Whole-number elevation still shows exactly 2 decimals.
    (586.0, "base", 1968, "586d00ft_plus0ft-runup_savepoint1968"),
    # Trailing-zero-but-not-whole elevation decimal is kept (2 decimals always).
    (586.40, "base", 1968, "586d40ft_plus0ft-runup_savepoint1968"),
    # Negative elevation.
    (-1.25, "base", 1968, "-1d25ft_plus0ft-runup_savepoint1968"),
])
def test_output_file_stem_known_values(magnitude_ft, component_name, save_point_id, expected):
    assert common_twl.output_file_stem(magnitude_ft, component_name, save_point_id) == expected


def test_output_file_stem_rounds_elevation_to_two_decimals():
    stem = common_twl.output_file_stem(586.4749, "base", 1968)
    assert stem == "586d47ft_plus0ft-runup_savepoint1968"


def test_output_file_stem_unknown_component_name_raises():
    with pytest.raises(ValueError, match="run99"):
        common_twl.output_file_stem(586.47, "run99", 1968)


@pytest.mark.parametrize("magnitude_ft,component_name,save_point_id,expected", [
    # elevation = magnitude_ft + runup_ft (combined, "d" for decimal), then runup_ft
    # alone (also "d" for decimal) as its own separate token.
    (583.0, "base", 1968, "1968_583d00_0d00"),
    (583.0, "run2", 1968, "1968_585d00_2d00"),
    (583.0, "run25", 1968, "1968_585d50_2d50"),
    (583.0, "run3", 4997, "4997_586d00_3d00"),
    # Whole-number elevation/runup still show exactly 2 decimals.
    (586.0, "base", 1968, "1968_586d00_0d00"),
    # Negative elevation.
    (-1.25, "base", 1968, "1968_-1d25_0d00"),
])
def test_output_file_stem_savepoint_elevation_runup_known_values(
    magnitude_ft, component_name, save_point_id, expected
):
    stem = common_twl.output_file_stem_savepoint_elevation_runup(
        magnitude_ft, component_name, save_point_id
    )
    assert stem == expected


def test_output_file_stem_savepoint_elevation_runup_rounds_to_two_decimals():
    stem = common_twl.output_file_stem_savepoint_elevation_runup(583.0049, "run2", 1968)
    assert stem == "1968_585d00_2d00"


def test_output_file_stem_savepoint_elevation_runup_unknown_component_name_raises():
    with pytest.raises(ValueError, match="run99"):
        common_twl.output_file_stem_savepoint_elevation_runup(583.0, "run99", 1968)


# ---- build_plot_title -------------------------------------------------------------------

@pytest.mark.parametrize("plot_kind,expected_type_label", [
    ("primary", "Overtopping Frequency"),
    ("equivalent_elevation", "Elevation Equivalents"),
    ("elevation_delta", "Elevation Delta"),
])
def test_build_plot_title_maps_plot_kind_to_type_label(plot_kind, expected_type_label):
    title = common_twl.build_plot_title(
        plot_kind, magnitude_ft=583.0, component_name="run25", save_point_id=1968
    )
    assert expected_type_label in title
    assert "Longtail" in title and "Point" in title


def test_build_plot_title_elevation_is_magnitude_plus_runup():
    # magnitude_ft=583.0 + run25's 2.5ft runup -> elevation 585.5ft.
    title = common_twl.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="run25", save_point_id=1968
    )
    assert "585.5" in title or "585.50" in title


def test_build_plot_title_includes_runup_datum_and_save_point():
    title = common_twl.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="run25", save_point_id=1968
    )
    assert "NAVD88" in title
    assert "runup: 2.5 ft" in title
    assert "save point: 1968" in title


def test_build_plot_title_is_three_lines():
    title = common_twl.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="base", save_point_id=1968
    )
    assert title.count("\n") == 2


def test_build_plot_title_unknown_plot_kind_raises():
    with pytest.raises(ValueError, match="bogus_kind"):
        common_twl.build_plot_title(
            "bogus_kind", magnitude_ft=583.0, component_name="base", save_point_id=1968
        )


def test_build_plot_title_unknown_component_name_raises():
    with pytest.raises(ValueError, match="run99"):
        common_twl.build_plot_title(
            "primary", magnitude_ft=583.0, component_name="run99", save_point_id=1968
        )


# ---- one_sided_color_style --------------------------------------------------------------


def test_one_sided_color_style_threshold_inside_range_returns_none():
    assert common_twl.one_sided_color_style((10.0, 20.0), 15.0) is None


def test_one_sided_color_style_threshold_equal_to_range_edge_is_one_sided():
    # Not strictly inside (10, 20) -> one-sided, not the default two-sided case.
    assert common_twl.one_sided_color_style((10.0, 20.0), 10.0) is not None


def test_one_sided_color_style_all_below_threshold_uses_reds_r():
    style = common_twl.one_sided_color_style((5.0, 9.0), 10.0)
    color_map, norm, levels, widths = style
    assert color_map == "Reds_r"
    assert isinstance(norm, Normalize)
    assert norm.vmin == pytest.approx(5.0)
    assert norm.vmax == pytest.approx(10.0)
    assert levels[0] == pytest.approx(5.0)
    assert levels[-1] == pytest.approx(10.0)
    assert len(levels) == 7  # extreme + 5 mids + threshold
    assert widths[levels.index(10.0)] == 2.0


def test_one_sided_color_style_all_above_threshold_uses_blues():
    style = common_twl.one_sided_color_style((11.0, 15.0), 10.0)
    color_map, norm, levels, widths = style
    assert color_map == "Blues"
    assert norm.vmin == pytest.approx(10.0)
    assert norm.vmax == pytest.approx(15.0)
    assert levels[0] == pytest.approx(10.0)
    assert levels[-1] == pytest.approx(15.0)


# ---- rounded_levels ------------------------------------------------------------------


def test_rounded_levels_rounds_default_contour_levels_to_two_decimals():
    levels, widths = common_twl.rounded_levels((0.0, 6.0), 3.0)
    assert levels == tuple(round(lvl, 2) for lvl in levels)
    assert len(levels) == 11
    assert 3.0 in levels
    assert widths[levels.index(3.0)] == 2.0


def test_rounded_levels_custom_decimals():
    levels, _ = common_twl.rounded_levels((0.0, 1.0 / 3), 0.5, decimals=1)
    assert all(round(lvl, 1) == lvl for lvl in levels)


# ---- symmetric_delta_levels -----------------------------------------------------------


def test_symmetric_delta_levels_small_range_uses_tenth_ft_steps():
    levels, widths = common_twl.symmetric_delta_levels((-0.3, 0.4))
    assert levels == pytest.approx([-0.5, -0.4, -0.3, -0.2, -0.1, 0.0,
                                     0.1, 0.2, 0.3, 0.4, 0.5])
    assert widths[levels.index(0.0)] == 2.0


def test_symmetric_delta_levels_medium_range_uses_quarter_ft_steps():
    levels, widths = common_twl.symmetric_delta_levels((-0.9, 1.1))
    assert levels == pytest.approx([-1.25, -1.0, -0.75, -0.5, -0.25, 0.0,
                                     0.25, 0.5, 0.75, 1.0, 1.25])
    assert widths[levels.index(0.0)] == 2.0


def test_symmetric_delta_levels_large_range_escalates_level_count_keeping_quarter_step():
    levels, widths = common_twl.symmetric_delta_levels((-1.8, 1.3))
    assert levels[0] == pytest.approx(-2.0)
    assert levels[-1] == pytest.approx(2.0)
    step = round(levels[1] - levels[0], 10)
    assert step == pytest.approx(0.25)
    assert 0.0 in levels
    assert widths[levels.index(0.0)] == 2.0
    assert len(levels) > 11


def test_symmetric_delta_levels_always_centered_on_zero():
    levels, _ = common_twl.symmetric_delta_levels((-0.05, 0.45))
    assert 0.0 in levels
    mid = len(levels) // 2
    assert levels[mid] == pytest.approx(0.0)


# ---- naming_scheme_readme_text ---------------------------------------------------------

def test_naming_scheme_readme_text_savepoint_elevation_runup_mentions_pattern():
    text = common_twl.naming_scheme_readme_text("savepoint_elevation_runup")
    assert "<save point ID>_<elevation>_<runup>" in text
    assert "NAVD88" in text
    assert "feet" in text or "ft" in text
    assert "d" in text  # explains "d" used for decimal point


def test_naming_scheme_readme_text_elevation_runup_savepoint_mentions_pattern():
    text = common_twl.naming_scheme_readme_text("elevation_runup_savepoint")
    assert "ft_plus" in text
    assert "NAVD88" in text


def test_naming_scheme_readme_text_unknown_style_raises():
    with pytest.raises(ValueError, match="bogus_style"):
        common_twl.naming_scheme_readme_text("bogus_style")
