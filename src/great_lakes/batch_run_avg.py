"""Batch-generate and run hydropattern .toml configs for Great Lakes resources.

Reads a resources.xlsx template (config sheet + resources sheet) and, for each row
of the resources sheet, generates one hydropattern .toml file (one component per row)
and runs it in-process against the corresponding lake's average lake-level timeseries
CSV (see clean_lake_levels_all_scenarios.py for how those CSVs are produced).

See CONTEXT.md for the "resource"/"resources sheet"/"config sheet"/"subdirectory
structure" vocabulary used throughout this file.
"""

from dataclasses import dataclass
from datetime import date
from math import isnan
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from hydropattern.cli import run as _hydropattern_cli_run  # type: ignore[import-untyped]

# Valid comparison symbols, mirrored from hydropattern.parsers._VALID_SYMBOLS. Kept as
# a local copy (rather than importing the private name) since this is example tooling,
# not a dependency on hydropattern internals.
_VALID_OPERATORS = frozenset({"<", "<=", ">", ">=", "=", "!="})

# lake code (as used in the resources sheet "lake" column) -> avg CSV filename produced
# by clean_lake_levels_all_scenarios.py.
LAKE_CSV_NAMES = {
    "superior": "superior_avg.csv",
    "michiganhuron": "michiganhuron_avg.csv",
    "stclair": "stclair_avg.csv",
    "erie": "erie_avg.csv",
    "ontario": "ontario_avg.csv",
}

# Non-leap reference year used only to compute a month's day-of-year. Leap-year
# effects are irrelevant here since hydropattern's own day-of-water-year conversion
# already normalizes them away (see timeseries.py:to_day_of_water_year).
_REFERENCE_YEAR = 2001


