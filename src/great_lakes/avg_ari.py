"""Plot Poisson-method ARI response surfaces for average lake levels.

(The mean-level figures live in great_lakes.avg_figures.)

For each of the 3 distinct average-lake-level datasets in `data/avg/` --
superior, michiganhuron (Michigan and Huron are one hydraulically-connected lake
and share a single avg-level dataset), ontario -- and each of the 17 precip/temp
scenarios in that dataset's monthly time series (1970-2999, 1030 years), this
computes the average lake level associated with the SWL workbooks' ARI values that
   are >= 1 year (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000 -- see
   ari.SWL_ARIS; the <1-year SWL ARI values, 0.1/0.2/0.5, are dropped
   here -- see "Why ARI < 1 is dropped" below), for both the high-water tail
   (level exceeded on average once every ARI years) and the low-water tail
   (level undershot on average once every ARI years), using the
   Poisson/peaks-over-threshold method described in
   `analyses/avg-statistics/methods/avg_ari_poisson_method.md` --
   NOT the annual-maximum-series (block maxima) method. Two variants:
   - non-declustered ("clustered"): every monthly value is treated as a Poisson-
     arrival candidate -> `ari/clustered/high/<lake>_<ari>.png`,
     `ari/clustered/low/<lake>_<ari>.png`.
   - declustered: only local turning points (peaks for the high tail, troughs
     for the low tail) of the monthly series are treated as candidates, so a
     multi-year high/low-water episode isn't counted as many separate "events"
     -> `ari/declustered/high/<lake>_<ari>.png`, `ari/declustered/low/<lake>_<ari>.png`.

Each of the plots above also gets a companion `interpolated/<name>.png` (in a
sibling `interpolated/` subfolder alongside the raw plot) using climate_canvas's
own `interpolate=True, fillin=True` (matching the SWL plots' convention) --
resampled to a finer grid; since the avg data already has every one of the 17
scenarios (no NaN cells to begin with), this only resamples, it never needs the
Delaunay fillin fallback.

All plots are response surfaces over the full 17-scenario precip/temp grid,
values converted from meters to feet, with the baseline (`_0_0`) scenario's
mean average lake level (in feet) as both the diverging-colormap threshold and
shown in the title as "baseline average lake level=".

## Why ARI < 1 is dropped, and why ARI=1 is replaced

The Poisson method's target annual exceedance probability is `aep = 1/ari`.
`aep` is a probability, so it must be <= 1, which requires `ari >= 1` -- ARI
values below 1 year (like the SWL data's 0.1/0.2/0.5) are mathematically
undefined here, for *either* population (non-declustered or declustered): they
don't reflect data limitations, they reflect `aep` no longer being a valid
probability. (SWL's own <1-year ARI columns are fine -- they're precomputed by
a different, already-tabulated method upstream, not derived through this
Poisson inversion.)

Even ARI=1 itself is only a hair inside the valid range: it requires
`aep = 1.0` exactly, which needs an infinite Poisson rate, which no finite
population can supply. This implementation caps the required rate at the
population's own size, giving the population's raw extreme value as the
answer whenever the target is at or beyond what the population can achieve.
For the non-declustered population (fixed at 12 values/year for every
scenario), that ceiling is at ARI~=1.000006 years -- so close to 1 that it barely
matters. For the declustered population (roughly one peak/trough per year from
the lakes' seasonal cycle), that ceiling is much further out, more like
ARI~=1.7-1.9 years -- so declustered ARI=1 is a real, not just theoretical,
degenerate case (see `analyses/avg-statistics/methods/avg_ari_poisson_method.md`).

Rather than plot a possibly-meaningless capped ARI=1 result, this instead
computes, per (lake, tail, declustered-or-not), the single highest (i.e.
worst-case, most restrictive) minimum-achievable ARI across all 17 scenarios,
and uses that -- instead of the literal value 1 -- as the smallest ARI in the
plotted set, applied uniformly to every scenario cell in that response surface
(so the whole plot stays one consistent, single-ARI comparison instead of each
cell secretly showing a different return period).

Run it with `analyses/avg-statistics/scripts/plot_ari_surfaces.py`.
"""

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from climate_canvas.plots_utilities import plot_response_surface  # type: ignore[import-untyped]
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]

