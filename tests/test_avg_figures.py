"""Tests for great_lakes.avg_figures: avg mean-level response-surface figures."""
import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from great_lakes import avg_figures, units  # noqa: E402
from great_lakes.paths import Layout  # noqa: E402


def test_avg_lakes_are_the_five_cleaned_lakes():
    assert avg_figures.AVG_LAKES == (
        "superior", "michiganhuron", "stclair", "erie", "ontario")


def test_build_mean_grid_uses_scenario_means_in_requested_units_and_datum():
    columns = {"_0_0": np.array([100.0, 102.0]), "_5_1.5": np.array([103.0, 105.0])}
    xs, ys, zs = avg_figures.build_mean_grid(columns, "ft", "NAVD88")
    # Generic path: exact-foot units plus the datum shift (not the case-study scale).
    def ft_navd88(m):
        return units.convert_datum(units.convert_units(m, "m", "ft"), "IGLD85", "NAVD88", "ft")

    assert zs[list(ys).index(0.0), list(xs).index(0.0)] == pytest.approx(ft_navd88(101.0))
    assert zs[list(ys).index(1.5), list(xs).index(5.0)] == pytest.approx(ft_navd88(104.0))
    assert np.isnan(zs[list(ys).index(7.0), list(xs).index(20.0)])  # scenario not in data


@pytest.fixture
def layout(tmp_path):
    lay = Layout(tmp_path)
    lay.avg.mkdir(parents=True)
    frame = pd.DataFrame({"time": ["2000-01-01", "2000-02-01"], "_0_0": [183.0, 183.4],
                          "_5_1.5": [183.1, 183.5], "_20_7": [182.0, 182.2]})
    for lake in ("superior", "erie"):
        frame.to_csv(lay.avg / f"{lake}_avg.csv", index=False)
    return lay


def test_write_avg_figures_defaults_write_tracked_and_bulk_figures(layout):
    written = avg_figures.write_avg_figures(layout, lake_names=("superior", "erie"))
    expected = [
        layout.avg_figures / "superior.png", layout.avg_figures / "erie.png",
        layout.avg_bulk_figures / "superior.png", layout.avg_bulk_figures / "erie.png",
        layout.avg_bulk_figures / "interpolated" / "superior.png",
        layout.avg_bulk_figures / "interpolated" / "erie.png",
    ]
    assert sorted(written) == sorted(expected)
    assert all(p.exists() for p in written)


def test_non_default_units_leave_tracked_figures_alone(layout):
    written = avg_figures.write_avg_figures(
        layout, lake_names=("superior",), to_units="m", to_datum="IGLD85")
    folder = layout.avg_bulk_figures / "m_IGLD85"
    assert sorted(written) == sorted([folder / "superior.png", folder / "interpolated" /
                                      "superior.png"])
    assert not layout.avg_figures.exists()
