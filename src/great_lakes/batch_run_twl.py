"""Batch-generate twl (total water level) response-surface plots for Great Lakes resources.

Reads a resources.xlsx template (config sheet + resources sheet) and, for each row of the
resources sheet, evaluates a magnitude-only characteristic against a water-level/ARI
(Average Return Interval) frequency curve -- one curve per save point, per scenario sheet,
in the corresponding lake's `<lake>_twl.xlsx` data file (see data/clean/).

Unlike batch_run_avg.py, this script does NOT generate a hydropattern .toml or invoke
hydropattern.cli: there is no timeseries here (each scenario sheet holds one static
water-level-vs-ARI curve per save point), so hydropattern's Component/Characteristic
evaluation engine -- which operates on per-timestep pandas series -- does not apply. Instead,
each resource row's magnitude threshold is resolved directly against its save point's curve
via linear interpolation across ARI values, and only a response-surface grid csv + plot png
are produced per resource (no raw results, no summary xlsx, no .toml).
"""

import warnings
from dataclasses import dataclass
from math import exp
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
from climate_canvas.plots_utilities import plot_response_surface  # type: ignore[import-untyped]
from hydropattern.cli import _resolve_color_map, write_grid_csv  # type: ignore[import-untyped]
from hydropattern.parsers import MetricMode  # type: ignore[import-untyped]
from hydropattern.scenario_grid import (  # type: ignore[import-untyped]
    build_grid,
    require_scenario_grid,
)

from great_lakes import batch_runner, common_twl
from great_lakes.batch_runner import (  # noqa: F401 -- re-exported for backward compat
    BatchSummary,
    RowResult,
    RowValidationError,
    SheetValidationError,
    _default_progress,
    _is_blank,
    _parse_color_map_ticks,
    _require_str,
    _to_bool,
    format_summary,
)

LAKE_TWL_FILENAMES = common_twl.LAKE_TWL_FILENAMES
resolve_lake_twl_path = common_twl.resolve_lake_twl_path
parse_scenario_sheet_name = common_twl.parse_scenario_sheet_name
_NON_ARI_COLUMNS = common_twl.NON_ARI_COLUMNS
_load_lake_sheets = common_twl.load_lake_sheets
_m_igld85_to_ft_NAVD88 = common_twl.m_igld85_to_ft_NAVD88


def interpolate_ari(levels: Sequence[float], aris: Sequence[float], threshold: float) -> float:
    """Linearly interpolate the ARI (Average Return Interval) at a water-level threshold.

    levels/aris are one save point's water-level-vs-ARI curve (levels ascending with
    ARI, per the twl data files -- one value per ARI column D:P). Interpolates linearly
    across ARI (per the fixed-space convention used throughout this script), i.e.
    ARI is treated as linear in water level between the two bracketing curve points.

    If threshold falls outside the curve's [min, max] water-level range, clamps to the
    nearest end ARI (0.1 or 1000-yr) and emits a UserWarning rather than extrapolating
    or failing -- thresholds a bit beyond the modeled range are still usable, just less
    precise.
    """
    if len(levels) != len(aris):
        raise ValueError(
            f"levels and aris must be the same length; got {len(levels)} and {len(aris)}."
        )
    if len(levels) < 2:
        raise ValueError("levels/aris must contain at least two points to interpolate.")

    if threshold < levels[0]:
        warnings.warn(
            f"Threshold {threshold!r} is below curve minimum {levels[0]!r}; "
            f"clamping to ARI={aris[0]!r}."
        )
        return float(aris[0])
    if threshold > levels[-1]:
        warnings.warn(
            f"Threshold {threshold!r} is above curve maximum {levels[-1]!r}; "
            f"clamping to ARI={aris[-1]!r}."
        )
        return float(aris[-1])
    return float(np.interp(threshold, levels, aris))


def interpolate_level(aris: Sequence[float], levels: Sequence[float], target_ari: float) -> float:
    """Linearly interpolate the water level at a target ARI (reverse of interpolate_ari).

    aris/levels are one save point's water-level-vs-ARI curve (levels ascending with
    ARI, per the twl data files -- one value per ARI column D:P). Interpolates linearly
    across ARI (per the fixed-space convention used throughout this script), i.e. water
    level is treated as linear in ARI between the two bracketing curve points.

    Used to compute equivalent elevation: given a baseline-scenario ARI, find the water
    level under a different scenario's curve that corresponds to that same ARI.

    If target_ari falls outside the curve's [min, max] ARI range, clamps to the nearest
    end level (the level at ARI=0.1 or ARI=1000) and emits a UserWarning rather than
    extrapolating or failing -- ARIs a bit beyond the modeled range are still usable,
    just less precise.
    """
    if len(aris) != len(levels):
        raise ValueError(
            f"aris and levels must be the same length; got {len(aris)} and {len(levels)}."
        )
    if len(aris) < 2:
        raise ValueError("aris/levels must contain at least two points to interpolate.")

    if target_ari < aris[0]:
        warnings.warn(
            f"Target ARI {target_ari!r} is below curve minimum {aris[0]!r}; "
            f"clamping to level={levels[0]!r}."
        )
        return float(levels[0])
    if target_ari > aris[-1]:
        warnings.warn(
            f"Target ARI {target_ari!r} is above curve maximum {aris[-1]!r}; "
            f"clamping to level={levels[-1]!r}."
        )
        return float(levels[-1])
    return float(np.interp(target_ari, aris, levels))


# Magnitude operators supported here. '=' and '!=' are deliberately excluded: against a
# continuous exceedance curve they have no sensible probability (always ~0 or ~1), unlike
# hydropattern's full operator set used for discrete per-timestep comparisons.
_VALID_OPERATORS = frozenset({">", ">=", "<", "<="})


def exceedance_probability(
    levels: Sequence[float], aris: Sequence[float], threshold: float, operator: str
) -> float:
    """Probability that the magnitude condition (`value <operator> threshold`) holds.

    Interpolates the ARI at threshold (see interpolate_ari) and converts to an annual
    exceedance probability via the Poisson relation `p = 1 - exp(-1/ARI)` (ARI is treated
    as the mean number of years between independent exceedance events, i.e. `1/ARI` is the
    mean annual exceedance rate). This stays correctly bounded in (0, 1) for any ARI > 0,
    unlike the naive `p = 1/ARI` approximation, which exceeds 1 whenever ARI < 1 year --
    this dataset's ARI columns go as low as 0.1 years, so the naive approximation is not
    safe to use here. For large ARI the two formulas converge (`1 - exp(-x) ~= x` for
    small x), so this only meaningfully changes results for ARI below roughly 10 years.
    For '>' / '>=' this probability *is* the exceedance probability; for '<' / '<=' it's
    the complement (1 - p), since the condition holds everywhere except in the exceedance
    tail.
    """
    if operator not in _VALID_OPERATORS:
        raise ValueError(
            f"Unsupported comparison operator {operator!r}; must be one of "
            f"{sorted(_VALID_OPERATORS)} ('=' and '!=' are not supported against a "
            "continuous exceedance curve)."
        )
    ari = interpolate_ari(levels, aris, threshold)
    p_exceed = 1.0 - exp(-1.0 / ari)
    if operator in (">", ">="):
        return p_exceed
    return 1.0 - p_exceed


