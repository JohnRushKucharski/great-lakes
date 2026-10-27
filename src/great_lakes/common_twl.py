"""Shared helpers for reading `<lake>_twl.xlsx` workbooks and `<avg-lake>_avg.csv` files.

Used by both batch_run_twl.py (evaluates twl frequency curves against a resource's
magnitude threshold) and fillin_twl.py (estimates missing scenario sheets via
Delaunay-linear interpolation and row-shift extrapolation). Factored out here rather
than duplicated, or imported one from the other, since neither script is a natural
"owner" of the other's logic.
"""

from functools import lru_cache
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
from climate_canvas.data_utilities import contour_levels  # type: ignore[import-untyped]
from matplotlib.colors import Normalize

# lake code -> twl xlsx filename, shared by data/clean/ and data/filled/ (directory
# alone disambiguates the two). Only 4 lakes have twl data (michigan and huron are
# separate files here, unlike batch_run_avg.py's combined "michiganhuron"; stclair/erie
# have no twl data at all).
LAKE_TWL_FILENAMES = {
    "superior": "superior_twl.xlsx",
    "michigan": "michigan_twl.xlsx",
    "huron": "huron_twl.xlsx",
    "ontario": "ontario_twl.xlsx",
}

# twl-lake code -> avg-lake key. Michigan and Huron are one hydraulically-connected
# lake body sharing a single average-lake-level record, despite having separate twl
# workbooks/codes above (see docs/adr/0001-row-shift-extrapolation-for-out-of-hull-
# scenarios.md for why this matters: extrapolation shifts a twl sheet by a delta in
# *average lake level*, which must come from the correct shared record for Michigan
# and Huron).
TWL_LAKE_TO_AVG_LAKE = {
    "superior": "superior",
    "michigan": "michiganhuron",
    "huron": "michiganhuron",
    "ontario": "ontario",
}

# avg-lake key -> average-lake-level csv filename (see
# data/raw/clean_lake_levels_all_scenarios.py, which produces these files; stclair and
# erie also exist there but have no corresponding twl data, so are omitted here).
LAKE_AVG_FILENAMES = {
    "superior": "superior_avg.csv",
    "michiganhuron": "michiganhuron_avg.csv",
    "ontario": "ontario_avg.csv",
}

# Sheet columns that are not ARI (Average Return Interval) values.
NON_ARI_COLUMNS = frozenset({"ID", "lat", "lon"})

# Plain SI meters->feet scale, used by the great_lakes.analysis response-surface
# scripts to convert raw twl/avg-level *data values* (not elevations already tied to
# a specific vertical datum) to feet. Deliberately distinct from
# m_igld85_to_ft_NAVD88's 1/3.281 factor below, which matches how longtailpoint's own
# resources sheets were populated -- these two conversions serve different data and
# must not be confused/merged.
METERS_TO_FEET = 1.0 / 0.3048

# Meters per foot, and the flat IGLD85->NAVD88 offset (in feet) used throughout the
# Great Lakes example data (see longtailpoint/longtail_waterlevel
# .xlsx, Sheet2's "NAVD88 to IGLD85" table: NAVD88 587ft -> IGLD85 586.56ft, NAVD88
# 582ft -> IGLD85 581.56ft -- both a flat -0.44ft offset, i.e. IGLD85_ft = NAVD88_ft -
# 0.44, so NAVD88_ft = IGLD85_ft + 0.44. This is the "USACE team estimate" noted in
# that workbook's conversion_ex sheet; it is *not* the slightly different computed
# ~0.4093ft offset, which the workbook explicitly says was not used).
#
# The meters<->feet scale factor is 1/3.281 (i.e. 1 m = 3.281 ft), matching how the
# longtailpoint resources sheets' magnitude_value column was populated -- NOT the
# exact 0.3048 m/ft conversion. The two differ by ~1.5e-5 m per ft, which compounds to
# a few hundredths of a foot at these magnitudes; using the same factor as the
# resources sheets keeps round-trips consistent with the source data.
_METERS_PER_FOOT = 1.0 / 3.281
_IGLD85_TO_NAVD88_OFFSET_FT = 0.44


