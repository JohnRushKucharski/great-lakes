"""Helpers shared by the scenario-grid figure sets (17 precip x temp scenarios per lake)."""

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from climate_canvas.data_utilities import (  # type: ignore[import-untyped]
    check_threshold,
    evenly_space,
    resample_resolution,
)
from climate_canvas.data_utilities import (  # type: ignore[import-untyped]
    contour_levels as canvas_contour_levels,
)
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
from matplotlib.ticker import FormatStrFormatter

from great_lakes import units
from great_lakes.batch import swl as swl_batch
from great_lakes.swl import complete as swl_complete
from great_lakes.swl.sheets import NON_ARI_COLUMNS, parse_scenario_sheet_name

KNOWN_SUFFIXES = {"_0_0", "_5_1.5", "_10_5", "_20_5", "_0_7"}
INTERPOLATED_SUFFIXES = {
    "_0_1.5", "_0_3", "_0_5", "_5_3", "_5_5", "_10_3", "_15_5",
}
EXTRAPOLATED_SUFFIXES = {"_15_3", "_5_7", "_10_7", "_15_7", "_20_7"}
WARMING_SCENARIOS = {
    1.5: ("_0_1.5", "_5_1.5"),
    3.0: ("_0_3", "_5_3", "_10_3", "_15_3"),
}
STATUS_MARKS = {"known": "", "interpolated": "*", "extrapolated": "**"}


def scenario_status(suffix: str) -> str:
    """`known` (modeled), `interpolated` or `extrapolated` for a scenario suffix."""
    if suffix in KNOWN_SUFFIXES:
        return "known"
    if suffix in INTERPOLATED_SUFFIXES:
        return "interpolated"
    if suffix in EXTRAPOLATED_SUFFIXES:
        return "extrapolated"
    raise ValueError(f"Unclassified scenario {suffix!r}")


def load_scenario_sheets(swl_path: Path) -> dict[str, pd.DataFrame]:
    """Read a complete `<lake>_swl.xlsx` into {suffix: frame}; require all 17 scenarios."""
    sheets = pd.read_excel(swl_path, sheet_name=None, engine="calamine")
    by_suffix: dict[str, pd.DataFrame] = {}
    for sheet_name, frame in sheets.items():
        suffix = parse_scenario_sheet_name(sheet_name)
        if suffix is None:
            continue
        if suffix in by_suffix:
            raise ValueError(f"Multiple SWL sheets found for scenario {suffix}")
        by_suffix[suffix] = frame
    expected = set(swl_complete.ALL_SCENARIO_SUFFIXES)
    if by_suffix.keys() != expected:
        raise ValueError(
            "SWL workbook scenarios do not match the expected 17-scenario set: "
            f"missing={sorted(expected - by_suffix.keys())}, "
            f"extra={sorted(by_suffix.keys() - expected)}"
        )
    return by_suffix


def ari_columns(frame: pd.DataFrame) -> list[tuple[float, str | int | float]]:
    """(ARI years, column label) pairs of a swl sheet, sorted by ARI."""
    columns = []
    for column in frame.columns:
        if column in NON_ARI_COLUMNS:
            continue
        if not isinstance(column, (str, int, float)):
            raise ValueError(f"Unexpected ARI column type: {type(column).__name__}")
        columns.append((float(column), column))
    return sorted(columns)


def _save_point_row(frame: pd.DataFrame, save_point_id: int) -> pd.Series:
    rows = frame.loc[frame["ID"] == save_point_id]
    if len(rows) != 1:
        raise ValueError(f"Expected one row for save point {save_point_id}; found {len(rows)}")
    return rows.iloc[0]


def scenario_level_ft(frame: pd.DataFrame, save_point_id: int, ari: float) -> float:
    """swl at a save point and ARI, interpolated on the curve, in ft NAVD88."""
    row = _save_point_row(frame, save_point_id)
    columns = ari_columns(frame)
    value_m = swl_batch.interpolate_level(
        [column[0] for column in columns],
        [float(row[column[1]]) for column in columns],
        ari,
    )
    return units.m_igld85_to_ft_NAVD88(value_m)


def scenario_means(monthly: pd.DataFrame) -> dict[str, float]:
    """Full-record mean of each scenario column of a monthly avg table."""
    return {
        suffix: float(monthly[suffix].mean()) for suffix in swl_complete.ALL_SCENARIO_SUFFIXES
    }


def scenario_coordinates(suffix: str) -> tuple[float, float]:
    """(precip delta %, temp delta C) of a scenario suffix."""
    coordinates = parse_scenario_name(suffix)
    if coordinates is None:
        raise ValueError(f"Invalid scenario suffix {suffix!r}")
    return coordinates


def save_grid_csv(values: dict[str, float], output_path: Path, offset_ft: float = 0.0) -> None:
    """Write scenario values as a temp x precip grid CSV (optionally shifted by `offset_ft`)."""
    coordinates = {suffix: scenario_coordinates(suffix) for suffix in values}
    precips = sorted({point[0] for point in coordinates.values()})
    temps = sorted({point[1] for point in coordinates.values()})
    grid = pd.DataFrame(index=temps, columns=precips, dtype=float)
    grid.index.name = "temp_delta\\precip_delta"
    for suffix, value in values.items():
        precip, temp = coordinates[suffix]
        grid.loc[temp, precip] = value + offset_ft
    grid.to_csv(output_path)