def compute_metric(p_exceed: float, success_pattern: bool, mode: str) -> float:
    """Compute the configured summary metric from a magnitude condition's probability.

    Mirrors hydropattern.formatters.compute_metric_series's semantics exactly, just
    starting from a single probability instead of a per-timestep portion series:
        - portion:        p_exceed if success_pattern else (1 - p_exceed).
        - percentage:      portion * 100.
        - return_period:   1 / portion; NaN (undefined) when portion <= 0.
    """
    portion = p_exceed if success_pattern else (1.0 - p_exceed)
    if mode == "portion":
        return portion
    if mode == "percentage":
        return portion * 100.0
    if mode == "return_period":
        return float("nan") if portion <= 0 else 1.0 / portion
    raise ValueError(
        f"Unsupported metric mode {mode!r}; must be one of "
        "'portion', 'percentage', 'return_period'."
    )


def select_save_point(
    save_points: pd.DataFrame,
    save_point_id: Any = None,
    lat: float | None = None,
    lon: float | None = None,
) -> pd.Series:
    """Select one save-point row from a twl sheet's DataFrame (columns ID, lat, lon, ...).

    save_point_id, if given, always wins (even when lat/lon are also given). Otherwise
    lat and lon must both be given, and the nearest save point is picked by simple
    euclidean distance on (lat, lon) degrees -- good enough for picking the closest
    modeled point, not a navigational distance.

    Raises ValueError if neither save_point_id nor a complete (lat, lon) pair is given,
    or if save_point_id does not match any row.
    """
    if save_point_id is not None:
        matches = save_points[save_points["ID"] == save_point_id]
        if matches.empty:
            raise ValueError(f"No save point found with ID {save_point_id!r}.")
        return matches.iloc[0]

    if lat is None or lon is None:
        raise ValueError(
            "Must provide either save_point_id or both lat and lon to select a save point."
        )
    # Plain pandas arithmetic (rather than np.hypot) keeps this a Series, so .idxmin()
    # is available and the return type stays a Series row (not a bare numpy scalar).
    distances = ((save_points["lat"] - lat) ** 2 + (save_points["lon"] - lon) ** 2) ** 0.5
    # A single integer position always selects one row (a Series), never a DataFrame,
    # but pandas-stubs' .loc/.iloc-by-label overloads can't express that -- looking up
    # the plain positional argmin sidesteps the ambiguity.
    nearest_position = int(np.asarray(distances).argmin())
    return save_points.iloc[nearest_position]


# ---- resources sheet: row parsing ------------------------------------------------------

_DEFAULT_COMPONENT_NAME = "twl"


@dataclass(frozen=True)
class ResourceSpec:
    """Pure-data specification for one resources-sheet row.

    One ResourceSpec = one save-point magnitude threshold = one scenario-grid metric
    per scenario = one generated grid csv + plot png.
    """

    resource_name: str
    component_name: str
    lake: str
    magnitude_operator: str
    magnitude_value: float
    save_point_id: Any = None
    lat: float | None = None
    lon: float | None = None
    success_pattern: bool = False
    # Climate-canvas plot reference line (colormap center), in the config's metric_mode
    # units (portion 0-1 / percentage 0-100 / return_period years) -- NOT a water level,
    # unlike magnitude_value. See docs/user/reference.md's climate-canvas `threshold`.
    threshold: float | None = None
    # Resolved from the resources-sheet 'equivalent_elevation' column. None means the
    # equivalent-elevation analysis is skipped entirely for this row (blank cell).
    # Otherwise, this is the water-level value used to find the baseline (_0_0)
    # scenario's ARI in compute_equivalent_elevation_metrics -- either magnitude_value
    # itself (cell = "baseline_magnitude", case-insensitive) or an explicit numeric
    # override (cell = a number), which replaces magnitude_value for this analysis
    # only. The primary scenario-grid metric always uses magnitude_value, unaffected
    # by this field. See CONTEXT.md's "Equivalent elevation" definition.
    equivalent_elevation: float | None = None

    @property
    def qualified_name(self) -> str:
        """resource_name+component_name(+save_point_id), used as the prefix of every
        generated output filename. Needed because multiple rows commonly share one
        output folder (flat mode, the default), so component_name alone would collide
        across resources -- and, since a resources sheet may legitimately reuse the
        same resource_name+component_name label across several save points (e.g. the
        same site name evaluated at multiple nearby points), save_point_id is appended
        when given to keep those rows' outputs from colliding too. Rows selected by
        lat/lon (no save_point_id) omit the suffix, matching prior behavior."""
        base = f"{self.resource_name}_{self.component_name}"
        if self.save_point_id is None:
            return base
        return f"{base}_{self.save_point_id}"


def _validate_lake(lake: str, errors: list[str]) -> None:
    if lake and lake not in LAKE_TWL_FILENAMES:
        errors.append(
            f"Unknown lake {lake!r}; must be one of {sorted(LAKE_TWL_FILENAMES)}."
        )


def _parse_magnitude_operator_value(
    row: dict[str, Any], errors: list[str]
) -> tuple[str | None, float | None]:
    operator: str | None = _require_str(row, "magnitude_operator", errors)
    value = row.get("magnitude_value")
    if value is None or _is_blank(value):
        errors.append("'magnitude_value' is required but missing or blank.")
        value = None
    else:
        value = float(value)
    if operator and operator not in _VALID_OPERATORS:
        errors.append(
            f"magnitude_operator {operator!r} is not a valid comparison symbol; "
            f"must be one of {sorted(_VALID_OPERATORS)}."
        )
        operator = None
    return (operator or None, value)


def _parse_save_point_selector(
    row: dict[str, Any], errors: list[str]
) -> tuple[Any, float | None, float | None]:
    save_point_id = row.get("save_point_id")
    save_point_id = None if _is_blank(save_point_id) else save_point_id
    lat = row.get("lat")
    lat = None if lat is None or _is_blank(lat) else float(lat)
    lon = row.get("lon")
    lon = None if lon is None or _is_blank(lon) else float(lon)

    if save_point_id is None and (lat is None or lon is None):
        errors.append(
            "Row must provide either 'save_point_id', or both 'lat' and 'lon', to "
            "select a save point."
        )
    elif save_point_id is None and (lat is None) != (lon is None):
        errors.append("Row provides only one of 'lat'/'lon'; both are required together.")
    return (save_point_id, lat, lon)


def _parse_threshold(row: dict[str, Any]) -> float | None:
    value = row.get("threshold")
    if value is None or _is_blank(value):
        return None
    return float(value)


_BASELINE_MAGNITUDE_KEYWORD = "baseline_magnitude"


def _parse_equivalent_elevation(
    row: dict[str, Any], magnitude_value: float | None, errors: list[str]
) -> float | None:
    """Resolve the 'equivalent_elevation' column into the value used for the
    equivalent-elevation baseline ARI lookup (or None to skip that analysis).

    Blank -> None (skip). The keyword "baseline_magnitude" (case-insensitive) ->
    magnitude_value (current default behavior). A number (or numeric string) -> that
    value, overriding magnitude_value for the equivalent-elevation analysis only.
    Anything else is a validation error.
    """
    value = row.get("equivalent_elevation")
    if value is None or _is_blank(value):
        return None
    if isinstance(value, str) and value.strip().lower() == _BASELINE_MAGNITUDE_KEYWORD:
        return magnitude_value
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(
            f"'equivalent_elevation' value {value!r} is invalid; must be blank, "
            f"{_BASELINE_MAGNITUDE_KEYWORD!r}, or a number."
        )
        return None


