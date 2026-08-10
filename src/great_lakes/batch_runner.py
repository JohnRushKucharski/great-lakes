"""Shared batch-run infrastructure for great_lakes's per-row Excel-driven batch scripts.

batch_run_avg.py and batch_run_twl.py both: read a resources-sheet row, validate/parse
it into a resource spec, resolve an output target, skip if that target repeats within
this run, skip/fail if the target already has output on disk and overwrite=False, run
job-specific work, and record a RowResult per row -- accumulating into a BatchSummary.
This module holds every piece of that shape once; each script supplies only what's
job-specific via the RowProcessor protocol (Strategy pattern: run_batch is the fixed
algorithm skeleton, RowProcessor is the swapped-in per-job behavior).

See CONTEXT.md for the "resource"/"resources sheet"/"config sheet" vocabulary shared
by both batch scripts.
"""

from dataclasses import dataclass
from datetime import datetime
from math import isnan
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

from great_lakes import run_readme as _run_readme

ResourceT = TypeVar("ResourceT")
# Contravariant: ConfigT only ever appears as a parameter type in RowProcessor's
# methods (never returned), which is what Protocol's strict variance checking expects.
ConfigT = TypeVar("ConfigT", contravariant=True)


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


def _require_str(row: dict[str, Any], field_name: str, errors: list[str]) -> str:
    value = row.get(field_name)
    if _is_blank(value):
        errors.append(f"{field_name!r} is required but missing or blank.")
        return ""
    return str(value).strip()


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


class RowValidationError(ValueError):
    """Raised when a resources-sheet row fails validation.

    Carries all validation problems found for the row (not just the first), so
    callers can report a complete picture per row.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class SheetValidationError(ValueError):
    """Raised when a template sheet (config or resources) fails header/structural
    validation -- i.e. problems with the sheet's shape itself, not with one row's data
    (see RowValidationError for that).

    Carries all validation problems found (not just the first).
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class RowResult:
    """Outcome of processing one resources-sheet row."""

    row_index: int  # 1-based position in the resources sheet's data rows
    resource_name: str | None
    component_name: str | None
    status: str  # "succeeded" | "failed"
    message: str | None = None
    # Every output file path written for this row (empty for failed rows).
    output_paths: tuple[Path, ...] = ()


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

    Each row invokes a full analysis (parsing, evaluation, optional plotting), which
    can take noticeable time -- without this, a batch run goes silent until the very
    end with no indication it's still working.
    """
    label = f"{resource_name or '?'}/{component_name or '?'}"
    print(f"[{row_index}/{total_rows}] {label}: {status}", flush=True)


class RowProcessor(Protocol[ResourceT, ConfigT]):
    """Job-specific behavior run_batch delegates to (Strategy pattern).

    One implementation per batch script (see batch_run_avg.py/batch_run_twl.py's
    private _AvgRowProcessor/_TwlRowProcessor). run_batch itself only knows this
    protocol -- it has no avg/twl-specific knowledge.
    """

    def read_rows(self, resources_path: Path) -> list[dict[str, Any]]:
        """Read the resources sheet into one raw row dict per row."""
        ...

    def parse(self, raw_row: dict[str, Any]) -> ResourceT:
        """Validate + parse one raw row. Raises RowValidationError if invalid."""
        ...

    def target(self, resource: ResourceT, config: ConfigT) -> tuple[Path, str]:
        """(output_folder, qualified_name) this row will write to -- used to detect
        two rows in the same batch resolving to the same output target."""
        ...

    def duplicate_message(self, output_folder: Path, resource: ResourceT) -> str:
        """Failure message for a row whose target() repeats an earlier row's."""
        ...

    def check_overwrite(self, resource: ResourceT, config: ConfigT) -> str | None:
        """Return a failure message if pre-existing output blocks this row (and
        config disallows overwriting it), else None. Jobs whose own build() already
        raises on pre-existing output (caught generically below) can just return
        None unconditionally here."""
        ...

    def build(self, resource: ResourceT, data_dir: Path, config: ConfigT) -> tuple[Path, ...]:
        """Do the actual per-row work; return every output path written. Any
        exception raised here is caught and reported as this row's failure message."""
        ...


