"""Generic reproducibility-record writer, shared by batch_runner.write_run_readme
(per-row batch scripts) and great_lakes.analysis's scripts (no resources workbook,
no per-row succeeded/failed summary -- just a flat list of input files and outputs
written).

See CONTEXT.md's "Run readme" entry: documents the timestamp, inputs used, a
job-specific results/naming-scheme blurb, every file written this run, and any
pre-existing file under output_directory this run doesn't recognize as its own
(flagged as not created by this run).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

_README_FILENAME = "README.txt"


def _relative_label(path: Path, workspace_root: Path) -> str:
    """`path` expressed relative to `workspace_root` if possible, else its resolved
    absolute path (e.g. in ad-hoc/test scenarios where path isn't under
    workspace_root)."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(workspace_root.resolve()))
    except ValueError:
        return str(resolved)


def write_readme(
    output_directory: Path,
    title: str,
    inputs: Sequence[tuple[str, Path]],
    results_text: str,
    naming_scheme_text: str,
    written_paths: Iterable[Path],
    workspace_root: Path,
    now: datetime | None = None,
) -> Path:
    """Write output_directory/README.txt: a reproducibility record of one run.

    Always written -- even if `written_paths` is empty -- since the input/timestamp
    information is useful precisely when a run didn't produce the expected output.

    - `inputs`: (label, path) pairs describing this run's inputs (e.g. a resources
      workbook + data directory for a batch run, or one or more source data files
      for an analysis script).
    - `results_text`: job-specific results blurb (e.g. batch_runner.format_summary's
      succeeded/failed counts, or an analysis script's own "wrote N plots" summary).
    - `naming_scheme_text`: job-specific naming-scheme blurb.
    - `written_paths`: every file this run wrote -- used both to list "Files written
      this run" and to exclude those paths from the stale-file scan below.

    Recursively scans the whole output_directory tree for pre-existing files this
    run doesn't recognize as its own (or this README itself), flagging them as "not
    created by this run" -- catches stale output left by a prior run under a
    different layout.
    """
    now = now or datetime.now(timezone.utc)
    output_directory = Path(output_directory)
    readme_path = output_directory / _README_FILENAME

    lines = [
        title,
        "=" * len(title),
        "",
        f"Run timestamp (UTC): {now.isoformat()}",
        "",
        "Inputs",
        "------",
    ]
    for label, path in inputs:
        lines.append(f"{label}: {_relative_label(path, workspace_root)}")
    lines += [
        "",
        "Results",
        "-------",
        results_text,
        "",
        "Naming scheme",
        "-------------",
        naming_scheme_text,
        "",
        "Files written this run",
        "-----------------------",
    ]

    known_paths: set[Path] = {readme_path.resolve()}
    written_labels: list[str] = []
    for path in written_paths:
        known_paths.add(Path(path).resolve())
        written_labels.append(_relative_label(path, workspace_root))
    lines.extend(written_labels if written_labels else ["(none)"])

    lines += [
        "",
        "Pre-existing files not created by this run",
        "-------------------------------------------",
    ]
    stale_labels: list[str] = []
    if output_directory.exists():
        for path in sorted(output_directory.rglob("*")):
            if path.is_file() and path.resolve() not in known_paths:
                stale_labels.append(_relative_label(path, workspace_root))
    lines.extend(stale_labels if stale_labels else ["(none found)"])

    output_directory.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("\n".join(lines) + "\n")
    return readme_path