def parse_resource_row(row: dict[str, Any]) -> ResourceSpec:
    """Validate and parse one resources-sheet row into a ResourceSpec.

    Raises RowValidationError (carrying all problems found, not just the first) if the
    row is invalid.
    """
    errors: list[str] = []

    resource_name = _require_str(row, "resource_name", errors)
    lake = _require_str(row, "lake", errors)
    _validate_lake(lake, errors)

    component_name = row.get("component_name")
    component_name = (
        _DEFAULT_COMPONENT_NAME if _is_blank(component_name) else str(component_name).strip()
    )

    magnitude_operator, magnitude_value = _parse_magnitude_operator_value(row, errors)
    save_point_id, lat, lon = _parse_save_point_selector(row, errors)
    success_pattern = _to_bool(row.get("success_pattern"), default=False)
    threshold = _parse_threshold(row)
    equivalent_elevation = _parse_equivalent_elevation(row, magnitude_value, errors)

    if errors:
        raise RowValidationError(errors)

    return ResourceSpec(
        resource_name=resource_name,
        component_name=component_name,
        lake=lake,
        magnitude_operator=magnitude_operator,  # type: ignore[arg-type]
        magnitude_value=magnitude_value,  # type: ignore[arg-type]
        save_point_id=save_point_id,
        lat=lat,
        lon=lon,
        success_pattern=success_pattern,
        threshold=threshold,
        equivalent_elevation=equivalent_elevation,
    )


# ---- config sheet -----------------------------------------------------------------

_VALID_SUBDIRECTORY_STRUCTURES = ("flat", "resource", "row")
_VALID_METRIC_MODES = frozenset({"portion", "percentage", "return_period"})
_VALID_FILENAME_STYLES = frozenset({
    "qualified_name", "elevation_runup_savepoint", "savepoint_elevation_runup",
})


@dataclass(frozen=True)
class BatchConfig:
    """Pure-data specification for the config-sheet options shared across all rows."""

    output_directory: str = ""  # base output directory; required, no sensible default
    subdirectory_structure: str = "flat"  # "flat" | "resource" | "row"
    metric_mode: str = "return_period"  # portion | percentage | return_period
    # "qualified_name" -> <resource_name>_<component_name>[_<save_point_id>] (default,
    # generic). "elevation_runup_savepoint" -> longtailpoint-specific
    # <elev>ft_plus<runup>ft-runup_savepoint<id> (see common_twl.output_file_stem).
    filename_style: str = "qualified_name"
    overwrite: bool = False
    plot_interpolate: bool = True
    plot_color_map: str = "RdBu"
    plot_color_map_ticks: tuple[float, ...] | None = None
    # Forwarded as climate-canvas's plot_response_surface(fillin=...) on every plot_fn
    # call this script makes (primary + equivalent-elevation). Estimates missing (NaN)
    # grid cells via Delaunay triangulation; see climate-canvas's --fillin option.
    fillin: bool = False
    # Forwarded as climate-canvas's plot_response_surface(show_values=..., value_decimals=...)
    # on every plot_fn call this script makes -- draws each pixel's own value centered
    # on the pixel (see climate-canvas's _label_cell_values).
    show_values: bool = False
    value_decimals: int = 2


def resolve_output_folder(resource: ResourceSpec, config: BatchConfig) -> Path:
    """Compute the output folder for one resource row.

    Pure/stateless: depends only on this row's resource_name/component_name and the
    config's output_directory/subdirectory_structure. Does NOT detect collisions
    between rows -- that's run_batch's job.

    subdirectory_structure:
        "flat"     -> output_directory/
        "resource" -> output_directory/<resource_name>/
        "row"      -> output_directory/<resource_name>/<component_name>/
    """
    if config.subdirectory_structure not in _VALID_SUBDIRECTORY_STRUCTURES:
        raise ValueError(
            f"Invalid subdirectory_structure {config.subdirectory_structure!r}; "
            f"must be one of {_VALID_SUBDIRECTORY_STRUCTURES!r}."
        )
    base = Path(config.output_directory)
    if config.subdirectory_structure == "flat":
        return base
    if config.subdirectory_structure == "resource":
        return base / resource.resource_name
    return base / resource.resource_name / resource.component_name


def resolve_output_stem(resource: ResourceSpec, config: BatchConfig) -> str:
    """Compute the file-name stem (no suffix/extension) used for this row's output
    files.

    "qualified_name" (default) -> resource.qualified_name, unchanged generic behavior.
    "elevation_runup_savepoint" -> longtailpoint-specific ft-based naming
    "<elevation>ft_plus<runup>ft-runup_savepoint<id>"; requires resource.magnitude_value
    to be an IGLD85-meters elevation and resource.component_name to be one of
    common_twl.RUNUP_FT_BY_COMPONENT's keys (raises ValueError otherwise).
    "savepoint_elevation_runup" -> longtailpoint-specific naming
    "<save point>_<elevation>_<runup>", elevation = magnitude + runup combined; same
    resource requirements as "elevation_runup_savepoint".
    """
    if config.filename_style == "qualified_name":
        return resource.qualified_name
    if config.filename_style == "elevation_runup_savepoint":
        magnitude_ft = common_twl.m_igld85_to_ft_NAVD88(resource.magnitude_value)
        return common_twl.output_file_stem(
            magnitude_ft, resource.component_name, resource.save_point_id
        )
    if config.filename_style == "savepoint_elevation_runup":
        magnitude_ft = common_twl.m_igld85_to_ft_NAVD88(resource.magnitude_value)
        return common_twl.output_file_stem_savepoint_elevation_runup(
            magnitude_ft, resource.component_name, resource.save_point_id
        )
    raise ValueError(
        f"Invalid filename_style {config.filename_style!r}; "
        f"must be one of {sorted(_VALID_FILENAME_STYLES)}."
    )


# filename_style values that are longtailpoint-specific (require resource.component_name
# to be a known runup-allowance code and drive the 3-line build_plot_title title).
_LONGTAILPOINT_FILENAME_STYLES = frozenset({
    "elevation_runup_savepoint", "savepoint_elevation_runup",
})


def resolve_plot_title(
    plot_kind: str, resource: ResourceSpec, config: BatchConfig,
    baseline_ari: float | None = None,
) -> str:
    """Compute one plot's title.

    Only longtailpoint-style runs (config.filename_style in
    _LONGTAILPOINT_FILENAME_STYLES, the same gate resolve_output_stem uses) get the
    "Longtail Point <type>/elevation.../save point..." title from
    common_twl.build_plot_title -- resource.component_name is only guaranteed to be a
    known runup-allowance code (common_twl.RUNUP_FT_BY_COMPONENT) for those runs.
    Every other filename_style keeps the original, generic
    "<resource>_<component>[_<save point>]" title (resource.qualified_name), optionally
    suffixed with the plot kind for the equivalent-elevation/elevation-delta plots so
    they remain distinguishable from the primary plot.

    baseline_ari, when given, is threaded through to build_plot_title -- only has an
    effect for plot_kind in ("equivalent_elevation", "elevation_delta") (see
    build_plot_title), where it adds a 4th "baseline ARI: <value> yr" title line.
    """
    if config.filename_style not in _LONGTAILPOINT_FILENAME_STYLES:
        if plot_kind == "primary":
            return resource.qualified_name
        return f"{resource.qualified_name}_{plot_kind}"
    magnitude_ft = common_twl.m_igld85_to_ft_NAVD88(resource.magnitude_value)
    return common_twl.build_plot_title(
        plot_kind, magnitude_ft, resource.component_name, resource.save_point_id,
        baseline_ari=baseline_ari,
    )