class RowValidationError(ValueError):
    """Raised when a resources-sheet row fails validation.

    Carries all validation problems found for the row (not just the first), so
    callers can report a complete picture per row.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class ResourceSpec:
    """Pure-data specification for one resources-sheet row.

    One ResourceSpec = one hydropattern component = one generated .toml = one run.
    """

    resource_name: str
    component_name: str
    lake: str
    success_pattern: bool = False
    verbose: bool = True
    timing: tuple[int, int] | None = None  # (first_doy, last_doy)
    magnitude: tuple[str, float, int] | None = None  # (operator, value, ma_periods)
    rate_of_change: tuple[str, float, int, int, float] | None = None
    # (operator, value, ma_periods, look_back, min_val)
    duration: tuple[str, int] | None = None  # (operator, value)
    threshold: float | None = None

    @property
    def qualified_name(self) -> str:
        """resource_name+component_name, used as the toml's [components.<name>]
        section name -- and therefore, via hydropattern's own naming, the prefix of
        every generated output filename. Needed because multiple rows commonly share
        one output folder (flat mode, the default), so component_name alone would
        collide across resources (e.g. two different resources both having a
        "high_water" component)."""
        return f"{self.resource_name}_{self.component_name}"


def month_to_doy(month: int) -> int:
    """Convert a calendar month number (1-12) to the day-of-year of its 1st day.

    Uses a fixed non-leap reference year; see _REFERENCE_YEAR for why leap years
    don't matter here.
    """
    if not 1 <= month <= 12:
        raise ValueError(f"month must be in range [1, 12], got {month!r}.")
    return date(_REFERENCE_YEAR, month, 1).timetuple().tm_yday


def resolve_lake_csv_path(lake: str, data_dir: Path) -> Path:
    """Resolve a lake code to its avg lake-level CSV path under data_dir."""
    return data_dir / LAKE_CSV_NAMES[lake]


def _is_blank(value: Any) -> bool:
    """True for None, NaN, empty string, or whitespace-only string (a blank cell)."""
    if value is None:
        return True
    if isinstance(value, float) and isnan(value):
        return True
    return isinstance(value, str) and value.strip() == ""


def _to_bool(value: Any, default: bool) -> bool:
    """Coerce a spreadsheet cell to bool; blank -> default.

    Excel string cells like "false" must be parsed by value, not by Python
    truthiness -- bool("false") is True, which would silently invert any
    string-boolean config cell (e.g. overwrite="false" -> True).
    """
    if _is_blank(value):
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1", "yes"):
            return True
        if normalized in ("false", "0", "no"):
            return False
        raise ValueError(f"Cannot parse {value!r} as a boolean.")
    return bool(value)


def _require_str(row: dict[str, Any], field: str, errors: list[str]) -> str:
    value = row.get(field)
    if _is_blank(value):
        errors.append(f"{field!r} is required but missing or blank.")
        return ""
    return str(value).strip()


def _validate_lake(lake: str, errors: list[str]) -> None:
    if lake and lake not in LAKE_CSV_NAMES:
        errors.append(
            f"Unknown lake {lake!r}; must be one of {sorted(LAKE_CSV_NAMES)}."
        )


def _parse_timing(row: dict[str, Any], errors: list[str]) -> tuple[int, int] | None:
    first = row.get("timing_first_month")
    last = row.get("timing_last_month")
    if _is_blank(first) and _is_blank(last):
        return None
    if first is None or _is_blank(first) or last is None or _is_blank(last):
        errors.append("timing requires both 'timing_first_month' and 'timing_last_month'.")
        return None
    try:
        first_doy = month_to_doy(int(first))
        last_doy = month_to_doy(int(last))
    except ValueError as exc:
        errors.append(f"timing: {exc}")
        return None
    return (first_doy, last_doy)


def _parse_magnitude(row: dict[str, Any], errors: list[str]) -> tuple[str, float, int] | None:
    operator = row.get("magnitude_operator")
    if _is_blank(operator):
        return None
    operator = str(operator).strip()
    value = row.get("magnitude_value")
    if value is None or _is_blank(value):
        errors.append("magnitude_operator is set but 'magnitude_value' is missing.")
        return None
    if operator not in _VALID_OPERATORS:
        errors.append(f"magnitude_operator {operator!r} is not a valid comparison symbol.")
        return None
    ma_periods = row.get("magnitude_ma_periods")
    ma_periods = 1 if ma_periods is None or _is_blank(ma_periods) else int(ma_periods)
    return (operator, float(value), ma_periods)


def _parse_rate_of_change(
    row: dict[str, Any], errors: list[str]
) -> tuple[str, float, int, int, float] | None:
    operator = row.get("rate_of_change_operator")
    if _is_blank(operator):
        return None
    operator = str(operator).strip()
    value = row.get("rate_of_change_value")
    if value is None or _is_blank(value):
        errors.append("rate_of_change_operator is set but 'rate_of_change_value' is missing.")
        return None
    if operator not in _VALID_OPERATORS:
        errors.append(f"rate_of_change_operator {operator!r} is not a valid comparison symbol.")
        return None
    ma_periods = row.get("rate_of_change_ma_periods")
    ma_periods = 1 if ma_periods is None or _is_blank(ma_periods) else int(ma_periods)
    look_back = row.get("rate_of_change_look_back")
    look_back = 1 if look_back is None or _is_blank(look_back) else int(look_back)
    min_val = row.get("rate_of_change_min_val")
    min_val = 0.0 if min_val is None or _is_blank(min_val) else float(min_val)
    return (operator, float(value), ma_periods, look_back, min_val)


def _parse_duration(row: dict[str, Any], errors: list[str]) -> tuple[str, int] | None:
    operator = row.get("duration_operator")
    if _is_blank(operator):
        return None
    operator = str(operator).strip()
    value = row.get("duration_value")
    if value is None or _is_blank(value):
        errors.append("duration_operator is set but 'duration_value' is missing.")
        return None
    if operator not in _VALID_OPERATORS:
        errors.append(f"duration_operator {operator!r} is not a valid comparison symbol.")
        return None
    return (operator, int(value))


def _parse_threshold(row: dict[str, Any], _errors: list[str]) -> float | None:
    """`errors` is unused here (a threshold value is never itself invalid), but the
    parameter is kept so this function's signature matches its `_parse_*` siblings,
    all of which are called uniformly as `parser(row, errors)`."""
    value = row.get("threshold")
    if value is None or _is_blank(value):
        return None
    return float(value)


@dataclass(frozen=True)
class BatchConfig:
    """Pure-data specification for the config-sheet options shared across all rows.

    `plot_show` is intentionally absent: it is always forced to False when building a
    .toml (see build_toml_text) so a batch run never spawns interactive plot windows.
    """

    first_day_of_water_year: int = 1
    metric_mode: str = "portion"  # portion | percentage | return_period
    excel: bool = True
    overwrite: bool = False
    output_directory: str = ""  # base output directory; required, no sensible default
    subdirectory_structure: str = "flat"  # "flat" | "resource" | "row"
    plot_enabled: bool = True
    plot_interpolate: bool = True
    plot_color_map: str = "RdBu"
    plot_color_map_ticks: tuple[float, ...] | None = None


_VALID_SUBDIRECTORY_STRUCTURES = ("flat", "resource", "row")


def resolve_output_folder(resource: ResourceSpec, config: BatchConfig) -> Path:
    """Compute the co-located .toml + output folder for one resource row.

    Pure/stateless: depends only on this row's resource_name/component_name and the
    config's output_directory/subdirectory_structure. Does NOT detect collisions
    between rows (e.g. two rows resolving to the same folder) -- that requires
    tracking state across rows in processing order, which belongs to the batch
    orchestration (run_batch), not this per-row path computation.

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