def run_batch(
    resources_path: Path,
    data_dir: Path,
    config: ConfigT,
    processor: RowProcessor[ResourceT, ConfigT],
    progress: Callable[[int, int, str | None, str | None, str], None] = _default_progress,
) -> BatchSummary:
    """Process every resources-sheet row via `processor`, accumulating a BatchSummary.

    Continues past a failing row (bad row data, duplicate output target, pre-existing
    output with overwrite disallowed, or a processor.build() error) rather than
    aborting the whole batch; every row's outcome is captured in the returned
    BatchSummary.

    progress is injectable so callers can redirect/silence the real-time per-row
    status output (and so tests can capture it without parsing stdout). It's called
    once with status="running" when a row starts, and again with the final status
    ("succeeded"/"failed") when it finishes.
    """
    raw_rows = processor.read_rows(resources_path)
    total_rows = len(raw_rows)
    results: list[RowResult] = []
    seen_targets: set[tuple[Path, str]] = set()

    def _finish(row_index: int, resource_name: str | None, component_name: str | None,
               status: str, message: str | None = None,
               output_paths: tuple[Path, ...] = ()) -> None:
        results.append(
            RowResult(row_index, resource_name, component_name, status, message, output_paths)
        )
        progress(row_index, total_rows, resource_name, component_name, status)

    for row_index, raw_row in enumerate(raw_rows, start=1):
        resource_name = raw_row.get("resource_name")
        component_name = raw_row.get("component_name")
        progress(row_index, total_rows, resource_name, component_name, "running")
        try:
            resource = processor.parse(raw_row)
        except RowValidationError as exc:
            _finish(row_index, resource_name, component_name, "failed", str(exc))
            continue

        output_folder, qualified_name = processor.target(resource, config)
        target = (output_folder, qualified_name)
        if target in seen_targets:
            _finish(
                row_index, resource_name, component_name, "failed",
                processor.duplicate_message(output_folder, resource),
            )
            continue
        seen_targets.add(target)

        overwrite_error = processor.check_overwrite(resource, config)
        if overwrite_error is not None:
            _finish(row_index, resource_name, component_name, "failed", overwrite_error)
            continue

        try:
            output_paths = processor.build(resource, data_dir, config)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # continue-on-failure: any error in this row (bad data, a missing file, a
            # downstream validation error, ...) is reported and the batch moves on.
            _finish(row_index, resource_name, component_name, "failed", str(exc))
            continue

        _finish(row_index, resource_name, component_name, "succeeded",
               output_paths=tuple(output_paths))

    return BatchSummary(results=results)


def write_run_readme(
    resources_path: Path,
    data_dir: Path,
    output_directory: Path,
    summary: BatchSummary,
    naming_scheme_text: str,
    workspace_root: Path,
    now: datetime | None = None,
) -> Path:
    """Write output_directory/README.txt: a reproducibility record of one batch run.

    Thin wrapper around great_lakes.run_readme.write_readme -- the generic core
    shared with great_lakes.analysis's scripts (see CONTEXT.md's "Run readme"
    entry). Supplies this job's inputs (resources workbook + data directory), its
    results text (format_summary(summary)), and every succeeded row's output_paths
    as the written-files list.

    Always written -- even if every row failed or the batch produced zero rows --
    since the failure/timestamp/input information is useful precisely when a run
    didn't produce the expected output.
    """
    written_paths = [
        path for result in summary.results for path in result.output_paths
    ]
    return _run_readme.write_readme(
        output_directory=output_directory,
        title="Batch run report",
        inputs=[("resources workbook", resources_path), ("data directory", data_dir)],
        results_text=format_summary(summary),
        naming_scheme_text=naming_scheme_text,
        written_paths=written_paths,
        workspace_root=workspace_root,
        now=now,
    )