def m_igld85_to_ft_NAVD88(value_m_igld85: float) -> float:
    """Convert an elevation in meters, IGLD85 datum, to feet, NAVD88 datum."""
    ft_igld85 = value_m_igld85 / _METERS_PER_FOOT
    return ft_igld85 + _IGLD85_TO_NAVD88_OFFSET_FT


def ft_NAVD88_to_m_igld85(value_ft_NAVD88: float) -> float:
    """Convert an elevation in feet, NAVD88 datum, to meters, IGLD85 datum.

    Inverse of m_igld85_to_ft_NAVD88 -- used to translate a NAVD88-ft input (e.g. an
    equivalent_elevation override expressed in NAVD88 feet) into the meters-IGLD85
    value the rest of the pipeline (twl curves, magnitude_value) operates in.
    """
    ft_igld85 = value_ft_NAVD88 - _IGLD85_TO_NAVD88_OFFSET_FT
    return ft_igld85 * _METERS_PER_FOOT


# longtailpoint-specific wave-runup allowance, in feet, per component_name code (see
# CONTEXT.md's "Runup allowance" definition). Used by output_file_stem below to render
# a human-readable output filename instead of the raw code.
RUNUP_FT_BY_COMPONENT: dict[str, float] = {
    "base": 0.0,
    "run2": 2.0,
    "run25": 2.5,
    "run3": 3.0,
}


def _format_ft_fixed2(value: float) -> str:
    """Render a ft value with exactly 2 decimals, "." replaced by "d" (filename-safe),
    e.g. 586.4749 -> "586d47", 586.0 -> "586d00". Used for the elevation part of
    output_file_stem, which always keeps both decimals even when trailing zero.
    """
    return f"{value:.2f}".replace(".", "d")


def _format_ft_trim(value: float) -> str:
    """Render a ft value with as many decimals as needed (no trailing zeros), "."
    replaced by "d", and no decimal point at all for whole numbers (e.g. 2.5 -> "2d5",
    3.0 -> "3", 0.0 -> "0").
    """
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    if text in ("", "-"):
        text = "0"
    return text.replace(".", "d")


def output_file_stem(magnitude_ft: float, component_name: str, save_point_id: object) -> str:
    """Build the human-readable output-filename stem for one longtailpoint twl resource
    row: "<elevation>ft_plus<runup>ft-runup_savepoint<id>".

    magnitude_ft is the resource's magnitude_value already converted to ft, NAVD88
    (see m_igld85_to_ft_NAVD88) -- always rendered with exactly 2 decimals (e.g.
    586.0 -> "586d00ft"). component_name is looked up in RUNUP_FT_BY_COMPONENT to get
    the runup allowance in ft -- rendered with only as many decimals as needed, no
    trailing zero (e.g. 0.0 -> "0ft", 2.5 -> "2d5ft", 3.0 -> "3ft"). Raises ValueError
    for any component_name not in RUNUP_FT_BY_COMPONENT, rather than silently falling
    back to the raw code.

    This is purely a filename-formatting concern -- it does not replace
    ResourceSpec.qualified_name, which remains the internal identifier used for
    logging, collision detection, and dashboard identity/labels.
    """
    if component_name not in RUNUP_FT_BY_COMPONENT:
        raise ValueError(
            f"Unknown runup component_name {component_name!r}; expected one of "
            f"{sorted(RUNUP_FT_BY_COMPONENT)}."
        )
    runup_ft = RUNUP_FT_BY_COMPONENT[component_name]
    elevation_label = _format_ft_fixed2(magnitude_ft)
    runup_label = _format_ft_trim(runup_ft)
    return f"{elevation_label}ft_plus{runup_label}ft-runup_savepoint{save_point_id}"