def _toml_str(value: str) -> str:
    """Format a python string as a quoted TOML basic string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _toml_array(values: list[Any]) -> str:
    def fmt(v: Any) -> str:
        if isinstance(v, str):
            return _toml_str(v)
        if isinstance(v, bool):
            return _toml_bool(v)
        return repr(float(v)) if isinstance(v, float) else str(v)
    return "[" + ", ".join(fmt(v) for v in values) + "]"


def _characteristic_lines(resource: ResourceSpec) -> list[str]:
    """Build characteristic lines in the fixed evaluation order: timing, magnitude,
    rate_of_change, duration. Order only matters when verbose=False (see
    hydropattern.parsing.requests.parse_request), but is kept fixed regardless for
    predictable, testable output.
    """
    lines: list[str] = []
    if resource.timing is not None:
        lines.append(f"timing = {_toml_array(list(resource.timing))}")
    if resource.magnitude is not None:
        lines.append(f"magnitude = {_toml_array(list(resource.magnitude))}")
    if resource.rate_of_change is not None:
        lines.append(f"rate_of_change = {_toml_array(list(resource.rate_of_change))}")
    if resource.duration is not None:
        lines.append(f"duration = {_toml_array(list(resource.duration))}")
    return lines


def build_toml_text(
    resource: ResourceSpec,
    timeseries_path: Path,
    output_directory: Path,
    config: BatchConfig,
) -> str:
    """Build the full .toml text for one resource (one component, one run).

    `show` is always hardcoded False regardless of config, so a batch run never
    spawns interactive plot windows. `threshold` comes from the row (resource),
    never from the shared config, since it's component/magnitude-specific.
    """
    lines: list[str] = []

    lines.append("[timeseries]")
    lines.append(f"path = {_toml_str(timeseries_path.as_posix())}")
    lines.append(f"first_day_of_water_year = {config.first_day_of_water_year}")
    lines.append("")

    lines.append(f"[components.{resource.qualified_name}]")
    if not resource.verbose:
        lines.append(f"verbose = {_toml_bool(resource.verbose)}")
    lines.extend(_characteristic_lines(resource))
    # Always emitted: hydropattern's own default is True, but this batch tool's
    # default is False, so omitting the key would silently flip behavior.
    lines.append(f"success_pattern = {_toml_bool(resource.success_pattern)}")
    lines.append("")

    lines.append("[output]")
    lines.append(f"directory = {_toml_str(output_directory.as_posix())}")
    lines.append(f"overwrite = {_toml_bool(config.overwrite)}")
    lines.append(f"excel = {_toml_bool(config.excel)}")
    lines.append("")

    lines.append("[output.metric]")
    lines.append(f"mode = {_toml_str(config.metric_mode)}")
    lines.append("")

    lines.append("[output.plot]")
    lines.append(f"enabled = {_toml_bool(config.plot_enabled)}")
    lines.append("")

    lines.append("[output.plot.climate-canvas]")
    lines.append(f"interpolate = {_toml_bool(config.plot_interpolate)}")
    lines.append("show = false")  # hardcoded: never spawn interactive windows in a batch run
    if resource.threshold is not None:
        lines.append(f"threshold = {resource.threshold!r}")
    lines.append(f"color_map = {_toml_str(config.plot_color_map)}")
    if config.plot_color_map_ticks is not None:
        lines.append(f"color_map_ticks = {_toml_array(list(config.plot_color_map_ticks))}")

    return "\n".join(lines) + "\n"


def parse_resource_row(row: dict[str, Any]) -> ResourceSpec:
    """Validate and parse one resources-sheet row into a ResourceSpec.

    Raises RowValidationError (carrying all problems found, not just the first) if
    the row is invalid.
    """
    errors: list[str] = []

    resource_name = _require_str(row, "resource_name", errors)
    component_name = _require_str(row, "component_name", errors)
    lake = _require_str(row, "lake", errors)
    _validate_lake(lake, errors)

    success_pattern = _to_bool(row.get("success_pattern"), default=False)
    verbose = _to_bool(row.get("verbose"), default=True)

    timing = _parse_timing(row, errors)
    magnitude = _parse_magnitude(row, errors)
    rate_of_change = _parse_rate_of_change(row, errors)
    duration = _parse_duration(row, errors)
    threshold = _parse_threshold(row, errors)

    if not errors and timing is None and magnitude is None \
            and rate_of_change is None and duration is None:
        errors.append(
            "Row has no characteristics: at least one of timing/magnitude/"
            "rate_of_change/duration must be populated."
        )

    if errors:
        raise RowValidationError(errors)

    return ResourceSpec(
        resource_name=resource_name,
        component_name=component_name,
        lake=lake,
        success_pattern=success_pattern,
        verbose=verbose,
        timing=timing,
        magnitude=magnitude,
        rate_of_change=rate_of_change,
        duration=duration,
        threshold=threshold,
    )


class SheetValidationError(ValueError):
    """Raised when a template sheet (config or resources) fails header/structural
    validation -- i.e. problems with the sheet's shape itself, not with one row's
    data (see RowValidationError for that).

    Carries all validation problems found (not just the first).
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


