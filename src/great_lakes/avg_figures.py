"""avg mean-level figures: mean average lake level vs precip and temp climate deltas.

One figure per lake (all five avg lakes). Cells are the 17 scenarios' mean levels over
the whole synthetic record; the colour scale is centred on the baseline (`_0_0`) mean.
Rendering is shared with the swl figures (`great_lakes.swl.figures`).
"""

from pathlib import Path

import numpy as np
import pandas as pd
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]

from great_lakes import units
from great_lakes.cleaning import avg as clean_avg
from great_lakes.paths import Layout
from great_lakes.swl import figures
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES

AVG_LAKES = tuple(name.removesuffix("_avg.csv") for name in clean_avg.LAKES.values())

_ALL_COORDS = {suffix: parse_scenario_name(suffix) for suffix in ALL_SCENARIO_SUFFIXES}
_PRECIPS = sorted({p for p, _ in _ALL_COORDS.values()})
_TEMPS = sorted({t for _, t in _ALL_COORDS.values()})


def _convert(meters_igld85: float, to_units: units.Units, to_datum: units.Datum) -> float:
    value = units.convert_units(meters_igld85, "m", to_units)
    return float(units.convert_datum(value, "IGLD85", to_datum, to_units))


def build_mean_grid(
    columns: dict[str, np.ndarray],
    to_units: units.Units = figures.DEFAULT_UNITS,
    to_datum: units.Datum = figures.DEFAULT_DATUM,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(precip x, temp y, mean level z) over the 17-scenario space, NaN for absent scenarios.

    `columns` maps scenario suffix to monthly levels (meters, IGLD85).
    """
    z = np.full((len(_TEMPS), len(_PRECIPS)), np.nan)
    for suffix, values in columns.items():
        if suffix in _ALL_COORDS:
            precip, temp = _ALL_COORDS[suffix]
            z[_TEMPS.index(temp), _PRECIPS.index(precip)] = _convert(
                float(np.mean(values)), to_units, to_datum)
    return np.array(_PRECIPS, dtype=float), np.array(_TEMPS, dtype=float), z


def write_avg_figures(
    layout: Layout,
    lake_names: tuple[str, ...] = AVG_LAKES,
    to_units: units.Units = figures.DEFAULT_UNITS,
    to_datum: units.Datum = figures.DEFAULT_DATUM,
) -> list[Path]:
    """Write each lake's mean-level figure (raw grid, plus an interpolated companion).

    The default units and datum (ft, NAVD88) also write the tracked
    `data/avg/figures/<lake>.png`; any other choice writes only under
    `<bulk figures>/<units>_<datum>/`. Returns the files written.
    """
    is_default = (to_units, to_datum) == (figures.DEFAULT_UNITS, figures.DEFAULT_DATUM)
    bulk_dir = layout.avg_bulk_figures if is_default else (
        layout.avg_bulk_figures / f"{to_units}_{to_datum}")
    labels = ("precip_delta", "temp_delta",
              units.water_level_label(to_units, to_datum, "Mean water level"))
    written: list[Path] = []
    for lake in lake_names:
        frame = pd.read_csv(layout.avg / f"{lake}_avg.csv")
        columns = {c: frame[c].to_numpy(dtype=float) for c in frame.columns if c != "time"}
        xs, ys, zs = build_mean_grid(columns, to_units, to_datum)
        threshold = _convert(float(np.mean(columns["_0_0"])), to_units, to_datum)
        title = (f"{lake.capitalize()} mean level "
                 f"(baseline avg = {threshold:.2f} {to_units}, {to_datum})")
        surface = figures.Surface(xs, ys, zs, title)

        targets = [(bulk_dir / f"{lake}.png", False),
                   (bulk_dir / "interpolated" / f"{lake}.png", True)]
        if is_default:
            targets.insert(0, (layout.avg_figures / f"{lake}.png", False))
        for path, interpolate in targets:
            fig = figures.build_standalone_figure(surface, labels, threshold, interpolate)
            written.append(figures.save_figure(fig, path))
    return written