def output_file_stem_savepoint_elevation_runup(
    magnitude_ft: float, component_name: str, save_point_id: object
) -> str:
    """Build the "<save point>_<elevation>_<runup>" output-filename stem: save point ID
    first, then the combined elevation (magnitude_ft + this component_name's runup
    allowance, "d" for the decimal point, always 2 decimals), then the runup allowance
    alone (also "d" for decimal, always 2 decimals).

    component_name is looked up in RUNUP_FT_BY_COMPONENT for the runup allowance in ft;
    raises ValueError for any component_name not in RUNUP_FT_BY_COMPONENT, same as
    output_file_stem.
    """
    if component_name not in RUNUP_FT_BY_COMPONENT:
        raise ValueError(
            f"Unknown runup component_name {component_name!r}; expected one of "
            f"{sorted(RUNUP_FT_BY_COMPONENT)}."
        )
    runup_ft = RUNUP_FT_BY_COMPONENT[component_name]
    elevation_ft = magnitude_ft + runup_ft
    elevation_label = _format_ft_fixed2(elevation_ft)
    runup_label = _format_ft_fixed2(runup_ft)
    return f"{save_point_id}_{elevation_label}_{runup_label}"


# Maps build_resource_outputs' internal plot kinds to the human-readable "type" label
# used in build_plot_title's first line.
PLOT_TITLE_TYPE_LABELS: dict[str, str] = {
    "primary": "Overtopping Frequency",
    "equivalent_elevation": "Elevation Equivalents",
    "elevation_delta": "Elevation Delta",
}


def build_plot_title(
    plot_kind: str, magnitude_ft: float, component_name: str, save_point_id: object,
    baseline_ari: float | None = None,
) -> str:
    """Build a plot title for one longtailpoint twl resource's response-surface plot.

    3-line default:

        Longtail Point <type>
        elevation: <elevation> ft (NAVD88), runup: <runup> ft
        save point: <save_point_id>

    4-line when plot_kind is "equivalent_elevation" or "elevation_delta" and
    baseline_ari is given (a "baseline ARI: <value> yr" line is inserted between the
    elevation/runup line and the save point line -- the baseline scenario's
    interpolated ARI at the resource's equivalent_elevation lookup value, i.e. what
    every scenario's equivalent elevation/elevation delta is computed relative to):

        Longtail Point <type>
        elevation: <elevation> ft (NAVD88), runup: <runup> ft
        baseline ARI: <baseline_ari> yr
        save point: <save_point_id>

    plot_kind selects the "<type>" label via PLOT_TITLE_TYPE_LABELS -- one of
    "primary" ("Overtopping Frequency"), "equivalent_elevation" ("Elevation
    Equivalents"), or "elevation_delta" ("Elevation Delta"). Raises ValueError for any
    other plot_kind.

    magnitude_ft is the resource's magnitude_value already converted to ft, NAVD88 (see
    m_igld85_to_ft_NAVD88). component_name is looked up in RUNUP_FT_BY_COMPONENT for
    the runup allowance in ft; elevation is magnitude_ft + that runup allowance (the
    actual crest elevation being evaluated, not the raw magnitude alone). Raises
    ValueError for any component_name not in RUNUP_FT_BY_COMPONENT.

    baseline_ari has no effect for plot_kind="primary" (the primary plot has no
    equivalent_elevation lookup to report an ARI for) -- it always stays 3 lines,
    even if a caller passes baseline_ari anyway.

    All lines render at Axes.set_title's one implicit font size: matplotlib
    mathtext (unlike real LaTeX) has no \\Large/\\small size macros to vary size
    per-line within a single title string, so a uniform size is used instead.
    """
    if plot_kind not in PLOT_TITLE_TYPE_LABELS:
        raise ValueError(
            f"Unknown plot_kind {plot_kind!r}; expected one of "
            f"{sorted(PLOT_TITLE_TYPE_LABELS)}."
        )
    if component_name not in RUNUP_FT_BY_COMPONENT:
        raise ValueError(
            f"Unknown runup component_name {component_name!r}; expected one of "
            f"{sorted(RUNUP_FT_BY_COMPONENT)}."
        )
    runup_ft = RUNUP_FT_BY_COMPONENT[component_name]
    elevation_ft = magnitude_ft + runup_ft
    type_label = PLOT_TITLE_TYPE_LABELS[plot_kind]
    line1 = f"Longtail Point {type_label}"
    line2 = f"elevation: {elevation_ft:g} ft (NAVD88), runup: {runup_ft:g} ft"
    save_point_line = f"save point: {save_point_id}"
    if plot_kind in ("equivalent_elevation", "elevation_delta") and baseline_ari is not None:
        baseline_ari_line = f"baseline ARI: {baseline_ari:g} yr"
        return f"{line1}\n{line2}\n{baseline_ari_line}\n{save_point_line}"
    return f"{line1}\n{line2}\n{save_point_line}"