def _format_ari_component(ari: float) -> str:
    """Format an ARI (in years) for use in a `savepoint<id>_ari<ari>_elevation`
    filename component: whole-number ARIs render without a trailing ".0" (e.g. "15"),
    fractional ARIs keep one decimal-free `g`-style representation (e.g. "12.5")."""
    return f"{ari:g}"


def resolve_save_point_ari_elevation_output_paths(
    resource: ResourceSpec, config: BatchConfig
) -> tuple[Path, Path]:
    """Compute the (grid csv, plot png) paths for one save point's threshold-ARI
    elevation output (see CONTEXT.md's "Threshold-ARI elevation" entry).

    Unlike resolve_output_folder/resolve_output_stem, this output is keyed by
    save_point_id + resource.threshold alone (not resource_name/component_name/
    filename_style) -- it's written once per unique save point, shared across every
    resource row for that save point -- so it always lives directly under
    config.output_directory (flat, regardless of config.subdirectory_structure),
    named `savepoint<id>_ari<threshold>_elevation_grid.csv`/`_plot.png`.

    Callers should only invoke this when resource.threshold is not None.
    """
    assert resource.threshold is not None, (
        "resolve_save_point_ari_elevation_output_paths requires resource.threshold"
    )
    folder = Path(config.output_directory)
    stem = f"savepoint{resource.save_point_id}_ari{_format_ari_component(resource.threshold)}_elevation"
    return folder / f"{stem}_grid.csv", folder / f"{stem}_plot.png"


def resolve_all_output_paths(resource: ResourceSpec, config: BatchConfig) -> list[Path]:
    """Compute every output file path build_resource_outputs will write for this row:
    always the primary grid+plot, plus (when resource.equivalent_elevation is not
    None) the equivalent-elevation and elevation-delta grid+plot pairs, plus (when
    resource.threshold is not None) the save-point threshold-ARI elevation grid+plot
    pair (see resolve_save_point_ari_elevation_output_paths -- shared across every
    resource row for the same save point, but still listed here so a single row's
    "where did my outputs go" answer is complete).

    Pure/stateless (mirrors build_resource_outputs' own path construction) so callers
    (e.g. run_batch, for the results workbook's "output location" column) can learn a
    row's full output-file list without re-running the actual grid/plot generation.
    """
    output_folder = resolve_output_folder(resource, config)
    stem = resolve_output_stem(resource, config)
    paths = [
        output_folder / f"{stem}_grid.csv",
        output_folder / f"{stem}_plot.png",
    ]
    if resource.equivalent_elevation is not None:
        paths += [
            output_folder / f"{stem}_equivalent_elevation_grid.csv",
            output_folder / f"{stem}_equivalent_elevation_plot.png",
            output_folder / f"{stem}_elevation_delta_grid.csv",
            output_folder / f"{stem}_elevation_delta_plot.png",
        ]
    if resource.threshold is not None:
        paths += list(resolve_save_point_ari_elevation_output_paths(resource, config))
    return paths


_RESOURCE_REQUIRED_COLUMNS = frozenset(
    {"resource_name", "lake", "magnitude_operator", "magnitude_value"}
)
_RESOURCE_OPTIONAL_COLUMNS = frozenset({
    "component_name", "save_point_id", "lat", "lon", "success_pattern", "threshold",
    "equivalent_elevation",
})
_RESOURCE_ALL_COLUMNS = _RESOURCE_REQUIRED_COLUMNS | _RESOURCE_OPTIONAL_COLUMNS


def read_resources_sheet(path: Path, sheet_name: str = "resources") -> list[dict[str, Any]]:
    """Read the resources sheet into a list of raw row dicts (column name -> cell value).

    One dict per row. NaN/blank cells become None (not float('nan')) so downstream
    _is_blank()-based checks (e.g. in parse_resource_row) behave correctly.

    Only validates the sheet's *shape* (required columns present, no unrecognized
    columns -- likely a typo). Per-row data validation is parse_resource_row's job.
    """
    df = pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
    columns = set(df.columns)
    errors: list[str] = []
    missing = _RESOURCE_REQUIRED_COLUMNS - columns
    if missing:
        errors.append(
            f"Resources sheet is missing required column(s): {sorted(missing)}."
        )
    unknown = columns - _RESOURCE_ALL_COLUMNS
    if unknown:
        errors.append(
            f"Resources sheet has unrecognized column(s): {sorted(unknown)}."
        )
    if errors:
        raise SheetValidationError(errors)

    records = df.to_dict(orient="records")
    # df.to_dict()'s keys are typed Hashable (pandas' general column-label type), but
    # they're always the sheet's str column names here, matching this function's
    # declared list[dict[str, Any]] return type.
    return [{str(k): (None if _is_blank(v) else v) for k, v in row.items()} for row in records]


_CONFIG_BOOL_KEYS = frozenset(
    {"overwrite", "plot_interpolate", "fillin", "show_values"}
)
_CONFIG_STR_KEYS = frozenset(
    {
        "metric_mode", "output_directory", "subdirectory_structure", "plot_color_map",
        "filename_style",
    }
)
_CONFIG_TICKS_KEY = "plot_color_map_ticks"
_CONFIG_INT_KEYS = frozenset({"value_decimals"})
_CONFIG_KNOWN_KEYS = _CONFIG_BOOL_KEYS | _CONFIG_STR_KEYS | _CONFIG_INT_KEYS | {_CONFIG_TICKS_KEY}


