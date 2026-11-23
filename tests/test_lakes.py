"""Tests for great_lakes.lakes: lake names, avg/swl file paths, centroids."""
import pandas as pd
import pytest

from great_lakes import lakes


def test_resolve_lake_swl_path(tmp_path):
    assert lakes.resolve_lake_swl_path("huron", tmp_path) == tmp_path / "huron_swl.xlsx"


def test_resolve_lake_avg_path_michigan_and_huron_share_same_file(tmp_path):
    michigan_path = lakes.resolve_lake_avg_path("michigan", tmp_path)
    huron_path = lakes.resolve_lake_avg_path("huron", tmp_path)
    assert michigan_path == huron_path == tmp_path / "michiganhuron_avg.csv"


def test_resolve_lake_avg_path_superior(tmp_path):
    assert lakes.resolve_lake_avg_path("superior", tmp_path) == tmp_path / "superior_avg.csv"


def test_resolve_lake_avg_path_ontario(tmp_path):
    assert lakes.resolve_lake_avg_path("ontario", tmp_path) == tmp_path / "ontario_avg.csv"


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
    means = lakes.read_avg_scenario_means("superior", tmp_path)
    assert means["_0_0"] == pytest.approx(183.2)
    assert means["_0_7"] == pytest.approx(182.333333, rel=1e-6)


def test_read_avg_scenario_means_excludes_time_column(tmp_path):
    _write_tiny_avg_csv(tmp_path)
    means = lakes.read_avg_scenario_means("superior", tmp_path)
    assert "time" not in means


def test_read_avg_scenario_means_michigan_and_huron_read_same_file(tmp_path):
    _write_tiny_avg_csv(tmp_path, filename="michiganhuron_avg.csv")
    michigan_means = lakes.read_avg_scenario_means("michigan", tmp_path)
    huron_means = lakes.read_avg_scenario_means("huron", tmp_path)
    assert michigan_means == huron_means == {"_0_0": pytest.approx(183.2),
                                              "_0_7": pytest.approx(182.333333, rel=1e-6)}


def test_read_avg_scenario_means_uses_full_record_not_a_subset(tmp_path):
    rows = "time,_0_0\n" + "\n".join(f"1970-{m:02d}-01,{100.0 + m}" for m in range(1, 13)) + "\n"
    (tmp_path / "superior_avg.csv").write_text(rows)
    means = lakes.read_avg_scenario_means("superior", tmp_path)
    expected = sum(100.0 + m for m in range(1, 13)) / 12
    assert means["_0_0"] == pytest.approx(expected)


# ---- lake centroids / lake_centroid_save_point_id -----------------------------------

def test_lake_centroids_cover_all_five_lakes():
    assert lakes.LAKE_CENTROIDS == {
        "superior": (47.72, -86.94),
        "michigan": (44.01, -86.76),
        "huron": (44.94, -82.22),
        "erie": (42.25, -81.15),
        "ontario": (43.63, -77.62),
    }


def _sheets(rows):
    return {"baseline-_0_0": pd.DataFrame(rows, columns=["ID", "lat", "lon"])}


def test_lake_centroid_save_point_id_is_nearest_to_lake_centroid_not_save_point_mean():
    # The save points' own mean is near (22, 12); the lake centroid is not.
    sheets = _sheets([(1, 10.0, 10.0), (2, 10.0, 12.0), (3, 47.7, -86.9)])
    assert lakes.lake_centroid_save_point_id("superior", sheets) == 3


def test_lake_centroid_save_point_id_scales_longitude_by_cos_latitude():
    # Superior centroid (47.72, -86.94). A is 1.0 deg lon away (0.67 deg on the ground),
    # B is 0.8 deg lat away: unscaled B is nearer, scaled A is nearer.
    sheets = _sheets([(1, 47.72, -85.94), (2, 48.52, -86.94)])
    assert lakes.lake_centroid_save_point_id("superior", sheets) == 1


def test_lake_centroid_save_point_id_uses_first_sheet_only():
    first = _sheets([(10, 47.72, -86.94), (20, 40.0, -80.0)])["baseline-_0_0"]
    other = pd.DataFrame([(99, 47.72, -86.94)], columns=["ID", "lat", "lon"])
    assert lakes.lake_centroid_save_point_id(
        "superior", {"baseline-_0_0": first, "filled-_5_7": other}
    ) == 10


def test_lake_centroid_save_point_id_unknown_lake_raises():
    with pytest.raises(KeyError):
        lakes.lake_centroid_save_point_id("champlain", _sheets([(1, 1.0, 1.0)]))
