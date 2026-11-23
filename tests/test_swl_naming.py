"""Tests for great_lakes.swl.naming: runup allowances, output filename stems, plot titles."""
import pytest

from great_lakes.swl import naming

# Per GLOSSARY.md's "Runup allowance" definition: base=0ft, run2=2ft, run25=2.5ft, run3=3ft.


def test_runup_ft_by_component_known_values():
    assert naming.RUNUP_FT_BY_COMPONENT == {
        "base": 0.0, "run2": 2.0, "run25": 2.5, "run3": 3.0,
    }


@pytest.mark.parametrize("magnitude_ft,component_name,save_point_id,expected", [
    (586.47, "base", 1968, "586d47ft_plus0ft-runup_savepoint1968"),
    (586.47, "run2", 1968, "586d47ft_plus2ft-runup_savepoint1968"),
    (586.47, "run25", 1968, "586d47ft_plus2d5ft-runup_savepoint1968"),
    (586.47, "run3", 4997, "586d47ft_plus3ft-runup_savepoint4997"),
    # Whole-number elevation still shows exactly 2 decimals.
    (586.0, "base", 1968, "586d00ft_plus0ft-runup_savepoint1968"),
    (586.40, "base", 1968, "586d40ft_plus0ft-runup_savepoint1968"),
    (-1.25, "base", 1968, "-1d25ft_plus0ft-runup_savepoint1968"),
])
def test_output_file_stem_known_values(magnitude_ft, component_name, save_point_id, expected):
    assert naming.output_file_stem(magnitude_ft, component_name, save_point_id) == expected


def test_output_file_stem_rounds_elevation_to_two_decimals():
    stem = naming.output_file_stem(586.4749, "base", 1968)
    assert stem == "586d47ft_plus0ft-runup_savepoint1968"


def test_output_file_stem_unknown_component_name_raises():
    with pytest.raises(ValueError, match="run99"):
        naming.output_file_stem(586.47, "run99", 1968)


@pytest.mark.parametrize("magnitude_ft,component_name,save_point_id,expected", [
    # elevation = magnitude_ft + runup_ft (combined), then runup_ft alone.
    (583.0, "base", 1968, "1968_583d00_0d00"),
    (583.0, "run2", 1968, "1968_585d00_2d00"),
    (583.0, "run25", 1968, "1968_585d50_2d50"),
    (583.0, "run3", 4997, "4997_586d00_3d00"),
    (586.0, "base", 1968, "1968_586d00_0d00"),
    (-1.25, "base", 1968, "1968_-1d25_0d00"),
])
def test_output_file_stem_savepoint_elevation_runup_known_values(
    magnitude_ft, component_name, save_point_id, expected
):
    stem = naming.output_file_stem_savepoint_elevation_runup(
        magnitude_ft, component_name, save_point_id
    )
    assert stem == expected


def test_output_file_stem_savepoint_elevation_runup_rounds_to_two_decimals():
    stem = naming.output_file_stem_savepoint_elevation_runup(583.0049, "run2", 1968)
    assert stem == "1968_585d00_2d00"


def test_output_file_stem_savepoint_elevation_runup_unknown_component_name_raises():
    with pytest.raises(ValueError, match="run99"):
        naming.output_file_stem_savepoint_elevation_runup(583.0, "run99", 1968)


# ---- build_plot_title -------------------------------------------------------------------

@pytest.mark.parametrize("plot_kind,expected_type_label", [
    ("primary", "Overtopping Frequency"),
    ("equivalent_elevation", "Elevation Equivalents"),
    ("elevation_delta", "Elevation Delta"),
])
def test_build_plot_title_maps_plot_kind_to_type_label(plot_kind, expected_type_label):
    title = naming.build_plot_title(
        plot_kind, magnitude_ft=583.0, component_name="run25", save_point_id=1968
    )
    assert expected_type_label in title
    assert "Longtail" in title and "Point" in title


def test_build_plot_title_elevation_is_magnitude_plus_runup():
    title = naming.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="run25", save_point_id=1968
    )
    assert "585.5" in title or "585.50" in title


def test_build_plot_title_includes_runup_datum_and_save_point():
    title = naming.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="run25", save_point_id=1968
    )
    assert "NAVD88" in title
    assert "runup: 2.5 ft" in title
    assert "save point: 1968" in title


def test_build_plot_title_is_three_lines():
    title = naming.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="base", save_point_id=1968
    )
    assert title.count("\n") == 2


def test_build_plot_title_unknown_plot_kind_raises():
    with pytest.raises(ValueError, match="bogus_kind"):
        naming.build_plot_title(
            "bogus_kind", magnitude_ft=583.0, component_name="base", save_point_id=1968
        )


def test_build_plot_title_unknown_component_name_raises():
    with pytest.raises(ValueError, match="run99"):
        naming.build_plot_title(
            "primary", magnitude_ft=583.0, component_name="run99", save_point_id=1968
        )


def test_build_plot_title_equivalent_elevation_adds_baseline_ari_as_fourth_line():
    title = naming.build_plot_title(
        "equivalent_elevation", magnitude_ft=583.0, component_name="run25",
        save_point_id=1968, baseline_ari=12.4,
    )
    assert title.count("\n") == 3
    lines = title.split("\n")
    assert lines[2] == "baseline ARI: 12.4 yr"
    assert lines[3] == "save point: 1968"


def test_build_plot_title_elevation_delta_adds_baseline_ari_as_fourth_line():
    title = naming.build_plot_title(
        "elevation_delta", magnitude_ft=583.0, component_name="run25",
        save_point_id=1968, baseline_ari=0.5,
    )
    assert title.count("\n") == 3
    lines = title.split("\n")
    assert lines[2] == "baseline ARI: 0.5 yr"
    assert lines[3] == "save point: 1968"


def test_build_plot_title_primary_ignores_baseline_ari_kwarg():
    title = naming.build_plot_title(
        "primary", magnitude_ft=583.0, component_name="run25", save_point_id=1968,
        baseline_ari=12.4,
    )
    assert title.count("\n") == 2
    assert "baseline ARI" not in title


# ---- build_threshold_ari_title -----------------------------------------------------------

def test_build_threshold_ari_title_is_three_lines():
    title = naming.build_threshold_ari_title(threshold_ari=15.0, save_point_id=1968)
    assert title.count("\n") == 2
    lines = title.split("\n")
    assert lines[0] == "Longtail Point Threshold ARI Elevation"
    assert lines[1] == "ARI: 15 yr"
    assert lines[2] == "save point: 1968"


def test_build_threshold_ari_title_formats_non_integer_ari():
    title = naming.build_threshold_ari_title(threshold_ari=12.5, save_point_id=4997)
    assert "ARI: 12.5 yr" in title
    assert "save point: 4997" in title


# ---- naming_scheme_readme_text ---------------------------------------------------------

def test_naming_scheme_readme_text_savepoint_elevation_runup_mentions_pattern():
    text = naming.naming_scheme_readme_text("savepoint_elevation_runup")
    assert "<save point ID>_<elevation>_<runup>" in text
    assert "NAVD88" in text
    assert "feet" in text or "ft" in text
    assert "d" in text  # explains "d" used for decimal point


def test_naming_scheme_readme_text_elevation_runup_savepoint_mentions_pattern():
    text = naming.naming_scheme_readme_text("elevation_runup_savepoint")
    assert "ft_plus" in text
    assert "NAVD88" in text


def test_naming_scheme_readme_text_unknown_style_raises():
    with pytest.raises(ValueError, match="bogus_style"):
        naming.naming_scheme_readme_text("bogus_style")
