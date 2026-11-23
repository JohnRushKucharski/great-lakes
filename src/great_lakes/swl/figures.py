"""swl response-surface figures: storm water level vs precip and temp climate deltas.

One renderer draws both the standalone figures and the panels of the 2x2 summary figures,
so a panel looks the same as its standalone figure. Cells that were estimated (filled or
extrapolated, not known) carry a small dot. Cells are discrete (no interpolation); the
colour scale is centred on the lake's baseline avg level (see `GLOSSARY.md`).
"""

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from climate_canvas.plots_utilities import _render_surface  # type: ignore[import-untyped]
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from great_lakes import ari, lakes, units
from great_lakes.paths import Layout
from great_lakes.swl import sheets as swl_sheets
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES, known_scenario_coords

LAKES = tuple(lakes.LAKE_SWL_FILENAMES)
SUMMARY_ARIS = (1.0, 10.0, 100.0, 1000.0)
ESTIMATED_LABEL = "estimated (filled or extrapolated)"
DEFAULT_UNITS: units.Units = "ft"
DEFAULT_DATUM: units.Datum = "NAVD88"

_ALL_COORDS = {suffix: parse_scenario_name(suffix) for suffix in ALL_SCENARIO_SUFFIXES}


@dataclass(frozen=True)
class Surface:
    """One response surface: z[i, j] at (ys[i] temp delta, xs[j] precip delta)."""

    xs: np.ndarray
    ys: np.ndarray
    zs: np.ndarray
    title: str
    estimated: np.ndarray | None = None


def draw_panel(
    fig: Figure, ax: Axes, surface: Surface, labels: tuple[str, str, str], threshold: float,
    interpolate: bool = False,
) -> None:
    """Draw `surface` on `ax` with its own colorbar, dotting estimated cells.

    `interpolate` resamples to a finer grid (Delaunay fill for NaN cells); the dots are
    only drawn on the discrete grid.
    """
    im, _, levels, threshold_given = _render_surface(
        ax, surface.xs, surface.ys, surface.zs, labels=labels, title=surface.title,
        threshold=threshold, interpolate=interpolate, fillin=interpolate,
    )
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(labels[2])
    if threshold_given:
        cbar.set_ticks(levels)
    if surface.estimated is not None and surface.estimated.any():
        rows, cols = np.nonzero(surface.estimated)
        (marker,) = ax.plot(
            surface.xs[cols], surface.ys[rows], linestyle="", marker=".", color="black",
            markersize=8, label=ESTIMATED_LABEL,
        )
        ax.legend(handles=[marker], loc="upper right", fontsize="small")


def build_standalone_figure(
    surface: Surface, labels: tuple[str, str, str], threshold: float, interpolate: bool = False
) -> Figure:
    fig, ax = plt.subplots(figsize=(10, 10))
    draw_panel(fig, ax, surface, labels, threshold, interpolate)
    return fig


def build_summary_figure(
    surfaces: list[Surface], labels: tuple[str, str, str], threshold: float, suptitle: str
) -> Figure:
    """2x2 figure of four surfaces, each with its own colorbar."""
    if len(surfaces) != 4:
        raise ValueError(f"A summary figure needs 4 surfaces, got {len(surfaces)}.")
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    for ax, surface in zip(axes.ravel(), surfaces):
        draw_panel(fig, ax, surface, labels, threshold)
    fig.suptitle(suptitle)
    fig.tight_layout()
    return fig


def save_figure(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _baseline_level(
    lake: str, avg_dir: Path, to_units: units.Units, to_datum: units.Datum
) -> float:
    """Baseline (`_0_0`) avg level of the lake, in the requested units and datum."""
    meters_igld85 = lakes.read_avg_scenario_means(lake, avg_dir)["_0_0"]
    value = units.convert_units(meters_igld85, "m", to_units)
    return float(units.convert_datum(value, "IGLD85", to_datum, to_units))


def write_swl_figures(
    layout: Layout,
    lake_names: tuple[str, ...] = LAKES,
    to_units: units.Units = DEFAULT_UNITS,
    to_datum: units.Datum = DEFAULT_DATUM,
    summary_only: bool = False,
) -> list[Path]:
    """Write the swl figures for `clean` (known scenarios) and `complete` (all 17) workbooks.

    Per lake: a 2x2 summary (ARI 1/10/100/1000 at the lake-centroid save point) and, unless
    `summary_only`, one standalone figure per ARI under `layout.swl_bulk_figures`. Summaries
    of the default units and datum (ft, NAVD88) go next to the data they describe
    (`data/swl/<kind>/figures/`); any other choice goes under
    `<bulk figures>/summary_<units>_<datum>/<kind>/` so tracked figures stay consistent.
    Returns the files written.
    """
    is_default = (to_units, to_datum) == (DEFAULT_UNITS, DEFAULT_DATUM)
    labels = ("precip_delta", "temp_delta",
              units.water_level_label(to_units, to_datum, "Storm water level"))
    unit_note = f"{to_units}, {to_datum}"
    written: list[Path] = []
    for kind, source_dir, tracked_dir in (
        ("clean", layout.swl_clean, layout.swl_clean_figures),
        ("complete", layout.swl_complete, layout.swl_complete_figures),
    ):
        summary_dir = tracked_dir if is_default else (
            layout.swl_bulk_figures / f"summary_{to_units}_{to_datum}" / kind)
        for lake in lake_names:
            sheets = swl_sheets.load_lake_sheets(lakes.resolve_lake_swl_path(lake, source_dir))
            coords = known_scenario_coords(list(sheets)) if kind == "clean" else _ALL_COORDS
            estimated = None if kind == "clean" else swl_sheets.estimated_cell_mask(coords, sheets)
            save_point = lakes.lake_centroid_save_point_id(lake, sheets)
            threshold = _baseline_level(lake, layout.avg, to_units, to_datum)
            heading = (f"{lake.capitalize()} save point {save_point} "
                       f"(baseline average lake level = {threshold:.2f} {unit_note})")

            def surface(aril: float, title: str) -> Surface:
                xs, ys, zs = swl_sheets.build_scenario_ari_grid(
                    coords, sheets, save_point, aril, to_units, to_datum)
                return Surface(xs, ys, zs, title, estimated)

            panels = [surface(a, f"ARI={ari.format_ari(a)}") for a in SUMMARY_ARIS]
            fig = build_summary_figure(panels, labels, threshold, heading)
            written.append(save_figure(fig, summary_dir / f"{lake}.png"))

            if summary_only:
                continue
            for aril in ari.SWL_ARIS:
                label = ari.format_ari(aril)
                fig = build_standalone_figure(
                    surface(aril, f"{heading}\nARI={label}"), labels, threshold)
                written.append(
                    save_figure(fig, layout.swl_bulk_figures / kind / f"{lake}_{label}.png"))
    return written