from great_lakes import units
from great_lakes.ari import SWL_ARIS, format_ari
from great_lakes.batch import run_readme
from great_lakes.swl import contours
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES

# ARI=1's target aep=1/1=1.0 is only reachable in the theoretical limit (needs
# infinite Poisson rate); ARI<1 needs aep>1, which isn't a valid probability at
# all. Drop ARI<1; ARI=1 itself is replaced per-lake/tail/decluster below with
# the actual minimum achievable ARI (see module docstring).
AVG_ARIS = tuple(ari for ari in SWL_ARIS if ari >= 1.0)

# The 3 distinct avg-level datasets (Michigan and Huron share one; see
# lakes.LAKE_AVG_FILENAMES).
AVG_LAKES = ("superior", "michiganhuron", "ontario")

ALL_COORDS = {suffix: parse_scenario_name(suffix) for suffix in ALL_SCENARIO_SUFFIXES}
ALL_PRECIPS = sorted({p for p, _ in ALL_COORDS.values()})
ALL_TEMPS = sorted({t for _, t in ALL_COORDS.values()})


def local_turning_points(values: np.ndarray, kind: str) -> np.ndarray:
    """Indices of local peaks (kind="peak") or troughs (kind="trough") in `values`.

    A peak is a point strictly greater than both its neighbors (or its one
    neighbor, at the series' boundary); a trough is strictly less. These are
    threshold-independent "events" -- identified from the series' shape alone,
    not from where a candidate ARI level happens to fall -- so counting how many
    of them exceed/undershoot a candidate level doesn't double-count a single
    multi-month excursion. See docs/avg_level_ari_poisson_method.md.
    """
    v = -values if kind == "trough" else values
    n = len(v)
    is_turning = np.zeros(n, dtype=bool)
    is_turning[1:-1] = (v[1:-1] > v[:-2]) & (v[1:-1] > v[2:])
    is_turning[0] = v[0] > v[1]
    is_turning[-1] = v[-1] > v[-2]
    return np.nonzero(is_turning)[0]


def population_for(values_ft: np.ndarray, tail: str, decluster: bool) -> np.ndarray:
    """The candidate population used for the Poisson rate: every monthly value
    (decluster=False), or just its local peaks/troughs (decluster=True).
    """
    if not decluster:
        return values_ft
    idx = local_turning_points(values_ft, "peak" if tail == "high" else "trough")
    return values_ft[idx]


def min_achievable_ari(columns: dict[str, np.ndarray], tail: str, decluster: bool) -> float:
    """Highest (worst-case/most-restrictive) minimum achievable ARI across all
    17 scenarios for this (tail, decluster) combination -- i.e. 1/max_aep for
    whichever scenario's population has the fewest members (the sparsest
    events), so a single ARI value is valid to apply uniformly across the
    whole response-surface grid. See module docstring.
    """
    worst_ari = 1.0
    for suffix, values in columns.items():
        if suffix not in ALL_COORDS:
            continue
        values_ft = units.convert_units(values, "m", "ft")
        years = len(values_ft) / 12.0
        population = population_for(values_ft, tail, decluster)
        n = len(population)
        max_aep = 1.0 - np.exp(-n / years)
        worst_ari = max(worst_ari, 1.0 / max_aep)
    return worst_ari


def poisson_ari_level(population: np.ndarray, ari: float, years: float, tail: str) -> float:
    """Empirical Poisson-process ARI level for `tail` ("high" or "low").

    See docs/avg_level_ari_poisson_method.md for the derivation. Summary: target annual exceedance
    probability aep = 1/ari; solve aep = 1-exp(-k/years) for k (the expected
    number of population members exceeding/undershooting the answer over the
    whole record); read the level off the population's k-th order statistic
    (interpolating between order statistics for fractional k). If the required
    k exceeds the population size (aep >= the population's max achievable rate),
    the result is capped at the population's extreme value -- see
    docs/avg_level_ari_poisson_method.md's "ARI=1 edge case" section.
    """
    n = len(population)
    aep = 1.0 / ari
    if aep >= 1.0:
        k = float(n)
    else:
        k = min(years * (-np.log(1.0 - aep)), float(n))
    sorted_pop = np.sort(population)[::-1] if tail == "high" else np.sort(population)
    k_floor = max(1, min(int(np.floor(k)), n))
    k_ceil = max(1, min(int(np.ceil(k)), n))
    if k_floor == k_ceil:
        return float(sorted_pop[k_floor - 1])
    frac = k - k_floor
    return float(sorted_pop[k_floor - 1] * (1 - frac) + sorted_pop[k_ceil - 1] * frac)