# ---- resources sheet -----------------------------------------------------------------

_RESOURCE_REQUIRED_COLUMNS = frozenset({"resource_name", "component_name", "lake"})
_RESOURCE_OPTIONAL_COLUMNS = frozenset({
    "success_pattern", "verbose",
    "timing_first_month", "timing_last_month",
    "magnitude_operator", "magnitude_value", "magnitude_ma_periods",
    "rate_of_change_operator", "rate_of_change_value", "rate_of_change_ma_periods",
    "rate_of_change_look_back", "rate_of_change_min_val",
    "duration_operator", "duration_value",
    "threshold",
})
_RESOURCE_ALL_COLUMNS = _RESOURCE_REQUIRED_COLUMNS | _RESOURCE_OPTIONAL_COLUMNS


def read_resources_sheet(path: Path, sheet_name: str = "resources") -> list[dict[str, Any]]:
    """Read the resources sheet into a list of raw row dicts (column name -> cell value).

    One dict per row.NaN/blank cells become None (not float('nan')) so downstream
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


# ---- config sheet ---------------------------------------------------------------------

_CONFIG_BOOL_KEYS = frozenset({"excel", "overwrite", "plot_enabled", "plot_interpolate"})
_CONFIG_INT_KEYS = frozenset({"first_day_of_water_year"})
_CONFIG_STR_KEYS = frozenset(
    {"metric_mode", "output_directory", "subdirectory_structure", "plot_color_map"}
)
_CONFIG_TICKS_KEY = "plot_color_map_ticks"
_CONFIG_KNOWN_KEYS = _CONFIG_BOOL_KEYS | _CONFIG_INT_KEYS | _CONFIG_STR_KEYS | {_CONFIG_TICKS_KEY}

_VALID_METRIC_MODES = frozenset({"portion", "percentage", "return_period"})


def _parse_color_map_ticks(raw: Any, errors: list[str]) -> tuple[float, ...] | None:
    if _is_blank(raw):
        return None
    try:
        return tuple(float(v.strip()) for v in str(raw).split(","))
    except ValueError:
        errors.append(
            f"Config sheet option 'plot_color_map_ticks' {raw!r} must be a "
            "comma-separated list of numbers."
        )
        return None


def read_config_sheet(path: Path, sheet_name: str = "config") -> BatchConfig:
    """Read the config sheet (key/value pairs: 'option' column, 'value' column) into
    a BatchConfig. Options left blank or absent fall back to BatchConfig's own
    defaults, except 'output_directory', which is required.
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

    ticks = _parse_color_map_ticks(values.get(_CONFIG_TICKS_KEY), errors)

    if errors:
        raise SheetValidationError(errors)

    defaults = BatchConfig()
    kwargs: dict[str, Any] = {"output_directory": str(output_directory).strip()}
    if not _is_blank(values.get("first_day_of_water_year")):
        kwargs["first_day_of_water_year"] = int(values["first_day_of_water_year"])
    if not _is_blank(metric_mode):
        kwargs["metric_mode"] = str(metric_mode).strip()
    if not _is_blank(values.get("excel")):
        kwargs["excel"] = _to_bool(values.get("excel"), defaults.excel)
    if not _is_blank(values.get("overwrite")):
        kwargs["overwrite"] = _to_bool(values.get("overwrite"), defaults.overwrite)
    if not _is_blank(subdirectory_structure):
        kwargs["subdirectory_structure"] = str(subdirectory_structure).strip()
    if not _is_blank(values.get("plot_enabled")):
        kwargs["plot_enabled"] = _to_bool(values.get("plot_enabled"), defaults.plot_enabled)
    if not _is_blank(values.get("plot_interpolate")):
        kwargs["plot_interpolate"] = _to_bool(
            values.get("plot_interpolate"), defaults.plot_interpolate
        )
    if not _is_blank(values.get("plot_color_map")):
        kwargs["plot_color_map"] = str(values["plot_color_map"]).strip()
    if ticks is not None:
        kwargs["plot_color_map_ticks"] = ticks

    return BatchConfig(**kwargs)


