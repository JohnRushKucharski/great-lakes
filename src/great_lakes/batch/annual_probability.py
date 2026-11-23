"""Annual probability: the avg batch's metric for "how often does the pattern occur in a year".

annual_probability = (complete water years with at least 1 occurrence) / (complete water
years whose occurrence count is known), per scenario. An occurrence is a run of consecutive
success timesteps of the component (hydropattern calls these "events" in the
`event_count_*` columns of the summary workbook's `reporting_details` sheet). Partial water
years and water years whose outcomes are too unknown to say whether an occurrence happened
are left out. The result is in [0, 1].

This is NOT a return period: monthly timeseries values are not independent enough to
support one, so occurrences are not treated as independent events. Hydropattern's summary
workbook already holds the per-water-year counts, so this module only reads them and builds
the grid csv and plot (hydropattern's own grid supports portion/percentage only).
"""
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from climate_canvas.plots_utilities import plot_response_surface  # type: ignore[import-untyped]
from hydropattern.formatters import write_grid_csv  # type: ignore[import-untyped]
from hydropattern.scenario_grid import (  # type: ignore[import-untyped]
    build_grid,
    require_scenario_grid,
)

from great_lakes.batch.runner import default_color_map_direction

METRIC_MODE = "annual_probability"
Z_LABEL = "Annual probability of at least 1 occurrence"
_SHEET = "reporting_details"


def annual_probability_by_scenario(summary_path: Path, component_name: str) -> pd.DataFrame:
    """Per-scenario annual probability from a hydropattern `<name>_summary.xlsx`.

    Columns: eligible_water_years, occurrence_water_years, annual_probability (NaN when no
    water year is eligible). Index: scenario name.
    """
    details = pd.read_excel(summary_path, sheet_name=_SHEET, engine="calamine")
    rows = details[
        (details["outcome_column"] == component_name)
        & (details["completeness"] == "complete")
    ]
    lower = pd.to_numeric(rows["event_count_lower"], errors="coerce")
    upper = pd.to_numeric(rows["event_count_upper"], errors="coerce")
    has_occurrence = lower >= 1
    no_occurrence = upper == 0
    flags = pd.DataFrame({
        "scenario": rows["scenario"],
        "eligible": has_occurrence | no_occurrence,
        "occurrence": has_occurrence,
    })
    table = flags.groupby("scenario", sort=False).agg(
        eligible_water_years=("eligible", "sum"),
        occurrence_water_years=("occurrence", "sum"),
    )
    # Scenarios with no complete water year at all still get a (NaN) row.
    scenarios = list(dict.fromkeys(details["scenario"]))
    table = table.reindex(scenarios).fillna(0).astype(int)
    eligible = table["eligible_water_years"].replace(0, np.nan)
    table["annual_probability"] = table["occurrence_water_years"] / eligible
    table.index.name = "scenario"
    return table


def write_outputs(
    summary_path: Path,
    component_name: str,
    output_folder: Path,
    success_pattern: bool,
    plot_enabled: bool,
    plot_options: dict[str, Any],
    plot_fn: Callable[..., None] = plot_response_surface,
) -> list[Path]:
    """Write `<name>_annual_probability.csv` and, if plot_enabled, `<name>_grid.csv` + plot.

    plot_options are forwarded to plot_fn (interpolate, threshold, color_map, ...). The
    default 'RdBu' is reversed when the component is not a success pattern, so red always
    means less success (the same rule hydropattern 0.1.1 applied to portion).
    """
    table = annual_probability_by_scenario(summary_path, component_name)
    table_path = output_folder / f"{component_name}_annual_probability.csv"
    table.to_csv(table_path)
    written = [table_path]
    if not plot_enabled:
        return written

    values = {str(s): float(v) for s, v in table["annual_probability"].items()}
    require_scenario_grid(list(values))
    xs, ys, zs = build_grid(list(values), values)
    grid_path = output_folder / f"{component_name}_grid.csv"
    plot_path = output_folder / f"{component_name}_plot.png"
    write_grid_csv(xs, ys, zs, grid_path)
    options = dict(plot_options)
    options["color_map"] = default_color_map_direction(
        options.get("color_map", "RdBu"), reverse=not success_pattern
    )
    plot_fn(
        xs, ys, zs,
        labels=("Precipitation Delta (%)", "Temperature Delta (C)", Z_LABEL),
        title=component_name,
        save_path=plot_path,
        show=False,
        **options,
    )
    return written + [grid_path, plot_path]