def build_grid(columns: dict[str, np.ndarray],
               ari: float, tail: str, decluster: bool) -> tuple[
        np.ndarray, np.ndarray, np.ndarray]:
    """Build (precip x, temp y, z) grid, z = Poisson ARI level, over the full
    17-scenario coordinate space, in feet.
    """
    z = np.full((len(ALL_TEMPS), len(ALL_PRECIPS)), np.nan)
    for suffix, values in columns.items():
        if suffix not in ALL_COORDS:
            continue
        precip, temp = ALL_COORDS[suffix]
        values_ft = units.convert_units(values, "m", "ft")
        years = len(values_ft) / 12.0
        population = population_for(values_ft, tail, decluster)
        z[ALL_TEMPS.index(temp), ALL_PRECIPS.index(precip)] = poisson_ari_level(
            population, ari, years, tail)
    return np.array(ALL_PRECIPS, dtype=float), np.array(ALL_TEMPS, dtype=float), z


def one_sided_color_style(zs: np.ndarray, threshold: float, tail: str) -> tuple | None:
    """Thin tail-gated wrapper around contours.one_sided_color_style (see there for
    the shared math/rationale): only low-tail plots may get the 'Reds_r'
    all-below-threshold treatment, and only high-tail plots may get 'Blues'
    all-above-threshold.
    """
    z_min, z_max = float(np.nanmin(zs)), float(np.nanmax(zs))
    if tail == "low" and not (z_max <= threshold):
        return None
    if tail == "high" and not (z_min >= threshold):
        return None
    return contours.one_sided_color_style((z_min, z_max), threshold)


def _write_pair(xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, title: str,
                directory: Path, filename: str, threshold: float,
                labels: tuple[str, str, str], tail: str) -> tuple[Path, Path]:
    """Write both the raw (interpolate=False) plot and its interpolated
    (interpolate=True, fillin=True) companion into `directory` and
    `directory/interpolated`, both named `<filename>.png`.
    """
    style = one_sided_color_style(zs, threshold, tail)
    color_map = style[0] if style else "RdBu"
    extra = dict(norm=style[1], levels=style[2], widths=style[3]) if style else {}

    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"{filename}.png"
    plot_response_surface(
        xs, ys, zs, interpolate=False, labels=labels, title=title,
        save_path=raw_path, show=False, threshold=threshold, color_map=color_map, **extra,
    )

    interpolated_dir = directory / "interpolated"
    interpolated_dir.mkdir(parents=True, exist_ok=True)
    interpolated_path = interpolated_dir / f"{filename}.png"
    plot_response_surface(
        xs, ys, zs, interpolate=True, fillin=True, labels=labels, title=title,
        save_path=interpolated_path, show=False, threshold=threshold, color_map=color_map, **extra,
    )
    return raw_path, interpolated_path


LEVELS_COLUMNS = ["lake", "tail", "population", "ari", "ari_is_min_floor", "scenario",
                  "precip_delta", "temp_delta", "level_ft"]


def _grid_rows(lake: str, tail: str, population: str, ari: float, is_floor: bool,
               zs: np.ndarray) -> list[dict]:
    """One row per scenario of a (precip x temp) level grid `zs` (see build_grid)."""
    rows = []
    for suffix, (precip, temp) in ALL_COORDS.items():
        rows.append({
            "lake": lake, "tail": tail, "population": population, "ari": ari,
            "ari_is_min_floor": is_floor, "scenario": suffix,
            "precip_delta": precip, "temp_delta": temp,
            "level_ft": float(zs[ALL_TEMPS.index(temp), ALL_PRECIPS.index(precip)]),
        })
    return rows