def build_threshold_ari_title(threshold_ari: float, save_point_id: object) -> str:
    """Build a plot title for one save point's threshold-ARI elevation plot (see
    CONTEXT.md's "Threshold-ARI elevation" entry).

    3-line title:

        Longtail Point Threshold ARI Elevation
        ARI: <threshold_ari> yr
        save point: <save_point_id>

    Unlike build_plot_title, this plot has no single magnitude/runup component to
    describe (it's computed once per save point, shared across every resource row
    sharing that save point), so there's no elevation/runup line -- just the target
    ARI itself.
    """
    return (
        "Longtail Point Threshold ARI Elevation\n"
        f"ARI: {threshold_ari:g} yr\n"
        f"save point: {save_point_id}"
    )


# ---- shared response-surface contour/color-style helpers ---------------------------

def one_sided_color_style(
    z_range: tuple[float, float], threshold: float
) -> tuple[str, Normalize, tuple[float, ...], tuple[float, ...]] | None:
    """When every grid cell falls on one side of `threshold`, climate_canvas's default
    RdBu/TwoSlopeNorm can't place `threshold` at its usual colorbar center
    (TwoSlopeNorm requires vmin < vcenter < vmax) -- it silently falls back to the
    *data range's own midpoint* instead (see climate_canvas.data_utilities.
    check_threshold), which breaks the "colorbar center = threshold" convention.

    Returns None when threshold falls strictly inside z_range (the normal, two-sided
    case) -- callers should keep climate_canvas's default RdBu diverging behavior.
    Otherwise returns (color_map, norm, levels, widths) for a one-sided sequential
    scale anchored at `threshold`:
    - every cell <= threshold: 'Reds_r' colormap, lightest (white) at `threshold`,
      darkest red at the grid's most extreme (lowest) value.
    - every cell >= threshold: 'Blues' colormap, lightest at `threshold`, darkest blue
      at the grid's most extreme (highest) value.

    levels/widths mark `threshold` plus 5 evenly-spaced points between it and the
    extreme (bold at threshold, matching the normal RdBu contour convention) -- these
    also make sensible colorbar ticks. Ported from
    data/analysis/avg/plot_avg_levels.py's original
    (tail-specific) implementation, generalized here to infer direction purely from
    where the data falls relative to threshold rather than a caller-supplied tail
    label, so it applies uniformly to any response-surface plot.
    """
    z_min, z_max = z_range
    if z_min < threshold < z_max:
        return None
    if z_max <= threshold:
        extreme, color_map = z_min, "Reds_r"
    elif z_min >= threshold:
        extreme, color_map = z_max, "Blues"
    else:
        return None
    mids = [threshold + i * (extreme - threshold) / 6 for i in range(1, 6)]
    ascending = sorted([extreme, threshold] + mids)
    widths = tuple(2.0 if lvl == threshold else 1.0 for lvl in ascending)
    return (
        color_map,
        Normalize(vmin=min(threshold, extreme), vmax=max(threshold, extreme)),
        tuple(ascending),
        widths,
    )