# ---- run_batch orchestration -----------------------------------------------------------

def _default_run_toml(toml_path: Path) -> None:
    """Invoke hydropattern's own CLI `run` command in-process for one generated .toml.

    run_toml_options=True means "run exactly as specified in the .toml's [output]
    section" -- correct here since build_toml_text already bakes every CLI-overridable
    option (plot, output dir, excel, overwrite, etc.) into the file, so no CLI
    overrides are needed (or wanted -- passing any would raise a CLI_CONFLICTING_OPTIONS
    error together with run_toml_options=True).

    Note: `run` is a typer command, so its optional parameters default to
    typer.Option/typer.Argument sentinel objects (used by Click for CLI parsing), not
    plain None. Calling it in-process (bypassing Click) means those sentinels must be
    overridden explicitly with None here, or run_toml_options's conflicting-options
    check would see them as "explicitly passed" and always raise.
    """
    _hydropattern_cli_run(
        path=str(toml_path),
        # These parameters are typed as plain bool/str/float/list (their typer.Option
        # CLI defaults), not Optional -- None is passed anyway per the docstring above,
        # which is why each of these lines needs a type: ignore.
        plot=None, output_directory=None, write_to_excel=None,  # type: ignore[arg-type]
        overwrite=None, interp=None, show=None, threshold=None,  # type: ignore[arg-type]
        color_map=None, color_map_ticks=None, fillin=None,  # type: ignore[arg-type]
        run_toml_options=True,
    )


def _expected_output_filenames(resource: ResourceSpec, config: BatchConfig) -> list[str]:
    """Deterministic output filenames hydropattern will write for one component.

    Excludes raw per-scenario CSV files (only produced when excel=False): those are
    named off scenario+component together using internal cleanup/collision logic
    (see hydropattern.formatters._build_all_filenames) that isn't safe to duplicate
    here, so they're intentionally not pre-checked.
    """
    name = resource.qualified_name
    filenames = [f"{name}.toml", f"{name}_summary.xlsx"]
    if config.excel:
        filenames.append(f"{name}_output.xlsx")
    if config.plot_enabled:
        filenames.append(f"{name}_grid.csv")
        filenames.append(f"{name}_plot.png")
    return filenames


@dataclass(frozen=True)
class RowResult:
    """Outcome of processing one resources-sheet row."""

    row_index: int  # 1-based position in the resources sheet's data rows
    resource_name: str | None
    component_name: str | None
    status: str  # "succeeded" | "failed"
    message: str | None = None


@dataclass(frozen=True)
class BatchSummary:
    """End-of-run report for a full run_batch call."""

    results: list[RowResult]

    @property
    def succeeded(self) -> list[RowResult]:
        return [r for r in self.results if r.status == "succeeded"]

    @property
    def failed(self) -> list[RowResult]:
        return [r for r in self.results if r.status == "failed"]


def format_summary(summary: BatchSummary) -> str:
    """Human-readable end-of-run report: counts + one line per failed row."""
    lines = [
        f"{len(summary.succeeded)} succeeded, {len(summary.failed)} failed "
        f"out of {len(summary.results)} row(s)."
    ]
    for result in summary.failed:
        lines.append(
            f"  Row {result.row_index} ({result.resource_name!r}, "
            f"{result.component_name!r}): {result.message}"
        )
    return "\n".join(lines)


