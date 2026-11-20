"""Tests for great_lakes.swl.figures: swl response-surface figures."""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from great_lakes.ari import SWL_ARIS  # noqa: E402
from great_lakes.paths import Layout  # noqa: E402
from great_lakes.swl import figures  # noqa: E402
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES  # noqa: E402

LABELS = ("precip_delta", "temp_delta", "Water level (ft, NAVD88)")


def _surface(estimated=None) -> figures.Surface:
    xs = np.array([0.0, 5.0, 10.0])
    ys = np.array([0.0, 3.0])
    zs = np.array([[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]])
    return figures.Surface(xs, ys, zs, title="t", estimated=estimated)


def _estimated_lines(ax):
    return [ln for ln in ax.get_lines() if ln.get_label() == figures.ESTIMATED_LABEL]


def test_draw_panel_marks_only_estimated_cells():
    mask = np.array([[False, True, False], [False, False, True]])
    fig, ax = plt.subplots()
    figures.draw_panel(fig, ax, _surface(mask), LABELS, threshold=2.5)
    (line,) = _estimated_lines(ax)
    assert sorted(zip(line.get_xdata(), line.get_ydata())) == [(5.0, 0.0), (10.0, 3.0)]
    plt.close(fig)


def test_draw_panel_without_estimated_cells_adds_no_marker():
    fig, ax = plt.subplots()
    figures.draw_panel(fig, ax, _surface(), LABELS, threshold=2.5)
    assert _estimated_lines(ax) == []
    plt.close(fig)


def test_summary_figure_has_one_colorbar_per_panel():
    fig = figures.build_summary_figure([_surface()] * 4, LABELS, 2.5, "suptitle")
    assert len(fig.axes) == 8  # 4 panels + 4 colorbars
    plt.close(fig)


def test_summary_figure_requires_four_panels():
    with pytest.raises(ValueError, match="4"):
        figures.build_summary_figure([_surface()] * 3, LABELS, 2.5, "suptitle")


def _write_workbook(path, names):
    frame = {"ID": [1, 2], "lat": [47.7, 46.0], "lon": [-86.9, -85.0]}
    for ari in SWL_ARIS:
        frame[ari] = [183.0 + 0.001 * ari, 184.0]
    with pd.ExcelWriter(path) as writer:
        for i, name in enumerate(names):
            data = pd.DataFrame(frame)
            data[list(SWL_ARIS)] = data[list(SWL_ARIS)] + 0.01 * i
            data.to_excel(writer, sheet_name=name, index=False)


@pytest.fixture
def layout(tmp_path):
    lay = Layout(tmp_path)
    for directory in (lay.avg, lay.swl_clean, lay.swl_complete):
        directory.mkdir(parents=True)
    pd.DataFrame({"time": [1, 2], "_0_0": [183.0, 183.2]}).to_csv(
        lay.avg / "superior_avg.csv", index=False)
    known = ["baseline-_0_0", "nearterm-_5_1.5", "moderate_low-_10_5",
             "extreme_low-_20_5", "extreme_high-_0_7"]
    _write_workbook(lay.swl_clean / "superior_swl.xlsx", known)
    names = list(known)
    for suffix in ALL_SCENARIO_SUFFIXES:
        if not any(n.endswith(suffix) for n in known):
            names.append(f"{'filled' if suffix == '_5_3' else 'extrapolated'}-{suffix}")
    _write_workbook(lay.swl_complete / "superior_swl.xlsx", names)
    return lay


def test_write_swl_figures_writes_summaries_and_bulk(layout):
    written = figures.write_swl_figures(layout, lake_names=("superior",))
    assert layout.swl_clean_figures / "superior.png" in written
    assert layout.swl_complete_figures / "superior.png" in written
    for kind in ("clean", "complete"):
        assert len(list((layout.swl_bulk_figures / kind).glob("superior_*.png"))) == len(SWL_ARIS)
    assert all(p.exists() for p in written)


def test_summary_only_skips_bulk_figures(layout):
    written = figures.write_swl_figures(layout, lake_names=("superior",), summary_only=True)
    assert not layout.swl_bulk_figures.exists()
    assert len(written) == 2


def test_non_default_units_write_summaries_to_a_separate_folder(layout):
    written = figures.write_swl_figures(
        layout, lake_names=("superior",), to_units="m", to_datum="IGLD85", summary_only=True)
    folder = layout.swl_bulk_figures / "summary_m_IGLD85"
    assert sorted(p.parent for p in written) == [folder / "clean", folder / "complete"]
    assert not (layout.swl_clean_figures / "superior.png").exists()