def read_config_sheet(path: Path, sheet_name: str = "config") -> BatchConfig:
    """Read the config sheet (key/value pairs: 'option' column, 'value' column) into a
    BatchConfig. Options left blank or absent fall back to BatchConfig's own defaults,
    except 'output_directory', which is required.
    """
    df = pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
    if not {"option", "value"} <= set(df.columns):
        raise SheetValidationError(
            [f"Config sheet must have 'option' and 'value' columns; got {list(df.columns)}."]
        )

    errors: list[str] = []
    values: dict[str, Any] = {}
    for _, row in df.iterrows():
        key = row["option"]
        if _is_blank(key):
            continue
        key = str(key).strip()
        if key in values:
            errors.append(f"Config sheet has duplicate option {key!r}.")
            continue
        value = row["value"]
        values[key] = None if _is_blank(value) else value

    unknown = set(values) - _CONFIG_KNOWN_KEYS
    if unknown:
        errors.append(f"Config sheet has unrecognized option(s): {sorted(unknown)}.")

    output_directory = values.get("output_directory")
    if _is_blank(output_directory):
        errors.append(
            "Config sheet option 'output_directory' is required but missing or blank."
        )

    subdirectory_structure = values.get("subdirectory_structure")
    if not _is_blank(subdirectory_structure) \
            and str(subdirectory_structure).strip() not in _VALID_SUBDIRECTORY_STRUCTURES:
        errors.append(
            f"Config sheet option 'subdirectory_structure' {subdirectory_structure!r} "
            f"must be one of {_VALID_SUBDIRECTORY_STRUCTURES!r}."
        )

    metric_mode = values.get("metric_mode")
    if not _is_blank(metric_mode) and str(metric_mode).strip() not in _VALID_METRIC_MODES:
        errors.append(
            f"Config sheet option 'metric_mode' {metric_mode!r} "
            f"must be one of {sorted(_VALID_METRIC_MODES)}."
        )

    filename_style = values.get("filename_style")
    if not _is_blank(filename_style) \
            and str(filename_style).strip() not in _VALID_FILENAME_STYLES:
        errors.append(
            f"Config sheet option 'filename_style' {filename_style!r} "
            f"must be one of {sorted(_VALID_FILENAME_STYLES)}."
        )

    ticks = _parse_color_map_ticks(values.get(_CONFIG_TICKS_KEY), errors)

    if errors:
        raise SheetValidationError(errors)

    defaults = BatchConfig()
    kwargs: dict[str, Any] = {"output_directory": str(output_directory).strip()}
    if not _is_blank(metric_mode):
        kwargs["metric_mode"] = str(metric_mode).strip()
    if not _is_blank(values.get("overwrite")):
        kwargs["overwrite"] = _to_bool(values.get("overwrite"), defaults.overwrite)
    if not _is_blank(subdirectory_structure):
        kwargs["subdirectory_structure"] = str(subdirectory_structure).strip()
    if not _is_blank(filename_style):
        kwargs["filename_style"] = str(filename_style).strip()
    if not _is_blank(values.get("plot_interpolate")):
        kwargs["plot_interpolate"] = _to_bool(
            values.get("plot_interpolate"), defaults.plot_interpolate
        )
    if not _is_blank(values.get("plot_color_map")):
        kwargs["plot_color_map"] = str(values["plot_color_map"]).strip()
    if ticks is not None:
        kwargs["plot_color_map_ticks"] = ticks
    if not _is_blank(values.get("fillin")):
        kwargs["fillin"] = _to_bool(values.get("fillin"), defaults.fillin)
    if not _is_blank(values.get("show_values")):
        kwargs["show_values"] = _to_bool(values.get("show_values"), defaults.show_values)
    if not _is_blank(values.get("value_decimals")):
        kwargs["value_decimals"] = int(values["value_decimals"])

    return BatchConfig(**kwargs)


# ---- per-resource grid + plot building --------------------------------------------


def compute_scenario_metrics(resource: ResourceSpec, twl_path: Path, metric_mode: str
                             ) -> dict[str, float]:
    """Compute one metric value per scenario sheet for one resource's save point.

    Reads every sheet of the lake's twl workbook, selects the resource's save point in
    each, interpolates its magnitude condition's exceedance probability, and converts
    to metric_mode's units. Keys are the bare `_<precip>_<temp>` scenario-grid suffix
    (see parse_scenario_sheet_name) -- sheets that don't match that naming convention
    are skipped.
    """
    sheets = _load_lake_sheets(twl_path)
    metric_values: dict[str, float] = {}
    for sheet_name, df in sheets.items():
        suffix = parse_scenario_sheet_name(sheet_name)
        if suffix is None:
            continue
        save_point = select_save_point(df, resource.save_point_id, resource.lat, resource.lon)
        ari_columns = [c for c in df.columns if c not in _NON_ARI_COLUMNS]
        aris = [float(c) for c in ari_columns]
        levels = [float(save_point[c]) for c in ari_columns]
        p_exceed = exceedance_probability(
            levels, aris, resource.magnitude_value, resource.magnitude_operator
        )
        metric_values[suffix] = compute_metric(p_exceed, resource.success_pattern, metric_mode)
    return metric_values


# The known/filled/extrapolated scenario-grid suffix for the (0% precip delta, 0C temp
# delta) baseline scenario -- always present in every lake's twl workbook (see
# CONTEXT.md's "Known scenario" entry).
_BASELINE_SCENARIO_SUFFIX = "_0_0"


def _save_point_ari_columns_levels(
    resource: ResourceSpec, df: pd.DataFrame
) -> tuple[list[float], list[float]]:
    save_point = select_save_point(df, resource.save_point_id, resource.lat, resource.lon)
    ari_columns = [c for c in df.columns if c not in _NON_ARI_COLUMNS]
    aris = [float(c) for c in ari_columns]
    levels = [float(save_point[c]) for c in ari_columns]
    return aris, levels


def _compute_baseline_ari_from_sheets(
    resource: ResourceSpec, sheets: dict[str, pd.DataFrame], twl_path: Path
) -> float:
    baseline_aris: list[float] | None = None
    baseline_levels: list[float] | None = None
    for sheet_name, df in sheets.items():
        if parse_scenario_sheet_name(sheet_name) == _BASELINE_SCENARIO_SUFFIX:
            baseline_aris, baseline_levels = _save_point_ari_columns_levels(resource, df)
            break
    if baseline_aris is None or baseline_levels is None:
        raise ValueError(
            f"No baseline ({_BASELINE_SCENARIO_SUFFIX!r}) scenario sheet found in "
            f"{twl_path}; cannot compute equivalent elevation."
        )
    return interpolate_ari(baseline_levels, baseline_aris, resource.equivalent_elevation)


def compute_baseline_ari(resource: ResourceSpec, twl_path: Path) -> float:
    """Compute the baseline (_0_0) scenario's ARI at resource.equivalent_elevation.

    resource.equivalent_elevation is either resource.magnitude_value itself (resources
    sheet's 'equivalent_elevation' cell = "baseline_magnitude") or an explicit numeric
    override, resolved at parse time by parse_resource_row. This is the shared "baseline
    ARI" surfaced in equivalent_elevation/elevation_delta plot titles (see
    common_twl.build_plot_title's baseline_ari param) and used internally by
    compute_equivalent_elevation_metrics.

    Callers should only invoke this when resource.equivalent_elevation is not None --
    interpolate_ari requires a numeric threshold.

    Raises ValueError if the lake's twl workbook has no baseline (_0_0) scenario sheet.
    """
    assert resource.equivalent_elevation is not None, (
        "compute_baseline_ari requires resource.equivalent_elevation"
    )
    sheets = _load_lake_sheets(twl_path)
    return _compute_baseline_ari_from_sheets(resource, sheets, twl_path)