def _cell_edges(centers: Sequence[float]) -> np.ndarray:
    points = np.asarray(centers, dtype=float)
    midpoints = (points[:-1] + points[1:]) / 2
    return np.concatenate(([points[0] - (midpoints[0] - points[0])], midpoints,
                           [points[-1] + (points[-1] - midpoints[-1])]))


def draw_scenario_grid(
    ax: plt.Axes,
    values: dict[str, float],
    value_label: str,
    focus_suffixes: set[str] | None = None,
    contour_levels: Sequence[float] = (),
    value_fontsize: float = 8,
    threshold: float | None = None,
    blocky: bool = False,
) -> None:
    """Draw the scenario surface.

    Default: climate_canvas style (RdBu, bilinear resampling, centered on `threshold`).
    `blocky`: one flat cell per scenario (no interpolation), same RdBu scale and ticks.
    """
    coordinates = {suffix: scenario_coordinates(suffix) for suffix in values}
    precips = sorted({point[0] for point in coordinates.values()})
    temps = sorted({point[1] for point in coordinates.values()})
    grid = np.full((len(temps), len(precips)), np.nan)
    for suffix, value in values.items():
        precip, temp = coordinates[suffix]
        grid[temps.index(temp), precips.index(precip)] = value
    if blocky:
        z_range = (float(np.nanmin(grid)), float(np.nanmax(grid)))
        norm = TwoSlopeNorm(
            vmin=z_range[0], vcenter=check_threshold(threshold, z_range), vmax=z_range[1]
        )
        image = ax.pcolormesh(
            _cell_edges(precips), _cell_edges(temps), np.ma.masked_invalid(grid),
            shading="flat", cmap="RdBu", norm=norm,
        )
        tick_levels, _ = canvas_contour_levels(z_range, norm.vcenter)
    else:
        fine_x, fine_y, fine_z = evenly_space(
            np.asarray(precips), np.asarray(temps), grid, None,
            (resample_resolution(len(precips)), resample_resolution(len(temps))),
        )
        z_range = (float(np.nanmin(fine_z)), float(np.nanmax(fine_z)))
        norm = TwoSlopeNorm(
            vmin=z_range[0], vcenter=check_threshold(threshold, z_range), vmax=z_range[1]
        )
        image = ax.pcolormesh(fine_x, fine_y, fine_z, shading="nearest", cmap="RdBu", norm=norm)
    colorbar = ax.figure.colorbar(image, ax=ax, label=value_label)
    if blocky:
        colorbar.set_ticks(list(tick_levels))
    colorbar.ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    for suffix, value in values.items():
        precip, temp = coordinates[suffix]
        known = scenario_status(suffix) == "known"
        mark = STATUS_MARKS[scenario_status(suffix)]
        if blocky:
            x_index, y_index = precips.index(precip), temps.index(temp)
            left, right = _cell_edges(precips)[x_index:x_index + 2]
            bottom, top = _cell_edges(temps)[y_index:y_index + 2]
            if known:
                # white halo under black line keeps the outline visible on dark cells
                for color, width in (("white", 3.0), ("black", 1.4)):
                    ax.add_patch(
                        Rectangle(
                            (left, bottom), right - left, top - bottom,
                            fill=False, edgecolor=color, linewidth=width, zorder=3,
                        )
                    )
            ax.text(
                precip, temp, f"{value:.1f}{mark}", ha="center", va="center",
                fontsize=value_fontsize, zorder=6,
                bbox={
                    "boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.88,
                    "edgecolor": "none",
                },
            )
            continue
        if focus_suffixes and suffix in focus_suffixes:
            ax.add_patch(
                Rectangle(
                    (precip - 1.6, temp - 0.3), 3.2, 0.6,
                    fill=False, edgecolor="#159d8c", linewidth=2.2, zorder=5,
                )
            )
        ax.text(
            precip, temp, f"{value:.1f}{mark}", ha="center", va="center",
            fontsize=value_fontsize, zorder=6,
            bbox={
                "boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.75,
                "edgecolor": "black" if known else "none", "linewidth": 0.9,
            },
        )
    if contour_levels and blocky:
        ordered = sorted(values, key=lambda suffix: coordinates[suffix])
        points = np.asarray([coordinates[suffix] for suffix in ordered])
        z_values = np.asarray([values[suffix] for suffix in ordered])
        ax.tricontour(
            points[:, 0], points[:, 1], z_values, levels=list(contour_levels),
            colors="#252525", linestyles=("--", "-"), linewidths=1.5, zorder=4,
        )
    elif contour_levels:
        ax.contour(
            fine_x, fine_y, fine_z, levels=list(contour_levels),
            colors="#252525", linestyles=("--", "-"), linewidths=1.5,
        )
    ax.set_xticks(precips)
    ax.set_yticks(temps)
    ax.set_xlabel("Precipitation delta (%)")
    ax.set_ylabel("Temperature delta (C)")
    x_edges = _cell_edges(precips)
    y_edges = _cell_edges(temps)
    ax.set_xlim(float(x_edges[0]), float(x_edges[-1]))
    ax.set_ylim(float(y_edges[0]), float(y_edges[-1]))
