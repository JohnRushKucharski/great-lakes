"""Tests for the Great Lakes fillin_twl.py example script."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from great_lakes import fillin_twl

# ---- resolve_default_output_dir ----------------------------------------------------

def test_resolve_default_output_dir_extrapolate_true_uses_extrapolated_sibling():
    data_dir = Path("data/clean")
    result = fillin_twl.resolve_default_output_dir(data_dir, extrapolate=True)
    assert result == Path("data/extrapolated")


def test_resolve_default_output_dir_extrapolate_false_uses_filled_sibling():
    data_dir = Path("data/clean")
    result = fillin_twl.resolve_default_output_dir(data_dir, extrapolate=False)
    assert result == Path("data/filled")


# ---- known_scenario_coords --------------------------------------------------------

# The 5 known-scenario sheet names actually present in every data/clean/<lake>_twl.xlsx
# workbook, and their expected (precip_delta, temp_delta) coordinates.
REAL_KNOWN_SHEET_NAMES = [
    "baseline-_0_0",
    "nearterm-_5_1.5",
    "moderate_low-_10_5",
    "extreme_low-_20_5",
    "extreme_high-_0_7",
]
REAL_KNOWN_COORDS = {
    "_0_0": (0.0, 0.0),
    "_5_1.5": (5.0, 1.5),
    "_10_5": (10.0, 5.0),
    "_20_5": (20.0, 5.0),
    "_0_7": (0.0, 7.0),
}


def test_known_scenario_coords_parses_real_sheet_names():
    result = fillin_twl.known_scenario_coords(REAL_KNOWN_SHEET_NAMES)
    assert result == REAL_KNOWN_COORDS


def test_known_scenario_coords_skips_non_matching_sheet_names():
    names = REAL_KNOWN_SHEET_NAMES + ["not_a_grid_sheet", "-_0_0", "baseline_0_0"]
    result = fillin_twl.known_scenario_coords(names)
    assert result == REAL_KNOWN_COORDS


def test_known_scenario_coords_empty_input_returns_empty_dict():
    assert not fillin_twl.known_scenario_coords([])


# ---- classify_target_scenarios -----------------------------------------------------

# The exact in-hull/out-of-hull split for the real 5 known-scenario coordinates,
# verified against scipy.spatial.Delaunay directly during design (see plan.md).
REAL_IN_HULL = {"_0_1.5", "_0_3", "_0_5", "_5_3", "_5_5", "_10_3", "_15_5"}
REAL_OUT_OF_HULL = {"_5_7", "_10_7", "_15_3", "_15_7", "_20_7"}


def test_classify_target_scenarios_real_known_coords():
    classification = fillin_twl.classify_target_scenarios(REAL_KNOWN_COORDS)
    assert set(classification.in_hull) == REAL_IN_HULL
    assert set(classification.out_of_hull) == REAL_OUT_OF_HULL


def test_classify_target_scenarios_excludes_known_scenarios_from_both_lists():
    classification = fillin_twl.classify_target_scenarios(REAL_KNOWN_COORDS)
    all_classified = set(classification.in_hull) | set(classification.out_of_hull)
    assert all_classified.isdisjoint(REAL_KNOWN_COORDS.keys())


def test_classify_target_scenarios_in_hull_plus_out_of_hull_covers_all_targets():
    classification = fillin_twl.classify_target_scenarios(REAL_KNOWN_COORDS)
    all_classified = set(classification.in_hull) | set(classification.out_of_hull)
    all_targets = set(fillin_twl.ALL_SCENARIO_SUFFIXES) - set(REAL_KNOWN_COORDS.keys())
    assert all_classified == all_targets


# ---- build_barycentric_weights ------------------------------------------------------

# A simple, hand-computable right triangle -- NOT the real Great Lakes hull -- so the
# interpolated values below can be verified by hand.
#
#   C=(0,10), value 130
#   |\
#   | \
#   |  \
#   A---B    A=(0,0), value 100   B=(10,0), value 110
#
# Because A/B/C are axis-aligned, the plane through the 3 known values is exactly:
#   z(x, y) = 100 + (110-100)*(x/10) + (130-100)*(y/10) = 100 + x + 3y
SIMPLE_TRIANGLE_COORDS = {"_0_0": (0.0, 0.0), "_10_0": (10.0, 0.0), "_0_10": (0.0, 10.0)}
SIMPLE_TRIANGLE_VALUES = {"_0_0": 100.0, "_10_0": 110.0, "_0_10": 130.0}


def _interpolate(vertex_labels, weights, values=None):
    """Weighted sum of the 3 known values, using the same convention fill_scenarios
    will use later: value = sum(weight_i * values[vertex_i])."""
    values = SIMPLE_TRIANGLE_VALUES if values is None else values
    return sum(w * values[label] for label, w in zip(vertex_labels, weights))


def test_build_barycentric_weights_weights_sum_to_one():
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    _, w = weights["_2_2"]
    assert w.sum() == pytest.approx(1.0)


def test_build_barycentric_weights_interior_point_matches_hand_calculation():
    # z(2, 2) = 100 + 2 + 3*2 = 108, by the plane formula above.
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    vertex_labels, w = weights["_2_2"]
    assert _interpolate(vertex_labels, w) == pytest.approx(108.0)


def test_build_barycentric_weights_edge_midpoint_matches_hand_calculation():
    # Midpoint of edge A-B: exactly halfway between values 100 and 110 -> 105.
    # z(5, 0) = 100 + 5 + 0 = 105, by the plane formula above.
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_5_0"])
    vertex_labels, w = weights["_5_0"]
    assert _interpolate(vertex_labels, w) == pytest.approx(105.0)


def test_build_barycentric_weights_exact_vertex_is_one_hot():
    # A point exactly at a known vertex's coordinates gets weight 1.0 on that vertex
    # and 0.0 on the other two (a distinct suffix string is used so this point is
    # treated as its own target, not skipped as an already-known scenario).
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_0.0_0.0"])
    vertex_labels, w = weights["_0.0_0.0"]
    assert _interpolate(vertex_labels, w) == pytest.approx(100.0)
    assert sorted(w) == pytest.approx([0.0, 0.0, 1.0])


def test_build_barycentric_weights_raises_for_point_outside_hull():
    with pytest.raises(ValueError, match="convex hull"):
        fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_20_20"])


# ---- fill_scenarios ------------------------------------------------------------------

def _save_point_frame(ari_values):
    """Build a tiny 2-row save-point DataFrame: ID/lat/lon + ari_values per ARI column."""
    import pandas as pd
    return pd.DataFrame({
        "ID": [1, 2], "lat": [46.5, 46.6], "lon": [-84.1, -84.2],
        0.1: ari_values, 1000: [v + 1000 for v in ari_values],
    })


SIMPLE_TRIANGLE_FRAMES = {
    "_0_0": _save_point_frame([100.0, 200.0]),
    "_10_0": _save_point_frame([110.0, 210.0]),
    "_0_10": _save_point_frame([130.0, 230.0]),
}


def test_fill_scenarios_matches_hand_calculation():
    # Same "_2_2" case as the barycentric weight tests: weights (B=0.2, C=0.2, A=0.6).
    # Row 0: 0.2*110 + 0.2*130 + 0.6*100 = 108. Row 1: 0.2*210 + 0.2*230 + 0.6*200 = 208.
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    df = filled["filled-_2_2"]
    assert df[0.1].tolist() == pytest.approx([108.0, 208.0])
    assert df[1000].tolist() == pytest.approx([1108.0, 1208.0])


def test_fill_scenarios_sheet_name_has_filled_prefix():
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_5_0"])
    filled = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    assert set(filled.keys()) == {"filled-_5_0"}


def test_fill_scenarios_rounds_to_two_decimals():
    # Weights of 1/3 each would produce a long decimal without rounding.
    import numpy as np
    weights = {"_thirds": (("_0_0", "_10_0", "_0_10"), np.array([1 / 3, 1 / 3, 1 / 3]))}
    filled = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    # (100 + 110 + 130) / 3 = 113.33333... -> rounds to 113.33.
    assert filled["filled-_thirds"][0.1].tolist() == [113.33, 213.33]


def test_fill_scenarios_propagates_nan():
    import numpy as np
    frames_with_nan = dict(SIMPLE_TRIANGLE_FRAMES)
    nan_frame = _save_point_frame([np.nan, 200.0])
    frames_with_nan["_0_0"] = nan_frame
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled = fillin_twl.fill_scenarios(frames_with_nan, weights)
    df = filled["filled-_2_2"]
    assert np.isnan(df[0.1].iloc[0])
    assert df[0.1].iloc[1] == pytest.approx(208.0)  # unaffected row stays correct


def test_fill_scenarios_keeps_id_lat_lon_from_known_frame():
    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    df = filled["filled-_2_2"]
    assert df["ID"].tolist() == [1, 2]
    assert df["lat"].tolist() == pytest.approx([46.5, 46.6])
    assert df["lon"].tolist() == pytest.approx([-84.1, -84.2])


# ---- select_anchor_scenario ------------------------------------------------------------

def test_select_anchor_scenario_picks_the_only_same_row_point():
    # dT=7 row: only "_0_7" is resolved -- every other dT=7 target anchors to it.
    resolved = {"_0_0", "_0_7"}
    assert fillin_twl.select_anchor_scenario("_10_7", resolved) == "_0_7"
    assert fillin_twl.select_anchor_scenario("_20_7", resolved) == "_0_7"


def test_select_anchor_scenario_picks_nearest_by_precip_distance():
    # dT=3 row: "_0_3" (dist 15), "_5_3" (dist 10), "_10_3" (dist 5) all resolved --
    # "_15_3" must anchor to the nearest one, "_10_3".
    resolved = {"_0_3", "_5_3", "_10_3"}
    assert fillin_twl.select_anchor_scenario("_15_3", resolved) == "_10_3"


def test_select_anchor_scenario_ignores_other_rows_even_if_closer_in_raw_distance():
    # "_5_5" is geometrically closer to "_15_7" than "_10_7" is (in raw 2D distance),
    # but it's on a different row (dT=5, not dT=7) so it must be ignored.
    resolved = {"_5_5", "_10_7"}
    assert fillin_twl.select_anchor_scenario("_15_7", resolved) == "_10_7"


def test_select_anchor_scenario_raises_when_no_same_row_point_is_resolved():
    resolved = {"_0_0"}
    with pytest.raises(ValueError, match="_5_7"):
        fillin_twl.select_anchor_scenario("_5_7", resolved)


# ---- extrapolate_scenarios -------------------------------------------------------------

def test_extrapolate_scenarios_shifts_anchor_values_by_avg_delta():
    # Anchor "_0_7" TWL values 100/200 (ARI 0.1) and 1100/1200 (ARI 1000); avg delta
    # from "_0_7" (180.0) to "_10_7" (185.0) is +5.0, so every value shifts by +5.0.
    resolved_frames = {"_0_7": _save_point_frame([100.0, 200.0])}
    avg_means = {"_0_7": 180.0, "_10_7": 185.0}
    extrapolated = fillin_twl.extrapolate_scenarios(resolved_frames, avg_means, ["_10_7"])
    df = extrapolated["extrapolated-_10_7"]
    assert df[0.1].tolist() == pytest.approx([105.0, 205.0])
    assert df[1000].tolist() == pytest.approx([1105.0, 1205.0])


def test_extrapolate_scenarios_keeps_id_lat_lon_from_anchor_frame():
    resolved_frames = {"_0_7": _save_point_frame([100.0, 200.0])}
    avg_means = {"_0_7": 180.0, "_10_7": 185.0}
    extrapolated = fillin_twl.extrapolate_scenarios(resolved_frames, avg_means, ["_10_7"])
    df = extrapolated["extrapolated-_10_7"]
    assert df["ID"].tolist() == [1, 2]
    assert df["lat"].tolist() == pytest.approx([46.5, 46.6])
    assert df["lon"].tolist() == pytest.approx([-84.1, -84.2])


def test_extrapolate_scenarios_rounds_to_two_decimals():
    resolved_frames = {"_0_7": _save_point_frame([100.0, 200.0])}
    # Delta of 1/3 would produce a long decimal without rounding.
    avg_means = {"_0_7": 180.0, "_10_7": 180.0 + 1 / 3}
    extrapolated = fillin_twl.extrapolate_scenarios(resolved_frames, avg_means, ["_10_7"])
    assert extrapolated["extrapolated-_10_7"][0.1].tolist() == [100.33, 200.33]


def test_extrapolate_scenarios_sheet_name_has_extrapolated_prefix():
    resolved_frames = {"_0_7": _save_point_frame([100.0, 200.0])}
    avg_means = {"_0_7": 180.0, "_10_7": 185.0}
    extrapolated = fillin_twl.extrapolate_scenarios(resolved_frames, avg_means, ["_10_7"])
    assert set(extrapolated.keys()) == {"extrapolated-_10_7"}


def test_extrapolate_scenarios_uses_nearest_resolved_scenario_as_anchor():
    # "_10_3" is a Delaunay-filled scenario here (not "known"), but extrapolate_scenarios
    # doesn't care -- it just needs it present in resolved_frames/avg_means.
    resolved_frames = {
        "_0_3": _save_point_frame([90.0, 190.0]),
        "_10_3": _save_point_frame([100.0, 200.0]),
    }
    avg_means = {"_0_3": 170.0, "_10_3": 180.0, "_15_3": 182.0}
    extrapolated = fillin_twl.extrapolate_scenarios(resolved_frames, avg_means, ["_15_3"])
    # Anchors to "_10_3" (nearest), delta = 182.0 - 180.0 = +2.0.
    assert extrapolated["extrapolated-_15_3"][0.1].tolist() == pytest.approx([102.0, 202.0])


def test_extrapolate_scenarios_raises_when_no_anchor_available():
    resolved_frames = {"_0_0": _save_point_frame([100.0, 200.0])}
    avg_means = {"_0_0": 180.0, "_5_7": 182.0}
    with pytest.raises(ValueError, match="_5_7"):
        fillin_twl.extrapolate_scenarios(resolved_frames, avg_means, ["_5_7"])


# ---- write_filled_workbook -------------------------------------------------------------

KNOWN_SHEETS = {
    "baseline-_0_0": SIMPLE_TRIANGLE_FRAMES["_0_0"],
    "nearterm-_10_0": SIMPLE_TRIANGLE_FRAMES["_10_0"],
    "extreme-_0_10": SIMPLE_TRIANGLE_FRAMES["_0_10"],
}


def test_write_filled_workbook_contains_known_and_filled_sheets(tmp_path):
    import pandas as pd

    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2", "_5_0"])
    filled_frames = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    output_path = tmp_path / "lake_twl.xlsx"

    fillin_twl.write_filled_workbook(KNOWN_SHEETS, filled_frames, output_path)

    assert output_path.exists()
    sheets = pd.read_excel(output_path, sheet_name=None)
    assert set(sheets.keys()) == {
        "baseline-_0_0", "nearterm-_10_0", "extreme-_0_10", "filled-_2_2", "filled-_5_0",
    }


def test_write_filled_workbook_roundtrips_known_values(tmp_path):
    import pandas as pd

    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled_frames = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    output_path = tmp_path / "lake_twl.xlsx"

    fillin_twl.write_filled_workbook(KNOWN_SHEETS, filled_frames, output_path)

    sheets = pd.read_excel(output_path, sheet_name=None)
    assert sheets["baseline-_0_0"]["ID"].tolist() == [1, 2]
    assert sheets["baseline-_0_0"][0.1].tolist() == pytest.approx([100.0, 200.0])
    assert sheets["filled-_2_2"][0.1].tolist() == pytest.approx([108.0, 208.0])


def test_write_filled_workbook_refuses_to_overwrite_by_default(tmp_path):
    output_path = tmp_path / "lake_twl.xlsx"
    output_path.write_text("existing file")

    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled_frames = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)

    with pytest.raises(FileExistsError):
        fillin_twl.write_filled_workbook(KNOWN_SHEETS, filled_frames, output_path)
    assert output_path.read_text() == "existing file"  # untouched


def test_write_filled_workbook_overwrite_true_replaces_existing(tmp_path):
    import pandas as pd

    output_path = tmp_path / "lake_twl.xlsx"
    output_path.write_text("existing file")

    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled_frames = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)

    fillin_twl.write_filled_workbook(
        KNOWN_SHEETS, filled_frames, output_path, overwrite=True
    )

    sheets = pd.read_excel(output_path, sheet_name=None)
    assert "filled-_2_2" in sheets


def test_write_filled_workbook_includes_extrapolated_sheets_when_given(tmp_path):
    import pandas as pd

    weights = fillin_twl.build_barycentric_weights(SIMPLE_TRIANGLE_COORDS, ["_2_2"])
    filled_frames = fillin_twl.fill_scenarios(SIMPLE_TRIANGLE_FRAMES, weights)
    avg_means = {"_0_0": 180.0, "_20_0": 185.0}
    extrapolated_frames = fillin_twl.extrapolate_scenarios(
        {"_0_0": SIMPLE_TRIANGLE_FRAMES["_0_0"]}, avg_means, ["_20_0"]
    )
    output_path = tmp_path / "lake_twl.xlsx"

    fillin_twl.write_filled_workbook(
        KNOWN_SHEETS, filled_frames, output_path, extrapolated_frames=extrapolated_frames
    )

    sheets = pd.read_excel(output_path, sheet_name=None)
    assert set(sheets.keys()) == {
        "baseline-_0_0", "nearterm-_10_0", "extreme-_0_10", "filled-_2_2", "extrapolated-_20_0",
    }


# ---- CLI (typer) ------------------------------------------------------------------------

runner = CliRunner()

# The 5 real known scenarios, identical across all 4 lake twl workbooks.
REAL_KNOWN_SHEET_NAMES = [
    "baseline-_0_0", "nearterm-_5_1.5", "moderate_low-_10_5",
    "extreme_low-_20_5", "extreme_high-_0_7",
]


def _real_twl_sheet_frame(save_point_id, level):
    """2-ARI-column save-point row frame, value == level for every ARI (keeps hand math simple)."""
    import pandas as pd
    return pd.DataFrame({
        "ID": [save_point_id], "lat": [46.0], "lon": [-84.0], 1: [level], 50: [level],
    })


def _make_lake_workbook(path, save_point_ids=(1, 2)):
    """Build a synthetic <lake>_twl.xlsx with the 5 real known-scenario sheets."""
    import pandas as pd
    with pd.ExcelWriter(path) as writer:
        for sheet_name in REAL_KNOWN_SHEET_NAMES:
            df = pd.concat(
                [_real_twl_sheet_frame(sp_id, 100.0 + sp_id) for sp_id in save_point_ids],
                ignore_index=True,
            )
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


def _make_avg_csv(data_dir, filename):
    """Write a synthetic <avg-lake>_avg.csv covering all 17 scenario suffixes.

    Each scenario column's value is 180.0 + its index in ALL_SCENARIO_SUFFIXES (2
    identical rows), so AVG deltas between any two scenarios are easy to hand-check.
    """
    import pandas as pd
    columns = {suffix: [180.0 + i, 180.0 + i]
               for i, suffix in enumerate(fillin_twl.ALL_SCENARIO_SUFFIXES)}
    pd.DataFrame({"time": ["1970-01-01", "1970-02-01"], **columns}).to_csv(
        data_dir / filename, index=False
    )


def _make_data_dir(tmp_path):
    data_dir = tmp_path / "clean"
    data_dir.mkdir()
    for _lake, filename in fillin_twl.common_twl.LAKE_TWL_FILENAMES.items():
        _make_lake_workbook(data_dir / filename)
    for filename in fillin_twl.common_twl.LAKE_AVG_FILENAMES.values():
        _make_avg_csv(data_dir, filename)
    return data_dir


def test_cli_processes_all_four_lakes_writes_17_sheets_each_by_default(tmp_path):
    data_dir = _make_data_dir(tmp_path)
    output_dir = tmp_path / "filled"

    result = runner.invoke(fillin_twl.app, [str(data_dir), str(output_dir)])

    assert result.exit_code == 0, result.output
    import pandas as pd
    for filename in fillin_twl.common_twl.LAKE_TWL_FILENAMES.values():
        sheets = pd.read_excel(output_dir / filename, sheet_name=None)
        assert len(sheets) == 17
        assert set(REAL_KNOWN_SHEET_NAMES) <= set(sheets.keys())
        extrapolated_names = {f"extrapolated-{s}" for s in
                               ("_5_7", "_10_7", "_15_3", "_15_7", "_20_7")}
        assert extrapolated_names <= set(sheets.keys())


def test_cli_no_extrapolate_writes_12_sheets_only(tmp_path):
    data_dir = _make_data_dir(tmp_path)
    output_dir = tmp_path / "filled"

    result = runner.invoke(fillin_twl.app, [str(data_dir), str(output_dir), "--no-extrapolate"])

    assert result.exit_code == 0, result.output
    import pandas as pd
    for filename in fillin_twl.common_twl.LAKE_TWL_FILENAMES.values():
        sheets = pd.read_excel(output_dir / filename, sheet_name=None)
        assert len(sheets) == 12
        assert not any(name.startswith("extrapolated-") for name in sheets)


def test_cli_extrapolated_sheet_values_match_hand_calculation(tmp_path):
    # avg deltas come from _make_avg_csv's "180.0 + suffix index" scheme:
    #   _0_7 (index 4) -> 184.0, _10_7 (index 11) -> 191.0, delta = +7.0
    #   _10_3 (index 9, itself Delaunay-filled here) -> 189.0, _15_3 (index 12) -> 192.0,
    #   delta = +3.0
    # Every known sheet uses the same save-point value (100+id) for every scenario, so
    # in-hull filled scenarios (e.g. "_10_3") also equal [101, 102] before any shift.
    data_dir = _make_data_dir(tmp_path)
    output_dir = tmp_path / "filled"

    result = runner.invoke(fillin_twl.app, [str(data_dir), str(output_dir)])

    assert result.exit_code == 0, result.output
    import pandas as pd
    sheets = pd.read_excel(output_dir / "superior_twl.xlsx", sheet_name=None)
    assert sheets["extrapolated-_10_7"][1].tolist() == pytest.approx([108.0, 109.0])
    assert sheets["extrapolated-_15_3"][1].tolist() == pytest.approx([104.0, 105.0])


def test_cli_refuses_to_overwrite_by_default(tmp_path):
    data_dir = _make_data_dir(tmp_path)
    output_dir = tmp_path / "filled"
    output_dir.mkdir()
    existing = output_dir / "superior_twl.xlsx"
    existing.write_text("pre-existing")


    result = runner.invoke(fillin_twl.app, [str(data_dir), str(output_dir)])

    assert result.exit_code != 0
    assert existing.read_text() == "pre-existing"  # untouched
    # nothing else was written either -- fails fast, before processing any lake.
    assert not (output_dir / "huron_twl.xlsx").exists()


def test_cli_overwrite_flag_replaces_existing_files(tmp_path):
    data_dir = _make_data_dir(tmp_path)
    output_dir = tmp_path / "filled"
    output_dir.mkdir()
    existing = output_dir / "superior_twl.xlsx"
    existing.write_text("pre-existing")

    result = runner.invoke(
        fillin_twl.app, [str(data_dir), str(output_dir), "--overwrite"]
    )

    assert result.exit_code == 0, result.output
    import pandas as pd
    sheets = pd.read_excel(output_dir / "superior_twl.xlsx", sheet_name=None)
    assert len(sheets) == 17


def test_cli_omitted_output_dir_defaults_to_extrapolated_sibling(tmp_path):
    data_dir = _make_data_dir(tmp_path)

    result = runner.invoke(fillin_twl.app, [str(data_dir)])

    assert result.exit_code == 0, result.output
    default_output_dir = data_dir.parent / "extrapolated"
    import pandas as pd
    sheets = pd.read_excel(default_output_dir / "superior_twl.xlsx", sheet_name=None)
    assert len(sheets) == 17


def test_cli_omitted_output_dir_no_extrapolate_defaults_to_filled_sibling(tmp_path):
    data_dir = _make_data_dir(tmp_path)

    result = runner.invoke(fillin_twl.app, [str(data_dir), "--no-extrapolate"])

    assert result.exit_code == 0, result.output
    default_output_dir = data_dir.parent / "filled"
    import pandas as pd
    sheets = pd.read_excel(default_output_dir / "superior_twl.xlsx", sheet_name=None)
    assert len(sheets) == 12


def test_cli_explicit_output_dir_still_overrides_default(tmp_path):
    data_dir = _make_data_dir(tmp_path)
    explicit_output_dir = tmp_path / "custom"

    result = runner.invoke(fillin_twl.app, [str(data_dir), str(explicit_output_dir)])

    assert result.exit_code == 0, result.output
    assert (explicit_output_dir / "superior_twl.xlsx").exists()
    assert not (data_dir.parent / "extrapolated").exists()