def _default_progress(row_index: int, total_rows: int, resource_name: str | None,
                      component_name: str | None, status: str) -> None:
    """Prints one line per row as it starts and finishes.

    Each row invokes a full hydropattern analysis (parsing, evaluation, optional
    plotting), which can take noticeable time -- without this, a batch run goes
    silent until the very end with no indication it's still working.
    """
    label = f"{resource_name or '?'}/{component_name or '?'}"
    print(f"[{row_index}/{total_rows}] {label}: {status}", flush=True)


def run_batch(
    resources_path: Path,
    data_dir: Path,
    config: BatchConfig,
    run_toml: Callable[[Path], None] = _default_run_toml,
    progress: Callable[[int, int, str | None, str | None, str], None] = _default_progress,
) -> BatchSummary:
    """Generate + run one hydropattern .toml per resources-sheet row.

    Continues past a failing row (bad row data, duplicate output folder, pre-existing
    output with overwrite=False, or a hydropattern run error) rather than aborting the
    whole batch; every row's outcome is captured in the returned BatchSummary.

    run_toml is injectable so tests can mock the actual hydropattern invocation without
    running a full analysis. progress is injectable for the same reason (and to let
    callers redirect/silence the real-time per-row status output); it's called once
    with status="running" when a row starts, and again with the final status
    ("succeeded"/"failed") when it finishes.
    """
    raw_rows = read_resources_sheet(resources_path)
    total_rows = len(raw_rows)
    results: list[RowResult] = []
    seen_targets: set[tuple[Path, str]] = set()

    def _finish(row_index: int, resource_name: str | None, component_name: str | None,
               status: str, message: str | None = None) -> None:
        results.append(RowResult(row_index, resource_name, component_name, status, message))
        progress(row_index, total_rows, resource_name, component_name, status)

    for row_index, raw_row in enumerate(raw_rows, start=1):
        resource_name = raw_row.get("resource_name")
        component_name = raw_row.get("component_name")
        progress(row_index, total_rows, resource_name, component_name, "running")
        try:
            resource = parse_resource_row(raw_row)
        except RowValidationError as exc:
            _finish(row_index, resource_name, component_name, "failed", str(exc))
            continue

        output_folder = resolve_output_folder(resource, config)
        target = (output_folder, resource.qualified_name)
        if target in seen_targets:
            _finish(
                row_index, resource.resource_name, resource.component_name, "failed",
                f"Duplicate output folder+component within this batch run: "
                f"{output_folder / f'{resource.qualified_name}.toml'}",
            )
            continue
        seen_targets.add(target)

        if not config.overwrite and output_folder.exists():
            existing = [
                name for name in _expected_output_filenames(resource, config)
                if (output_folder / name).exists()
            ]
            if existing:
                _finish(
                    row_index, resource.resource_name, resource.component_name, "failed",
                    f"Output already exists and overwrite=False: {output_folder} "
                    f"(found {', '.join(existing)}).",
                )
                continue

        try:
            timeseries_path = resolve_lake_csv_path(resource.lake, data_dir)
            output_folder.mkdir(parents=True, exist_ok=True)
            toml_text = build_toml_text(resource, timeseries_path, output_folder, config)
            toml_path = output_folder / f"{resource.qualified_name}.toml"
            toml_path.write_text(toml_text, encoding="utf-8")
            run_toml(toml_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # continue-on-failure: any error in this row (bad data, a missing file, a
            # hydropattern validation error, ...) is reported and the batch moves on.
            _finish(row_index, resource.resource_name, resource.component_name,
                   "failed", str(exc))
            continue

        _finish(row_index, resource.resource_name, resource.component_name, "succeeded")

    return BatchSummary(results=results)


# ---- CLI entry point --------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: read a resources workbook, run every row, print a
    summary. Returns a process exit code (0 if every row succeeded, 1 otherwise).

    Usage:
        uv run python examples/great_lakes/batch_run_avg.py <resources.xlsx> <data_dir>
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "resources_path", type=Path,
        help="Path to the resources+config .xlsx workbook (see templates/template_avg.xlsx).",
    )
    parser.add_argument(
        "data_dir", type=Path,
        help="Directory containing the lake avg-level CSVs (see LAKE_CSV_NAMES).",
    )
    args = parser.parse_args(argv)

    config = read_config_sheet(args.resources_path)
    summary = run_batch(args.resources_path, args.data_dir, config)
    print(format_summary(summary))
    return 0 if not summary.failed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