def compute_equivalent_elevation_metrics(resource: ResourceSpec, twl_path: Path
                                          ) -> dict[str, float]:
    """Compute one equivalent-elevation value per scenario sheet for one resource.

    First finds the baseline (_0_0) scenario's ARI at resource.equivalent_elevation
    (see compute_baseline_ari) -- then, for every scenario sheet (including baseline
    itself), finds the water level at that same ARI under that scenario's curve (via
    interpolate_level) -- i.e. "what water level, under this scenario, is equally
    likely (same ARI) as resource.equivalent_elevation is under the baseline scenario".
    Keys are the bare `_<precip>_<temp>` scenario-grid suffix (see
    parse_scenario_sheet_name) -- sheets that don't match that naming convention are
    skipped.

    Callers should only invoke this when resource.equivalent_elevation is not None
    (see build_resource_outputs) -- interpolate_ari requires a numeric threshold.

    Raises ValueError if the lake's twl workbook has no baseline (_0_0) scenario sheet.
    """
    assert resource.equivalent_elevation is not None, (
        "compute_equivalent_elevation_metrics requires resource.equivalent_elevation"
    )
    sheets = _load_lake_sheets(twl_path)
    baseline_ari = _compute_baseline_ari_from_sheets(resource, sheets, twl_path)

    equivalent_elevations: dict[str, float] = {}
    for sheet_name, df in sheets.items():
        suffix = parse_scenario_sheet_name(sheet_name)
        if suffix is None:
            continue
        aris, levels = _save_point_ari_columns_levels(resource, df)
        equivalent_elevations[suffix] = interpolate_level(aris, levels, baseline_ari)
    return equivalent_elevations


def compute_threshold_ari_elevation_metrics(resource: ResourceSpec, twl_path: Path
                                             ) -> dict[str, float]:
    """Compute one threshold-ARI elevation value per scenario sheet for one resource.

    For every scenario sheet (including baseline itself), finds the water level at
    resource.threshold's ARI under that scenario's own curve (via interpolate_level) --
    i.e. "what water level is exceeded, under this scenario, with the same
    (resource.threshold)-year average recurrence interval". Unlike
    compute_equivalent_elevation_metrics, no baseline-curve ARI lookup step is needed
    first, since resource.threshold is already an ARI (not a water level). Keys are the
    bare `_<precip>_<temp>` scenario-grid suffix (see parse_scenario_sheet_name) --
    sheets that don't match that naming convention are skipped.

    See CONTEXT.md's "Threshold-ARI elevation" entry: this powers a fourth grid/plot
    written once per unique save point (not per resource row) -- callers are
    responsible for that per-save-point dedup (see build_save_point_ari_elevation_
    output/_TwlRowProcessor), since this function itself is a pure per-resource-row
    computation.

    Callers should only invoke this when resource.threshold is not None --
    interpolate_level requires a numeric target ARI.
    """
    assert resource.threshold is not None, (
        "compute_threshold_ari_elevation_metrics requires resource.threshold"
    )
    sheets = _load_lake_sheets(twl_path)
    elevations: dict[str, float] = {}
    for sheet_name, df in sheets.items():
        suffix = parse_scenario_sheet_name(sheet_name)
        if suffix is None:
            continue
        aris, levels = _save_point_ari_columns_levels(resource, df)
        elevations[suffix] = interpolate_level(aris, levels, resource.threshold)
    return elevations


def build_resource_outputs(
    resource: ResourceSpec,
    data_dir: Path,
    config: BatchConfig,
    plot_fn: Callable[..., None] = plot_response_surface,
) -> tuple[Path, Path]:
    """Compute one resource's scenario-grid metrics and write its grid csv + plot png.

    The primary grid/plot always evaluates resource.magnitude_value, regardless of the
    resources sheet's 'equivalent_elevation' setting.

    If resource.equivalent_elevation is not None (resources sheet's
    'equivalent_elevation' cell is "baseline_magnitude" or a numeric override -- not
    blank), also computes and writes:

    - a second grid csv + plot png: the water level under every scenario equivalent
      (same ARI) to the baseline scenario's ARI at resource.equivalent_elevation (see
      compute_equivalent_elevation_metrics). This plot's z-axis is labeled
      "Equivalent Elevation (ft, NAVD88)", its threshold is resource.equivalent_elevation,
      and it uses config.plot_color_map as given -- unlike the primary plot, no
      RdBu-direction auto-reversal or color_map_ticks are applied, since
      success_pattern/metric_mode semantics don't apply to a raw elevation value.
    - a third grid csv + plot png: elevation_delta, the increase/decrease (in ft
      NAVD88) of each scenario's equivalent elevation relative to
      resource.equivalent_elevation (the comparison/baseline-lookup elevation itself).
      Its z-axis is labeled "Elevation Delta (ft, NAVD88)" and its colorbar threshold
      is fixed at 0 (no delta), regardless of resource.threshold or the equivalent
      elevation plot's own threshold.

    compute_equivalent_elevation_metrics works entirely in meters, IGLD85 datum (the
    unit of magnitude_value/equivalent_elevation and the twl workbooks' level curves);
    the equivalent_elevation and elevation_delta grids/plots are the only places that
    convert to feet, NAVD88 datum (via common_twl.m_igld85_to_ft_NAVD88), since they are
    the only outputs of this script that represent a water level rather than a
    metric_mode value (portion/percentage/return_period), which has no elevation units
    to convert.

    plot_fn is injectable so tests can substitute a recording stub instead of the real
    climate_canvas plotting call (which opens a matplotlib figure).

    Raises FileExistsError if any target output file already exists and
    config.overwrite is False. Raises HydropatternError (via require_scenario_grid) if
    the lake's sheet names don't form a valid scenario grid.
    """
    twl_path = resolve_lake_twl_path(resource.lake, data_dir)
    metric_values = compute_scenario_metrics(resource, twl_path, config.metric_mode)
    scenario_names = list(metric_values.keys())
    require_scenario_grid(scenario_names)
    xs, ys, zs = build_grid(scenario_names, metric_values)

    output_folder = resolve_output_folder(resource, config)
    stem = resolve_output_stem(resource, config)
    grid_path = output_folder / f"{stem}_grid.csv"
    plot_path = output_folder / f"{stem}_plot.png"
    elev_grid_path = output_folder / f"{stem}_equivalent_elevation_grid.csv"
    elev_plot_path = output_folder / f"{stem}_equivalent_elevation_plot.png"
    delta_grid_path = output_folder / f"{stem}_elevation_delta_grid.csv"
    delta_plot_path = output_folder / f"{stem}_elevation_delta_plot.png"

    compute_elevation = resource.equivalent_elevation is not None
    targets = [grid_path, plot_path]
    if compute_elevation:
        targets += [elev_grid_path, elev_plot_path, delta_grid_path, delta_plot_path]
    if not config.overwrite:
        existing = [p for p in targets if p.exists()]
        if existing:
            raise FileExistsError(
                f"Output file(s) already exist and overwrite=False: "
                f"{', '.join(str(p) for p in existing)}."
            )

    output_folder.mkdir(parents=True, exist_ok=True)
    write_grid_csv(xs, ys, zs, grid_path)
    color_map = _resolve_color_map(
        config.plot_color_map, resource.success_pattern, MetricMode(config.metric_mode)
    )
    primary_extra: dict[str, Any] = {}
    if resource.threshold is not None:
        primary_z_range = (float(np.nanmin(zs)), float(np.nanmax(zs)))
        primary_style = common_twl.one_sided_color_style(primary_z_range, resource.threshold)
        if primary_style is not None:
            color_map = primary_style[0]
            primary_extra = dict(
                norm=primary_style[1], levels=primary_style[2], widths=primary_style[3]
            )
    plot_fn(
        xs, ys, zs,
        interpolate=config.plot_interpolate,
        labels=("Precipitation Delta (%)", "Temperature Delta (C)", config.metric_mode),
        title=resolve_plot_title("primary", resource, config),
        save_path=plot_path,
        show=False,
        threshold=resource.threshold,
        color_map=color_map,
        color_map_ticks=config.plot_color_map_ticks,
        fillin=config.fillin,
        show_values=config.show_values,
        value_decimals=config.value_decimals,
        **primary_extra,
    )

    if compute_elevation:
        assert resource.equivalent_elevation is not None
        elev_values_m = compute_equivalent_elevation_metrics(resource, twl_path)
        elev_values_ft = {
            suffix: _m_igld85_to_ft_NAVD88(value) for suffix, value in elev_values_m.items()
        }
        comparison_ft = _m_igld85_to_ft_NAVD88(resource.equivalent_elevation)
        baseline_ari = compute_baseline_ari(resource, twl_path)

        elev_xs, elev_ys, elev_zs = build_grid(list(elev_values_ft.keys()), elev_values_ft)
        write_grid_csv(elev_xs, elev_ys, elev_zs, elev_grid_path)
        elev_z_range = (float(np.nanmin(elev_zs)), float(np.nanmax(elev_zs)))
        elev_levels, elev_widths = common_twl.rounded_levels(elev_z_range, comparison_ft)
        elev_style = common_twl.one_sided_color_style(elev_z_range, comparison_ft)
        elev_color_map = elev_style[0] if elev_style is not None else config.plot_color_map
        elev_norm = elev_style[1] if elev_style is not None else None
        plot_fn(
            elev_xs, elev_ys, elev_zs,
            interpolate=config.plot_interpolate,
            labels=("Precipitation Delta (%)", "Temperature Delta (C)",
                    "Equivalent Elevation (ft, NAVD88)"),
            title=resolve_plot_title(
                "equivalent_elevation", resource, config, baseline_ari=baseline_ari
            ),
            save_path=elev_plot_path,
            show=False,
            threshold=comparison_ft,
            color_map=elev_color_map,
            color_map_ticks=elev_levels,
            fillin=config.fillin,
            show_values=config.show_values,
            value_decimals=config.value_decimals,
            norm=elev_norm,
            levels=elev_levels,
            widths=elev_widths,
        )

        delta_values_ft = {
            suffix: value - comparison_ft for suffix, value in elev_values_ft.items()
        }
        delta_xs, delta_ys, delta_zs = build_grid(list(delta_values_ft.keys()), delta_values_ft)
        write_grid_csv(delta_xs, delta_ys, delta_zs, delta_grid_path)
        delta_z_range = (float(np.nanmin(delta_zs)), float(np.nanmax(delta_zs)))
        delta_levels, delta_widths = common_twl.symmetric_delta_levels(delta_z_range)
        delta_ticks = common_twl.colorbar_ticks_within_range(delta_levels, delta_z_range)
        delta_style = common_twl.one_sided_color_style(delta_z_range, 0.0)
        delta_color_map = delta_style[0] if delta_style is not None else config.plot_color_map
        delta_norm = delta_style[1] if delta_style is not None else None
        plot_fn(
            delta_xs, delta_ys, delta_zs,
            interpolate=config.plot_interpolate,
            labels=("Precipitation Delta (%)", "Temperature Delta (C)",
                    "Elevation Delta (ft, NAVD88)"),
            title=resolve_plot_title(
                "elevation_delta", resource, config, baseline_ari=baseline_ari
            ),
            save_path=delta_plot_path,
            show=False,
            threshold=0.0,
            color_map=delta_color_map,
            color_map_ticks=delta_ticks,
            fillin=config.fillin,
            show_values=config.show_values,
            value_decimals=config.value_decimals,
            norm=delta_norm,
            levels=delta_levels,
            widths=delta_widths,
        )

    return (grid_path, plot_path)


