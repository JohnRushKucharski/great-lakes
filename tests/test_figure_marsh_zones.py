"""Tests for the F4 marsh-zone share heatmap + depth maps data prep (habitat memo)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "case-studies/long-tail-point/habitat/scripts"
spec = importlib.util.spec_from_file_location("f4", SCRIPTS / "figure_marsh_zones.py")
assert spec is not None and spec.loader is not None
f4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f4)


def test_zone_shares_count_points_inside_depth_ranges_inclusive():
    bottoms = np.array([578.0, 577.0, 574.0, 579.0])  # depths at 579 ft: 1, 2, 5, 0
    shares = f4.zone_shares(bottoms, 579.0)

    assert shares["Shoreline marsh"] == pytest.approx(2 / 4)  # 0 and 1 ft
    assert shares["Shallow submergent"] == pytest.approx(2 / 4)  # 2 and 5 ft
    assert shares["Deep submergent"] == pytest.approx(1 / 4)  # 5 ft
    assert list(shares.index) == list(f4.ZONES)


def test_zone_shares_ignore_floating_point_noise_at_boundaries():
    shares = f4.zone_shares(np.array([575.0 + 1e-9]), 579.0)  # depth 3.999999999 ~ 4 ft

    assert shares["Deep submergent"] == 1.0


def test_scenarios_are_ordered_dry_to_wet_by_mean_level():
    levels_ft = {"_0_0": 579.16, "_0_3": 576.06, "_15_3": 581.1, "_0_1.5": 577.56}

    assert f4.order_by_level(levels_ft) == ["_0_3", "_0_1.5", "_0_0", "_15_3"]


def test_jenny_maps_are_copied_unchanged_from_the_tracked_inputs(tmp_path):
    source = tmp_path / "maps"
    source.mkdir()
    (source / "F4B.png").write_bytes(b"map-3c-dry")
    (source / "F4C.png").write_bytes(b"map-3c-wet")
    out = tmp_path / "figures"
    out.mkdir()

    written = f4.copy_jenny_maps(out, source)

    assert sorted(p.name for p in written) == ["F4B.png", "F4C.png"]
    assert (out / "F4B.png").read_bytes() == b"map-3c-dry"
    assert (out / "F4C.png").read_bytes() == b"map-3c-wet"


def test_tracked_jenny_maps_exist():
    assert sorted(p.name for p in f4.JENNY_MAPS_DIR.glob("*.png")) == ["F4B.png", "F4C.png"]


def test_matches_jenny_save_point_counts_for_three_scenarios():
    if not (f4.SURVEY_XLSX.is_file() and f4.LEVELS_CSV.is_file()):
        pytest.skip("survey/levels inputs not available")
    bottoms = f4.save_point_elevations()
    levels = f4.mean_levels_ft(pd.read_csv(f4.LEVELS_CSV, index_col="time"))

    assert len(bottoms) == 288
    expected = {  # Jenny marsh_zone_distribution counts
        "_0_0": {"Rooting floating": 109, "Shallow submergent": 215, "Deep submergent": 107},
        "_0_3": {"Shoreline marsh": 65, "Rooting floating": 142, "Deep submergent": 29},
        "_15_3": {"Shallow submergent": 109, "Deep submergent": 109},
    }
    for scenario, counts in expected.items():
        shares = f4.zone_shares(bottoms, levels[scenario])
        for zone, count in counts.items():
            # baseline level in the CSV differs from Jenny's by ~0.002 ft: allow 3 boundary points
            assert abs(shares[zone] * 288 - count) <= 3, (scenario, zone)