def rounded_levels(
    z_range: tuple[float, float], threshold: float, decimals: int = 2
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """climate_canvas's default contour levels/widths (5 evenly-spaced below/above
    threshold, per contour_levels), rounded to `decimals` places.

    Used where a response-surface's z-values are in feet and contour lines/colorbar
    ticks should land on "nice" values (e.g. nearest 0.01 ft) instead of whatever
    fractional value evenly-spacing the raw data range happens to produce.
    """
    levels, widths = contour_levels(z_range, threshold)
    return tuple(round(level, decimals) for level in levels), widths


def symmetric_delta_levels(
    z_range: tuple[float, float], small_step: float = 0.1, big_step: float = 0.25,
    half_count: int = 5,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Contour levels/widths for an elevation-delta plot: a symmetric ladder of steps
    centered on 0.0, aiming for `half_count` steps on each side (~2*half_count+1 levels
    total, matching climate_canvas's usual default of 11).

    Picks `small_step` (0.1 ft) if the data's largest absolute value fits within
    `half_count` steps of that size; otherwise falls back to `big_step` (0.25 ft). If
    even `big_step` can't cover the data within `half_count` steps, the level count is
    grown (spacing stays at `big_step`) until it does -- so the plot may show more than
    2*half_count+1 levels for an unusually wide delta range, but the center stays at 0
    and the step size stays "nice" instead of being reduced further.
    """
    max_abs = max(abs(z_range[0]), abs(z_range[1]))
    if max_abs <= half_count * small_step:
        step, n = small_step, half_count
    else:
        step, n = big_step, max(half_count, ceil(max_abs / big_step))
    levels = tuple(round(i * step, 10) for i in range(-n, n + 1))
    widths = tuple(2.0 if level == 0.0 else 1.0 for level in levels)
    return levels, widths


def colorbar_ticks_within_range(
    levels: tuple[float, ...], z_range: tuple[float, float]
) -> tuple[float, ...]:
    """Filter `levels` down to only those that fall within `z_range` (inclusive), for
    safe use as climate_canvas's plot_response_surface(color_map_ticks=...).

    symmetric_delta_levels() (and, in principle, any other level-generating function
    not itself bounded by z_range) can return levels well outside the plotted data's
    actual z_range -- e.g. a symmetric +-7 ladder when the data only spans -6.91 to
    2.24. Passing an out-of-range tick to matplotlib's colorbar (via cbar.set_ticks)
    breaks the colorbar's rendering entirely (a blank/white bar, not just a missing
    tick) -- this was the root cause of the "blank elevation-delta colorbar" defect.
    Contour *levels* (drawn via ax.contour) are unaffected by out-of-range values (the
    contour simply never appears), so only the color_map_ticks use needs filtering --
    callers should keep passing the unfiltered levels for the `levels`/`widths`
    contour-drawing arguments.
    """
    z_min, z_max = z_range
    return tuple(lvl for lvl in levels if z_min <= lvl <= z_max)


# Human-readable per-style description used by naming_scheme_readme_text -- one section
# body per _VALID_FILENAME_STYLES value that has a pattern worth documenting (the
# generic "qualified_name" style needs no README since it's just resource_name +
# component_name, self-explanatory).
_NAMING_SCHEME_README_BODIES: dict[str, str] = {
    "elevation_runup_savepoint": (
        "Output filename pattern: <elevation>ft_plus<runup>ft-runup_savepoint<save "
        "point ID>...\n\n"
        "  elevation - the resource's magnitude value, converted to feet, NAVD88 "
        "datum. Always shown with exactly 2 decimals, with \"d\" standing in for "
        "the decimal point (filenames can't contain \".\" safely on every "
        "platform), e.g. 586d47 means 586.47 ft.\n"
        "  runup     - the wave-runup allowance for this row's component, in feet, "
        "NAVD88 datum. Shown with only as many decimals as needed (no trailing "
        "zero), \"d\" for the decimal point, e.g. 2d5 means 2.5 ft.\n"
        "  save point ID - the save point identifier the row was evaluated at.\n"
    ),
    "savepoint_elevation_runup": (
        "Output filename pattern: <save point ID>_<elevation>_<runup>...\n\n"
        "  save point ID - the save point identifier the row was evaluated at.\n"
        "  elevation - the actual crest elevation being evaluated: the resource's "
        "magnitude value plus its runup allowance (both converted to feet, NAVD88 "
        "datum), combined. Always shown with exactly 2 decimals, with \"d\" "
        "standing in for the decimal point (filenames can't contain \".\" safely "
        "on every platform), e.g. 585d50 means 585.50 ft.\n"
        "  runup     - the wave-runup allowance alone, in feet, NAVD88 datum, also "
        "with exactly 2 decimals and \"d\" for the decimal point, e.g. 2d50 means "
        "2.50 ft.\n"
    ),
}


def naming_scheme_readme_text(filename_style: str) -> str:
    """Build the plain-text README content explaining one output directory's
    filename_style naming scheme, including the NAVD88 datum and feet units.

    Raises ValueError for any filename_style not in _NAMING_SCHEME_README_BODIES
    (i.e. one with no dedicated naming convention worth documenting).
    """
    if filename_style not in _NAMING_SCHEME_README_BODIES:
        raise ValueError(
            f"Unknown filename_style {filename_style!r} for a naming-scheme README; "
            f"expected one of {sorted(_NAMING_SCHEME_README_BODIES)}."
        )
    header = "Output filename naming scheme for this directory\n" + "=" * 50 + "\n\n"
    return header + _NAMING_SCHEME_README_BODIES[filename_style]


def resolve_lake_twl_path(lake: str, data_dir: Path) -> Path:
    """Resolve a lake code to its twl xlsx path under data_dir."""
    return data_dir / LAKE_TWL_FILENAMES[lake]


def resolve_lake_avg_path(lake: str, data_dir: Path) -> Path:
    """Resolve a twl-lake code (e.g. "michigan") to its average-lake-level csv path.

    Looks up the shared avg-lake key first (TWL_LAKE_TO_AVG_LAKE), since michigan and
    huron share one avg csv (michiganhuron_avg.csv) despite having separate twl
    workbooks.
    """
    avg_lake = TWL_LAKE_TO_AVG_LAKE[lake]
    return data_dir / LAKE_AVG_FILENAMES[avg_lake]


def parse_scenario_sheet_name(sheet_name: str) -> str | None:
    """Parse a twl workbook sheet name into its bare scenario-grid suffix.

    Sheet names follow the `<label>-_<precip_delta>_<temp_delta>` convention (e.g.
    `baseline-_0_0`, `moderate_low-_10_5` -- note the label itself may contain
    underscores, so splitting is done on the first `-` only, not `_`). Returns the
    `_<precip_delta>_<temp_delta>` suffix (e.g. `_0_0`), suitable for
    hydropattern.scenario_grid's naming convention. Returns None if sheet_name does not
    match this convention (no `-` separator, blank label, or blank/missing suffix).
    """
    if "-" not in sheet_name:
        return None
    label, _, suffix = sheet_name.partition("-")
    if not label or not suffix:
        return None
    return suffix


def center_save_point_id(sheets: dict[str, pd.DataFrame]) -> int:
    """Return the ID of the save point nearest a twl workbook's lat/lon centroid.

    Uses the first sheet's lat/lon columns -- identical across every known sheet in
    a `<lake>_twl.xlsx` workbook, so any one of them would do. Shared by
    great_lakes.analysis's twl scripts (plot_center_save_points.py,
    plot_filled_and_extrapolated.py, compare_filled_vs_climate_canvas.py), which
    each pick this same centroid save point per lake before plotting/comparing its
    water-level-vs-ARI curve.
    """
    baseline = next(iter(sheets.values()))
    centroid_lat, centroid_lon = baseline["lat"].mean(), baseline["lon"].mean()
    lat_diff, lon_diff = baseline["lat"] - centroid_lat, baseline["lon"] - centroid_lon
    dist = (lat_diff**2 + lon_diff**2) ** 0.5
    return int(baseline.loc[dist.idxmin(), "ID"])  # type: ignore[arg-type]


def build_scenario_ari_grid(
    coords: dict[str, tuple[float, float]],
    sheets: dict[str, pd.DataFrame],
    save_point_id: int,
    ari: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build the (precip x, temp y, TWL-in-feet z) response-surface grid for one save
    point/ARI column, over exactly the scenario coordinate space given by `coords`.

    `coords` controls which scenarios the grid spans -- pass the 5-known-scenario
    coordinates (known_scenario_coords) for a known-only grid (blank elsewhere), or
    the full 17-scenario coordinates (parse_scenario_name over
    fillin_twl.ALL_SCENARIO_SUFFIXES) for a full grid (blank only where `sheets` is
    missing a scenario, e.g. data/filled/'s 5 out-of-hull gaps). Any sheet in
    `sheets` whose parsed suffix isn't a key of `coords` is ignored -- this lets
    callers pass the same full `sheets` dict regardless of which coordinate space
    they want plotted.

    z is shaped (len(temps), len(precips)), NaN for any coordinate with no matching
    sheet or no row for `save_point_id`.
    """
    precips = sorted({p for p, _ in coords.values()})
    temps = sorted({t for _, t in coords.values()})

    z = np.full((len(temps), len(precips)), np.nan)
    for sheet_name, df in sheets.items():
        suffix = parse_scenario_sheet_name(sheet_name)
        if suffix not in coords:
            continue
        precip, temp = coords[suffix]
        row = df.loc[df["ID"] == save_point_id, ari]
        if row.empty:
            continue
        z[temps.index(temp), precips.index(precip)] = row.iloc[0] * METERS_TO_FEET

    return np.array(precips, dtype=float), np.array(temps, dtype=float), z


@lru_cache(maxsize=None)
def load_lake_sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Read every sheet of a `<lake>_twl.xlsx` workbook into {sheet_name: DataFrame}.

    Cached per path: twl workbooks are large (~20k save-point rows), and a batch run
    commonly needs the same lake's data more than once, so re-reading per call would
    be wasteful.
    """
    return pd.read_excel(path, sheet_name=None, engine="calamine")


@lru_cache(maxsize=None)
def read_avg_scenario_means(lake: str, data_dir: Path) -> dict[str, float]:
    """Read a lake's average-lake-level csv and return each scenario's mean level.

    Returns {scenario_suffix: mean}, one entry per non-"time" column (e.g.
    {"_0_0": 183.3, "_5_7": 182.9, ...}). The mean is taken over the *entire* synthetic
    scenario record (~12,360 monthly rows spanning 1970-2999), not a calendar
    sub-period -- see docs/adr/0001-row-shift-extrapolation-for-out-of-hull-
    scenarios.md, which uses this as AVG(l, s) in its shift-extrapolation math.

    Cached per (lake, data_dir): the avg csvs are ~12,360 rows x 17 columns, and a
    fill run needs the same lake's means only once but may be looked up from more than
    one place (e.g. once per out-of-hull target scenario).
    """
    path = resolve_lake_avg_path(lake, data_dir)
    frame = pd.read_csv(path)
    return {column: float(frame[column].mean()) for column in frame.columns if column != "time"}