def build_save_point_ari_elevation_output(
    resource: ResourceSpec,
    twl_path: Path,
    config: BatchConfig,
    plot_fn: Callable[..., None] = plot_response_surface,
) -> tuple[Path, Path]:
    """Compute one save point's threshold-ARI elevation grid + write its grid csv +
    plot png (see CONTEXT.md's "Threshold-ARI elevation" entry).

    Depends only on resource.save_point_id + resource.threshold (not
    magnitude/component/runup) -- callers (see _TwlRowProcessor) are responsible for
    only invoking this once per unique save point per run, since every resource row
    sharing a save point would otherwise recompute and rewrite the identical output.

    The z-axis is labeled "Elevation (ft, NAVD88)"; the colorbar is centered on the
    baseline (_0_0) scenario's own value at resource.threshold's ARI (white at
    baseline), via common_twl.one_sided_color_style -- unlike elevation_delta's fixed
    0 center, since this plot reports raw elevations rather than a delta.

    Raises FileExistsError if either target output file already exists and
    config.overwrite is False.
    """
    assert resource.threshold is not None, (
        "build_save_point_ari_elevation_output requires resource.threshold"
    )
    grid_path, plot_path = resolve_save_point_ari_elevation_output_paths(resource, config)
    if not config.overwrite:
        existing = [p for p in (grid_path, plot_path) if p.exists()]
        if existing:
            raise FileExistsError(
                f"Output file(s) already exist and overwrite=False: "
                f"{', '.join(str(p) for p in existing)}."
            )

    values_m = compute_threshold_ari_elevation_metrics(resource, twl_path)
    values_ft = {suffix: _m_igld85_to_ft_NAVD88(value) for suffix, value in values_m.items()}
    baseline_ft = values_ft[_BASELINE_SCENARIO_SUFFIX]

    xs, ys, zs = build_grid(list(values_ft.keys()), values_ft)
    grid_path.parent.mkdir(parents=True, exist_ok=True)
    write_grid_csv(xs, ys, zs, grid_path)
    z_range = (float(np.nanmin(zs)), float(np.nanmax(zs)))
    levels, widths = common_twl.rounded_levels(z_range, baseline_ft)
    style = common_twl.one_sided_color_style(z_range, baseline_ft)
    color_map = style[0] if style is not None else config.plot_color_map
    norm = style[1] if style is not None else None
    plot_fn(
        xs, ys, zs,
        interpolate=config.plot_interpolate,
        labels=("Precipitation Delta (%)", "Temperature Delta (C)", "Elevation (ft, NAVD88)"),
        title=common_twl.build_threshold_ari_title(resource.threshold, resource.save_point_id),
        save_path=plot_path,
        show=False,
        threshold=baseline_ft,
        color_map=color_map,
        color_map_ticks=levels,
        fillin=config.fillin,
        show_values=config.show_values,
        value_decimals=config.value_decimals,
        norm=norm,
        levels=levels,
        widths=widths,
    )
    return (grid_path, plot_path)


# ---- run_batch orchestration -----------------------------------------------------------