def run(data_dir: Path, output_dir: Path, lakes: Sequence[str] | None = None,
        aris: Sequence[float] | None = None) -> tuple[Path, ...]:
    """Generate every ARI response-surface plot for every lake in AVG_LAKES, under
    output_dir's ari/<clustered|declustered>/<high|low>/ subfolders
    (each with a sibling interpolated/ subfolder), plus `ari/<lake>_ari_levels.csv`
    holding the plotted levels (feet) as numbers. Returns every file written.

    `lakes` and `aris` restrict the lakes and ARIs plotted (default: AVG_LAKES, AVG_ARIS).
    """
    lakes = AVG_LAKES if lakes is None else tuple(lakes)
    plotted_aris = AVG_ARIS if aris is None else tuple(aris)
    written: list[Path] = []
    for lake in lakes:
        path = data_dir / f"{lake}_avg.csv"
        df = pd.read_csv(path)
        columns = {col: df[col].to_numpy(dtype=float) for col in df.columns if col != "time"}
        baseline_avg_ft = units.convert_units(columns["_0_0"].mean(), "m", "ft")
        level_rows: list[dict] = []

        # ARI plots: high/low tail x declustered/non-declustered ("clustered").
        for tail in ("high", "low"):
            for decluster in (False, True):
                cluster_label = "declustered" if decluster else "clustered"
                subdir = output_dir / "ari" / cluster_label / tail

                # Replace the dropped ARI=1 with this (tail, decluster)
                # combination's actual worst-case minimum achievable ARI,
                # applied uniformly across every scenario in the grid.
                floor_ari = min_achievable_ari(columns, tail, decluster)
                tail_aris = sorted({round(floor_ari, 2)} | {a for a in plotted_aris if a > 1.0})

                for ari in tail_aris:
                    xs, ys, zs = build_grid(columns, ari=ari, tail=tail, decluster=decluster)
                    decl_note = " decl" if decluster else ""
                    ari_label = format_ari(ari)
                    is_floor = ari == round(floor_ari, 2)
                    floor_note = " [min]" if is_floor else ""
                    level_rows.extend(_grid_rows(lake, tail, cluster_label, ari, is_floor, zs))
                    # Kept short (single line) -- a longer title clips at the
                    # figure edge since plot_response_surface doesn't use a
                    # tight savefig bbox.
                    title = (f"{lake.capitalize()} {tail}-water ARI={ari_label}{floor_note}"
                             f"{decl_note} (baseline avg={baseline_avg_ft:.2f} ft)")
                    written.extend(_write_pair(
                        xs, ys, zs, title, subdir, f"{lake}_{ari_label}", baseline_avg_ft,
                        ("precip_delta", "temp_delta", "lake level (ft)"), tail=tail,
                    ))

        csv_path = output_dir / "ari" / f"{lake}_ari_levels.csv"
        pd.DataFrame(level_rows, columns=LEVELS_COLUMNS).to_csv(csv_path, index=False)
        written.append(csv_path)
    return tuple(written)


_NAMING_SCHEME_TEXT = (
    "ari/<lake>_ari_levels.csv - the plotted levels as numbers (feet): one row per "
    "tail, population, ARI and scenario.\n"
    "ari/<clustered|declustered>/<high|low>/<lake>_<ari>.png - Poisson-method ARI "
    "response surface (clustered = every monthly value is a candidate event; "
    "declustered = only local peaks/troughs are).\n"
    "ari/<clustered|declustered>/<high|low>/interpolated/<lake>_<ari>.png - same, "
    "climate_canvas interpolate+fillin resampled.\n"
    "ARI values follow ari.SWL_ARIS restricted to >=1 year; ARI=1 is "
    "replaced per lake/tail/clustered-or-declustered combination by that "
    "combination's actual minimum achievable ARI (flagged '[min]' in the plot "
    "title) -- see this module's docstring for why."
)


def plot_ari_surfaces(data_dir: Path, output_dir: Path, workspace_root: Path,
                      lakes: Sequence[str] | None = None,
                      aris: Sequence[float] | None = None) -> tuple[Path, ...]:
    """Run `run` and write the README.txt run record in `output_dir`; returns files written."""
    lakes = AVG_LAKES if lakes is None else tuple(lakes)
    written = run(data_dir, output_dir, lakes, aris)
    run_readme.write_readme(
        output_directory=output_dir,
        title="Average lake level ARI surfaces report",
        inputs=[(f"{lake} avg csv", data_dir / f"{lake}_avg.csv") for lake in lakes],
        results_text=f"Wrote {len(written)} plot file(s) across {len(lakes)} lake(s).",
        naming_scheme_text=_NAMING_SCHEME_TEXT,
        written_paths=written,
        workspace_root=workspace_root,
    )
    return written