class _TwlRowProcessor:
    """batch_runner.RowProcessor adapter wrapping this module's existing per-row
    functions -- the only twl-specific piece of run_batch's Strategy pattern. See
    batch_runner.py's module docstring for why this exists.

    Also owns the save-point threshold-ARI elevation output's per-run dedup: unlike
    the primary/equivalent_elevation/elevation_delta outputs (one per resource row),
    that output is keyed by save_point_id + resource.threshold alone, so it's built
    at most once per unique save_point_id encountered across this processor's
    lifetime (one instance per run_batch call -- see run_batch).
    """

    def __init__(
        self,
        build_outputs: Callable[[ResourceSpec, Path, BatchConfig], tuple[Path, Path]],
        build_save_point_ari_output: Callable[[ResourceSpec, Path, BatchConfig], tuple[Path, Path]]
            = build_save_point_ari_elevation_output,
    ):
        self._build_outputs = build_outputs
        self._build_save_point_ari_output = build_save_point_ari_output
        self._ari_written_save_points: set[Any] = set()

    def read_rows(self, resources_path: Path) -> list[dict[str, Any]]:
        return read_resources_sheet(resources_path)

    def parse(self, raw_row: dict[str, Any]) -> ResourceSpec:
        return parse_resource_row(raw_row)

    def target(self, resource: ResourceSpec, config: BatchConfig) -> tuple[Path, str]:
        return (resolve_output_folder(resource, config), resource.qualified_name)

    def duplicate_message(self, output_folder: Path, resource: ResourceSpec) -> str:
        return (
            f"Duplicate output target within this batch run: "
            f"{output_folder / f'{resource.qualified_name}_grid.csv'}"
        )

    def check_overwrite(self, resource: ResourceSpec, config: BatchConfig) -> str | None:
        # Unlike avg's processor, twl's pre-existing-output check happens inside
        # build_outputs itself (raises FileExistsError, caught generically by
        # batch_runner.run_batch's try/except around build()) -- nothing to check here.
        return None

    def build(
        self, resource: ResourceSpec, data_dir: Path, config: BatchConfig
    ) -> tuple[Path, ...]:
        self._build_outputs(resource, data_dir, config)
        if resource.threshold is not None and resource.save_point_id is not None:
            if resource.save_point_id not in self._ari_written_save_points:
                twl_path = resolve_lake_twl_path(resource.lake, data_dir)
                self._build_save_point_ari_output(resource, twl_path, config)
                self._ari_written_save_points.add(resource.save_point_id)
        return tuple(resolve_all_output_paths(resource, config))


def _naming_scheme_text(config: BatchConfig) -> str:
    """Naming-scheme blurb for config.filename_style: the longtailpoint-specific
    dedicated write-up (see common_twl.naming_scheme_readme_text) when one exists,
    else a generic description of the "qualified_name" default."""
    try:
        return common_twl.naming_scheme_readme_text(config.filename_style)
    except ValueError:
        header = "Output filename naming scheme for this directory\n" + "=" * 50 + "\n\n"
        return header + (
            "Output filename pattern: "
            "<resource_name>_<component_name>[_<save_point_id>]...\n\n"
            "  resource_name/component_name - from this row's resources-sheet "
            "columns.\n"
            "  save_point_id - appended only when the row selected its save point "
            "by ID rather than lat/lon (see CONTEXT.md's \"Save point\" entry).\n"
        )


def run_batch(
    resources_path: Path,
    data_dir: Path,
    config: BatchConfig,
    build_outputs: Callable[[ResourceSpec, Path, BatchConfig], tuple[Path, Path]]
        = build_resource_outputs,
    progress: Callable[[int, int, str | None, str | None, str], None] = _default_progress,
    build_save_point_ari_output: Callable[[ResourceSpec, Path, BatchConfig], tuple[Path, Path]]
        = build_save_point_ari_elevation_output,
) -> BatchSummary:
    """Generate one scenario-grid csv + plot png per hydropattern resources-sheet row.

    Continues past a failing row (bad row data, duplicate output target, pre-existing
    output with overwrite=False, or a build_outputs error) rather than aborting the
    whole batch; every row's outcome is captured in the returned BatchSummary.

    build_outputs is injectable so tests can mock the actual grid/plot generation
    without touching the filesystem or matplotlib. build_save_point_ari_output is
    injectable the same way, for the save-point threshold-ARI elevation output (see
    _TwlRowProcessor -- built at most once per unique save_point_id in this run).
    progress is injectable for the same reason (and to let callers redirect/silence
    the real-time per-row status output).

    Always writes a run readme (see CONTEXT.md's "Run readme" entry) to
    config.output_directory, even if every row fails or the sheet has zero rows.

    Thin wrapper over batch_runner.run_batch's shared loop; see _TwlRowProcessor for
    the twl-specific per-row behavior.
    """
    summary = batch_runner.run_batch(
        resources_path, data_dir, config,
        _TwlRowProcessor(build_outputs, build_save_point_ari_output), progress,
    )
    batch_runner.write_run_readme(
        resources_path, data_dir, Path(config.output_directory), summary,
        naming_scheme_text=_naming_scheme_text(config), workspace_root=WORKSPACE_ROOT,
    )
    return summary


# ---- results workbook (adds an "output location" column) --------------------------

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _output_location_cell(output_paths: Sequence[Path], workspace_root: Path) -> str:
    """Semicolon-joined list of `output_paths`, each expressed relative to
    `workspace_root` (falls back to the absolute path if a path isn't actually under
    workspace_root, e.g. in ad-hoc/test scenarios).
    """
    labels = []
    for path in output_paths:
        resolved = Path(path).resolve()
        try:
            labels.append(str(resolved.relative_to(workspace_root)))
        except ValueError:
            labels.append(str(resolved))
    return ";".join(labels)


def write_results_workbook(
    resources_path: Path,
    summary: BatchSummary,
    out_path: Path,
    workspace_root: Path = WORKSPACE_ROOT,
) -> Path:
    """Write a new workbook (copy of resources_path's 'resources' and 'config' sheets)
    with an extra 'output location' column on the resources sheet: one row per
    resources-sheet row (aligned by position, matching summary.results' row order),
    holding a ';'-joined list of every output file this row produced (empty string for
    a failed row), each path expressed relative to `workspace_root` (defaults to the
    hydropattern repo root).

    Does not modify resources_path itself -- always writes a brand-new workbook at
    out_path.
    """
    resources_df = pd.read_excel(resources_path, sheet_name="resources", engine="calamine")
    config_df = pd.read_excel(resources_path, sheet_name="config", engine="calamine")

    locations = [""] * len(resources_df)
    for result in summary.results:
        if 1 <= result.row_index <= len(locations):
            locations[result.row_index - 1] = _output_location_cell(
                result.output_paths, workspace_root
            )
    resources_df["output location"] = locations

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path) as writer:
        resources_df.to_excel(writer, sheet_name="resources", index=False)
        config_df.to_excel(writer, sheet_name="config", index=False)
    return out_path


# ---- CLI entry point --------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: read a resources workbook, run every row, print a
    summary. Returns a process exit code (0 if every row succeeded, 1 otherwise).

    Usage:
        uv run python -m great_lakes.batch_run_twl <resources.xlsx> <data_dir>
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "resources_path", type=Path,
        help="Path to the resources+config .xlsx workbook (see templates/template_twl.xlsx).",
    )
    parser.add_argument(
        "data_dir", type=Path,
        help="Directory containing the lake twl xlsx files (see LAKE_TWL_FILENAMES).",
    )
    args = parser.parse_args(argv)

    config = read_config_sheet(args.resources_path)
    summary = run_batch(args.resources_path, args.data_dir, config)
    print(format_summary(summary))
    return 0 if not summary.failed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
