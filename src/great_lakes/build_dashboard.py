"""Build a self-contained results dashboard for batch_run_swl.py outputs.

Reads one or more batch_run_swl.py resources+config workbooks (already run, with
outputs already written to disk -- see config sheet's output_directory) and produces:

- manifest.js: a sidecar JS file (`window.MANIFEST = {...};`) embedding per-row
  metadata, grid csv data, and relative paths to plot pngs.
- dashboard.html: a static, self-contained html page that reads window.MANIFEST to
  drive filter dropdowns (save point, magnitude, runup allowance, equivalent-elevation
  basis) and an output-kind picker (plot/grid x return_period/equivalent_elevation/
  elevation_delta), letting a user inspect one run or compare two side by side.

manifest.js is a plain JS sidecar (not embedded directly in dashboard.html, and not a
live-fetched .json/.csv) so it can be loaded via a <script src="manifest.js"> tag,
which -- unlike fetch()/XMLHttpRequest -- is not blocked by browsers' file:// CORS
restrictions. This lets the whole dashboard run with zero install and zero local
server: just double-click dashboard.html. See
docs/adr/0002-sidecar-js-manifest-for-longtailpoint-dashboard.md.
"""

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from great_lakes import batch_run_avg as avg
from great_lakes import batch_run_swl as swl
from great_lakes import common_swl

# Resolved equivalent_elevation keyword, mirrored from batch_run_swl.py's
# _BASELINE_MAGNITUDE_KEYWORD (kept as a local copy rather than importing the private
# name, same rationale as batch_run_swl.py's own _VALID_OPERATORS copy).
_BASELINE_MAGNITUDE_KEYWORD = "baseline_magnitude"

# output-kind key -> filename suffix, shared by resolve_files and build_manifest.
_FILE_SUFFIXES = {
    "grid": "_grid.csv",
    "plot": "_plot.png",
    "equivalent_elevation_grid": "_equivalent_elevation_grid.csv",
    "equivalent_elevation_plot": "_equivalent_elevation_plot.png",
    "elevation_delta_grid": "_elevation_delta_grid.csv",
    "elevation_delta_plot": "_elevation_delta_plot.png",
}
# The 4 output kinds gated on equivalent_elevation_basis being set (not None).
_EQUIVALENT_ELEVATION_KINDS = frozenset(
    {"equivalent_elevation_grid", "equivalent_elevation_plot",
     "elevation_delta_grid", "elevation_delta_plot"}
)
# The 2 save-point threshold-ARI elevation kinds, gated on entry.threshold being set
# (not None) rather than a filename suffix under entry.output_dir/file_stem -- their
# paths are already fully resolved on the entry itself (see build_entries), since
# they're shared across every entry for the same save point (not per-entry-stem like
# every other kind here). See CONTEXT.md's "Threshold-ARI elevation" entry.
_THRESHOLD_ARI_KINDS = ("threshold_ari_elevation_grid", "threshold_ari_elevation_plot")
_GRID_KINDS = frozenset(
    {"grid", "equivalent_elevation_grid", "elevation_delta_grid", "threshold_ari_elevation_grid"}
)
# Primary output kinds (always attempted, whether or not equivalent_elevation is set).
# A missing primary file is treated as a soft failure (e.g. a plot that failed to
# render for a degenerate/flat grid) -- the dashboard shows a message instead of
# aborting the whole build. Missing equivalent_elevation/elevation_delta files, by
# contrast, are still a fail-loud data-integrity signal (see resolve_files).
_PRIMARY_KINDS = frozenset({"grid", "plot"})
# Sentinel marking a primary file that was expected but not found on disk.
MISSING = "__missing__"


def compute_magnitude_ft(resource: "swl.ResourceSpec") -> float:
    """Convert resource.magnitude_value (meters, IGLD85) to feet, NAVD88.

    Used for dashboard filtering/display, since the raw meters-IGLD85 value (and the
    filename numbers derived from it) aren't a human-friendly/authoritative NAVD88
    elevation on their own -- see CONTEXT.md's "Equivalent elevation" definition.
    """
    return common_swl.m_igld85_to_ft_NAVD88(resource.magnitude_value)


def compute_equivalent_elevation_basis(row: dict[str, Any], resource: "swl.ResourceSpec") -> str | None:
    """Resolve a row's equivalent_elevation into a dashboard filter/display label.

    None -> None (resource.equivalent_elevation is None; row has no
    equivalent_elevation/elevation_delta outputs). The raw resources-sheet cell
    (case-insensitive) equal to "baseline_magnitude" -> "baseline_magnitude". Anything
    else (a numeric override) -> an explicit override label in ft, NAVD88 (e.g.
    "586.44 ft override"), converted from resource.equivalent_elevation (meters,
    IGLD85) -- see CONTEXT.md's "Equivalent-elevation basis" definition.
    """
    if resource.equivalent_elevation is None:
        return None
    raw = row.get("equivalent_elevation")
    if isinstance(raw, str) and raw.strip().lower() == _BASELINE_MAGNITUDE_KEYWORD:
        return _BASELINE_MAGNITUDE_KEYWORD
    override_ft = common_swl.m_igld85_to_ft_NAVD88(resource.equivalent_elevation)
    return f"{override_ft:.2f} ft override"


@dataclass(frozen=True)
class ManifestEntry:
    """One resources-sheet row's dashboard-relevant identity + where its outputs live.

    save_point_id, magnitude_ft, and component_name (runup allowance) together are the
    dashboard's 3 identifying filters -- see merge_and_validate, which enforces they
    always resolve to exactly one entry. equivalent_elevation_basis is retained as
    metadata (surfaced in the manifest) but is no longer a dashboard filter -- see
    CONTEXT.md's "Equivalent-elevation basis" entry.
    """

    workbook_path: Path
    analysis_type: str  # "swl" or "avg" -- see build_entries / build_avg_entries
    resource_name: str
    component_name: str  # runup allowance label, e.g. "base"/"run2"/"run25"/"run3"
    save_point_id: Any
    magnitude_ft: float
    equivalent_elevation_basis: str | None
    qualified_name: str
    output_dir: Path
    # On-disk file-name stem (no suffix), per the workbook's config.filename_style --
    # equals qualified_name for "qualified_name" style (and always for avg entries,
    # which have no filename_style concept) or common_swl.output_file_stem's ft-based
    # stem for "elevation_runup_savepoint" style. resolve_files uses this (not
    # qualified_name) to find each entry's actual output files.
    file_stem: str
    # The actual crest elevation being evaluated: magnitude_ft + this component's
    # runup allowance (common_swl.RUNUP_FT_BY_COMPONENT), or just magnitude_ft for avg
    # entries (no runup allowance concept there). Used by the dashboard's "Elevation
    # (NAVD88)" picker instead of the raw magnitude_ft, since the runup allowance
    # itself is already a separate picker ("Runup (ft)").
    elevation_ft: float
    # The numeric runup allowance itself (common_swl.RUNUP_FT_BY_COMPONENT's value for
    # component_name), 0.0 for avg entries. The dashboard's "Runup (ft)" picker filters
    # on this numeric value directly (not the raw component_name code) -- see
    # CONTEXT.md's "Runup allowance" entry.
    runup_ft: float = 0.0
    # resource.threshold (the target ARI, in years) -- None for avg entries and for
    # swl rows with a blank threshold cell (no threshold_ari_elevation output). See
    # CONTEXT.md's "Threshold-ARI elevation" entry.
    threshold: float | None = None
    # The save-point threshold-ARI elevation output's grid csv/plot png paths (see
    # batch_run_swl.resolve_save_point_ari_elevation_output_paths) -- shared across
    # every entry for the same save point, unlike this entry's own output_dir/
    # file_stem-based files. None when threshold is None.
    threshold_ari_grid_path: Path | None = None
    threshold_ari_plot_path: Path | None = None


def build_entries(workbook_path: Path) -> list[ManifestEntry]:
    """Read one workbook's config+resources sheets into a list of ManifestEntry.

    Does not touch the output files themselves (see resolve_files for that) -- this
    only resolves each row's identity and where its output folder *should* be, per the
    workbook's own config sheet.
    """
    config = swl.read_config_sheet(workbook_path)
    rows = swl.read_resources_sheet(workbook_path)
    entries = []
    for row in rows:
        resource = swl.parse_resource_row(row)
        output_dir = swl.resolve_output_folder(resource, config)
        magnitude_ft = compute_magnitude_ft(resource)
        runup_ft = common_swl.RUNUP_FT_BY_COMPONENT.get(resource.component_name, 0.0)
        threshold_ari_grid_path = threshold_ari_plot_path = None
        if resource.threshold is not None:
            threshold_ari_grid_path, threshold_ari_plot_path = (
                swl.resolve_save_point_ari_elevation_output_paths(resource, config)
            )
        entries.append(
            ManifestEntry(
                workbook_path=workbook_path,
                analysis_type="swl",
                resource_name=resource.resource_name,
                component_name=resource.component_name,
                save_point_id=resource.save_point_id,
                magnitude_ft=magnitude_ft,
                equivalent_elevation_basis=compute_equivalent_elevation_basis(row, resource),
                qualified_name=resource.qualified_name,
                output_dir=output_dir,
                file_stem=swl.resolve_output_stem(resource, config),
                elevation_ft=magnitude_ft + runup_ft,
                runup_ft=runup_ft,
                threshold=resource.threshold,
                threshold_ari_grid_path=threshold_ari_grid_path,
                threshold_ari_plot_path=threshold_ari_plot_path,
            )
        )
    return entries


def build_avg_entries(workbook_path: Path) -> list[ManifestEntry]:
    """Read one batch_run_avg.py workbook's config+resources sheets into a list of
    ManifestEntry (analysis_type "avg").

    batch_run_avg.py has no save_point_id or equivalent_elevation concept, so those
    fields are always None for avg entries. Every row must have a magnitude
    characteristic (resource.magnitude), since that's what the dashboard's magnitude
    filter/label is derived from -- raises ValueError (mentioning "magnitude") for any
    row missing one, rather than silently excluding it.
    """
    config = avg.read_config_sheet(workbook_path)
    rows = avg.read_resources_sheet(workbook_path)
    entries = []
    for row in rows:
        resource = avg.parse_resource_row(row)
        if resource.magnitude is None:
            raise ValueError(
                f"{workbook_path.name}:{resource.qualified_name} has no magnitude "
                "characteristic; the dashboard requires one to filter/label avg rows."
            )
        output_dir = avg.resolve_output_folder(resource, config)
        magnitude_value = resource.magnitude[1]
        magnitude_ft = common_swl.m_igld85_to_ft_NAVD88(magnitude_value)
        entries.append(
            ManifestEntry(
                workbook_path=workbook_path,
                analysis_type="avg",
                resource_name=resource.resource_name,
                component_name=resource.component_name,
                save_point_id=None,
                magnitude_ft=magnitude_ft,
                equivalent_elevation_basis=None,
                qualified_name=resource.qualified_name,
                output_dir=output_dir,
                file_stem=resource.qualified_name,
                elevation_ft=magnitude_ft,
            )
        )
    return entries


def resolve_files(entry: ManifestEntry) -> dict[str, Path | None | str]:
    """Resolve one entry's possible output file paths, verifying they exist.

    The 4 equivalent_elevation/elevation_delta kinds resolve to None (not expected to
    exist) when entry.equivalent_elevation_basis is None. The 2 threshold_ari_elevation
    kinds resolve to None when entry.threshold is None. When either pair IS expected
    (basis/threshold is set) but missing on disk, that's a fail-loud data-integrity
    signal -- raises FileNotFoundError rather than silently omitting it. The 2 primary
    kinds (grid/plot) are always attempted; if missing (e.g. a run whose plot failed to
    render for a degenerate/flat grid), they resolve to the MISSING sentinel instead of
    raising, so one bad row doesn't abort the whole dashboard build.
    """
    files: dict[str, Path | None | str] = {}
    for kind, suffix in _FILE_SUFFIXES.items():
        if kind in _EQUIVALENT_ELEVATION_KINDS and entry.equivalent_elevation_basis is None:
            files[kind] = None
            continue
        path = entry.output_dir / f"{entry.file_stem}{suffix}"
        if not path.exists():
            if kind in _PRIMARY_KINDS:
                files[kind] = MISSING
                continue
            raise FileNotFoundError(
                f"Expected output file missing for {entry.qualified_name!r} "
                f"({kind}): {path}"
            )
        files[kind] = path

    if entry.threshold is None:
        for kind in _THRESHOLD_ARI_KINDS:
            files[kind] = None
    else:
        threshold_ari_paths = {
            "threshold_ari_elevation_grid": entry.threshold_ari_grid_path,
            "threshold_ari_elevation_plot": entry.threshold_ari_plot_path,
        }
        for kind, ari_path in threshold_ari_paths.items():
            if ari_path is None or not ari_path.exists():
                raise FileNotFoundError(
                    f"Expected output file missing for {entry.qualified_name!r} "
                    f"({kind}): {ari_path}"
                )
            files[kind] = ari_path
    return files


def merge_and_validate(entries_lists: list[list[ManifestEntry]]) -> list[ManifestEntry]:
    """Flatten entries from every included workbook, and validate the dashboard's 3
    identifying filters (save_point_id, magnitude_ft, component_name) always resolve
    to exactly one entry.

    Raises ValueError (listing every offending group) if any combination is shared by
    more than one entry -- the dashboard's filters must always disambiguate to a
    single row, per CONTEXT.md.
    """
    all_entries = [entry for entries in entries_lists for entry in entries]
    groups: dict[tuple[str, Any, float, str], list[ManifestEntry]] = {}
    for entry in all_entries:
        key = (
            entry.analysis_type,
            entry.save_point_id,
            round(entry.magnitude_ft, 2),
            entry.component_name,
        )
        groups.setdefault(key, []).append(entry)

    duplicates = {key: group for key, group in groups.items() if len(group) > 1}
    if duplicates:
        lines = [
            f"{key} -> " + ", ".join(f"{e.workbook_path.name}:{e.qualified_name}" for e in group)
            for key, group in duplicates.items()
        ]
        raise ValueError(
            "Non-unique filter combination(s) found (analysis_type, save_point_id, "
            "magnitude_ft, component_name); the dashboard's filters must always "
            "resolve to exactly one row:\n" + "\n".join(lines)
        )
    return all_entries


def read_grid_csv(path: Path) -> dict[str, Any]:
    """Parse a batch_run_swl.py `_grid.csv` (`temp_delta\\precip_delta` header row, one
    row per temp_delta, one column per precip_delta, blank cells for scenarios outside
    the valid grid) into row/column labels + a values matrix for JS table rendering.

    Blank/NaN cells become None (JSON `null`), not float('nan') (invalid JSON).
    """
    df = pd.read_csv(path, index_col=0)
    col_labels = [str(c) for c in df.columns]
    row_labels = [str(r) for r in df.index]
    values = [
        [None if pd.isna(v) else float(v) for v in row]
        for row in df.itertuples(index=False, name=None)
    ]
    return {"row_labels": row_labels, "col_labels": col_labels, "values": values}


def build_manifest(entries: list[ManifestEntry], dashboard_dir: Path) -> dict[str, Any]:
    """Assemble the full JSON-serializable manifest for every entry.

    Grid-kind files (grid/equivalent_elevation_grid/elevation_delta_grid) embed their
    numeric data directly (via read_grid_csv). Plot-kind files (png) are recorded as a
    relative path (relative to dashboard_dir, where dashboard.html/manifest.js will
    live) for an <img src=...> tag to load directly -- no data embedding needed for
    images.
    """
    manifest_entries = []
    for entry in entries:
        files = resolve_files(entry)
        baseline_ari = None
        grid_path = files.get("grid")
        if isinstance(grid_path, Path):
            grid_data = read_grid_csv(grid_path)
            first_row = grid_data["values"][0] if grid_data["values"] else []
            if first_row and first_row[0] is not None:
                baseline_ari = first_row[0]
        file_entries: dict[str, Any] = {}
        for kind, path in files.items():
            if path is None:
                file_entries[kind] = None
            elif path == MISSING:
                expected_name = f"{entry.qualified_name}{_FILE_SUFFIXES[kind]}"
                file_entries[kind] = {
                    "type": "missing",
                    "message": f"File not found: {expected_name}",
                }
            elif kind in _GRID_KINDS:
                assert isinstance(path, Path)
                rel_path = Path(os.path.relpath(path, dashboard_dir)).as_posix()
                file_entries[kind] = {
                    "type": "grid", "data": read_grid_csv(path), "path": rel_path,
                }
            else:
                rel_path = Path(os.path.relpath(path, dashboard_dir)).as_posix()
                file_entries[kind] = {"type": "image", "path": rel_path}
        manifest_entries.append(
            {
                "analysis_type": entry.analysis_type,
                "resource_name": entry.resource_name,
                "component_name": entry.component_name,
                "save_point_id": entry.save_point_id,
                "magnitude_ft": round(entry.magnitude_ft, 2),
                "elevation_ft": round(entry.elevation_ft, 2),
                "runup_ft": round(entry.runup_ft, 2),
                "baseline_ari": round(baseline_ari, 4) if baseline_ari is not None else None,
                "equivalent_elevation_basis": entry.equivalent_elevation_basis,
                "qualified_name": entry.qualified_name,
                "files": file_entries,
            }
        )
    return {"entries": manifest_entries}


def write_manifest_js(manifest: dict[str, Any], path: Path) -> None:
    """Write manifest as a `window.MANIFEST = {...};` JS sidecar file.

    A <script src="manifest.js"> tag loading this isn't subject to the file:// CORS
    restriction that blocks fetch()/XMLHttpRequest of a real .json file -- see
    docs/adr/0002-sidecar-js-manifest-for-longtailpoint-dashboard.md.
    """
    path.write_text(f"window.MANIFEST = {json.dumps(manifest, indent=2)};\n", encoding="utf-8")


_DASHBOARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Long Tail Point Dashboard</title>
<script src="manifest.js"></script>
<style>
  :root {
    --bg: #F8FAFC; --surface: #FFFFFF; --surface-hover: #F1F5F9;
    --border: #E2E8F0; --text: #0F172A; --text-muted: #64748B;
    --primary: #2563EB; --primary-hover: #1D4ED8; --compare: #7C3AED;
    --radius: 8px;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0; background: var(--bg); color: var(--text);
  }
  h1 {
    font-size: 1.25rem; font-weight: 700; margin: 0; padding: 16px 24px;
    background: var(--surface); border-bottom: 1px solid var(--border);
  }
  .topbar {
    position: sticky; top: 0; z-index: 10; background: var(--surface);
    border-bottom: 1px solid var(--border); padding: 16px 24px;
    display: flex; flex-wrap: wrap; align-items: center; gap: 24px;
  }
  .filters {
    display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end;
    background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 8px 12px;
  }
  .filters label {
    display: flex; flex-direction: column; gap: 4px;
    font-size: 0.75rem; font-weight: 500; color: var(--text-muted);
  }
  select, input[type="checkbox"] { font-family: inherit; }
  select {
    font-size: 0.875rem; color: var(--text); background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px;
    min-width: 9rem; transition: border-color 0.15s ease-in-out, background 0.15s ease-in-out;
  }
  select:hover { background: var(--surface-hover); border-color: #CBD5E1; }
  select:focus-visible, input:focus-visible, button:focus-visible {
    outline: 2px solid var(--primary); outline-offset: 2px; border-color: var(--primary);
  }
  #compare-toggle-wrap { display: flex; align-items: center; gap: 8px; font-size: 0.875rem; font-weight: 500; }
  #compare-toggle-wrap label { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  #compare-toggle { width: 16px; height: 16px; accent-color: var(--compare); cursor: pointer; }
  main { padding: 24px; }
  .panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 24px; align-items: start; }
  .panel-column {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px; min-width: 0;
  }
  #panel-b-column { border-left: 3px solid var(--compare); }
  .panel-column h2 {
    font-size: 1rem; font-weight: 600; margin: 0 0 12px 0; color: var(--text-muted);
  }
  .panel { min-width: 0; margin-top: 12px; }
  .panel img { max-width: 100%; border-radius: 6px; border: 1px solid var(--border); display: block; }
  .empty-state {
    display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
    color: var(--text-muted); font-size: 0.875rem; padding: 16px 0;
  }
  .empty-state button {
    font-size: 0.8125rem; font-weight: 500; color: #fff; background: var(--primary);
    border: none; border-radius: 6px; padding: 6px 12px; cursor: pointer;
    transition: background 0.15s ease-in-out;
  }
  .empty-state button:hover { background: var(--primary-hover); }
  table { border-collapse: collapse; font-size: 0.8125rem; font-variant-numeric: tabular-nums; }
  td, th { border: 1px solid var(--border); padding: 4px 8px; text-align: right; }
  th { background: var(--bg); font-weight: 600; }
  .file-path-caption { font-size: 0.75rem; color: var(--text-muted); margin-top: 8px; word-break: break-all; }
  .initial-filter {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 12px 24px; display: flex; flex-wrap: wrap; align-items: flex-end; gap: 24px;
  }
  .initial-filter .criterion-toggle {
    display: flex; flex-direction: column; gap: 4px;
  }
  .initial-filter .criterion-toggle > span {
    font-size: 0.75rem; font-weight: 500; color: var(--text-muted);
  }
  .initial-filter .criterion-toggle .options {
    display: flex; gap: 12px; font-size: 0.875rem;
  }
  .initial-filter .criterion-toggle label {
    display: flex; align-items: center; gap: 4px; cursor: pointer; font-weight: 400;
  }
  .initial-filter .range-group {
    display: flex; flex-direction: column; gap: 4px;
  }
  .initial-filter .range-group > span {
    font-size: 0.75rem; font-weight: 500; color: var(--text-muted);
  }
  .initial-filter .range-group.disabled { opacity: 0.45; pointer-events: none; }
  .initial-filter .range-inputs { display: flex; align-items: center; gap: 6px; }
  .initial-filter .range-inputs select, .initial-filter .range-inputs input[type="number"] {
    font-family: inherit; font-size: 0.875rem; color: var(--text); background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; width: 6rem;
  }
  .initial-filter .range-inputs select:hover, .initial-filter .range-inputs input[type="number"]:hover {
    background: var(--surface-hover); border-color: #CBD5E1;
  }
  /* Hide the native up/down spinner UI on ARI number inputs -- rule (3): typing a
     value directly is the intended interaction, the spinner buttons just add visual
     noise for a 1-1000 range a user will always type rather than click through. */
  .initial-filter .range-inputs input[type="number"]::-webkit-outer-spin-button,
  .initial-filter .range-inputs input[type="number"]::-webkit-inner-spin-button {
    -webkit-appearance: none; margin: 0;
  }
  .initial-filter .range-inputs input[type="number"] { appearance: textfield; -moz-appearance: textfield; }
  .initial-filter .range-inputs span { color: var(--text-muted); font-size: 0.8125rem; }
  #initial-filter-reset {
    font-size: 0.8125rem; font-weight: 500; color: var(--text); background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; cursor: pointer;
    transition: background 0.15s ease-in-out;
  }
  #initial-filter-reset:hover { background: var(--surface-hover); }
  #initial-filter-count {
    font-size: 0.8125rem; font-weight: 600; color: var(--primary); margin-left: auto;
  }
  #initial-filter-error {
    font-size: 0.8125rem; font-weight: 500; color: #B91C1C; background: #FEF2F2;
    border: 1px solid #FCA5A5; border-radius: 6px; padding: 6px 10px; display: none;
  }
  #initial-filter-error.visible { display: block; }
</style>
</head>
<body>
<h1>Long Tail Point Dashboard</h1>

<div class="initial-filter">
  <div class="criterion-toggle">
    <span>Filter by</span>
    <div class="options">
      <label>
        <input type="radio" name="initial-filter-criterion" value="elevation" checked>
        Elevation
      </label>
      <label>
        <input type="radio" name="initial-filter-criterion" value="baseline_ari">
        Baseline ARI
      </label>
    </div>
  </div>
  <div class="range-group" id="initial-elev-group">
    <span>Elevation (NAVD88, ft)</span>
    <div class="range-inputs">
      <select id="initial-elev-min"></select>
      <span>&ndash;</span>
      <select id="initial-elev-max"></select>
    </div>
  </div>
  <div class="range-group disabled" id="initial-ari-group">
    <span>Baseline ARI (yr)</span>
    <div class="range-inputs">
      <input type="number" id="initial-ari-min" placeholder="min" min="1" max="1000">
      <span>&ndash;</span>
      <input type="number" id="initial-ari-max" placeholder="max" min="1" max="1000">
    </div>
  </div>
  <button type="button" id="initial-filter-reset">Reset filter</button>
  <span id="initial-filter-count"></span>
  <div id="initial-filter-error"></div>
</div>

<div class="topbar">
  <div class="filters">
    <label id="analysis-type-wrap">Water Level Type
      <select id="analysis-select"></select>
    </label>
    <label>Analysis
      <select id="metric-select">
        <option value="primary">Return Interval</option>
        <option value="equivalent_elevation" class="swl-only">Equivalent Elevation</option>
        <option value="elevation_delta" class="swl-only">Elevation Delta</option>
        <option value="threshold_ari_elevation" class="swl-only">Threshold ARI Elevation</option>
      </select>
    </label>
    <label>Form
      <select id="form-select">
        <option value="plot">Plot</option>
        <option value="grid">Grid</option>
      </select>
    </label>
  </div>
  <div id="compare-toggle-wrap">
    <label><input type="checkbox" id="compare-toggle"> Compare to a second selection</label>
  </div>
</div>

<main>
<div class="panels">
  <div class="panel-column">
    <h2>A</h2>
    <div class="filters">
      <label id="save-point-wrap">Save point
        <select id="save-point-select"></select>
      </label>
      <label id="magnitude-wrap">Elevation (NAVD88, ft)
        <select id="magnitude-select"></select>
      </label>
      <label id="runup-wrap">Runup (ft)
        <select id="runup-select"></select>
      </label>
    </div>
    <div class="panel" id="panel-a"></div>
  </div>
  <div class="panel-column" id="panel-b-column" style="display:none">
    <h2>B (compare)</h2>
    <div class="filters">
      <label id="save-point-wrap-b">Save point
        <select id="save-point-select-b"></select>
      </label>
      <label id="magnitude-wrap-b">Elevation (NAVD88, ft)
        <select id="magnitude-select-b"></select>
      </label>
      <label id="runup-wrap-b">Runup (ft)
        <select id="runup-select-b"></select>
      </label>
    </div>
    <div class="panel" id="panel-b"></div>
  </div>
</div>
</main>

<script>
const ENTRIES = window.MANIFEST.entries;

const KIND_BY_FORM_METRIC = {
  "plot,primary": "plot",
  "plot,equivalent_elevation": "equivalent_elevation_plot",
  "plot,elevation_delta": "elevation_delta_plot",
  "plot,threshold_ari_elevation": "threshold_ari_elevation_plot",
  "grid,primary": "grid",
  "grid,equivalent_elevation": "equivalent_elevation_grid",
  "grid,elevation_delta": "elevation_delta_grid",
  "grid,threshold_ari_elevation": "threshold_ari_elevation_grid",
};

function uniqueSorted(values) {
  return Array.from(new Set(values)).sort((a, b) => (a > b ? 1 : a < b ? -1 : 0));
}

function populateSelect(select, values, formatFn) {
  select.innerHTML = "";
  values.forEach((v) => {
    const opt = document.createElement("option");
    opt.value = String(v);
    opt.textContent = formatFn ? formatFn(v) : String(v);
    select.appendChild(opt);
  });
}

function currentFilters(suffix) {
  return {
    analysis_type: document.getElementById("analysis-select").value,
    save_point_id: document.getElementById(`save-point-select${suffix}`).value,
    elevation_ft: document.getElementById(`magnitude-select${suffix}`).value,
    runup_ft: document.getElementById(`runup-select${suffix}`).value,
  };
}

// Entries allowed by the top-of-page initial filter -- gated on which criterion radio
// is active (rule 1: Elevation OR Baseline ARI, never both at once). swl rows only
// (avg rows have no baseline ARI/grid concept, and are always shown regardless of
// this filter; see CONTEXT.md's "Save point"/"ARI" entries). A blank min or max field
// means "no constraint on that side". If max < min for the active criterion, the
// filter is treated as unconstrained (see initialFilterErrorMessage) rather than
// excluding every row.
function activeInitialFilterCriterion() {
  const checked = document.querySelector('input[name="initial-filter-criterion"]:checked');
  return checked ? checked.value : "elevation";
}

function initialFilterErrorMessage() {
  const criterion = activeInitialFilterCriterion();
  const minEl = document.getElementById(criterion === "elevation" ? "initial-elev-min" : "initial-ari-min");
  const maxEl = document.getElementById(criterion === "elevation" ? "initial-elev-max" : "initial-ari-max");
  const min = parseFloatOrNull(minEl.value);
  const max = parseFloatOrNull(maxEl.value);
  if (min !== null && max !== null && max < min) {
    return "Max must be greater than or equal to min.";
  }
  return null;
}

function initialFilterAllowedEntries() {
  const criterion = activeInitialFilterCriterion();
  const hasError = initialFilterErrorMessage() !== null;
  const elevMin = parseFloatOrNull(document.getElementById("initial-elev-min").value);
  const elevMax = parseFloatOrNull(document.getElementById("initial-elev-max").value);
  const ariMin = parseFloatOrNull(document.getElementById("initial-ari-min").value);
  const ariMax = parseFloatOrNull(document.getElementById("initial-ari-max").value);
  return ENTRIES.filter((e) => {
    if (e.analysis_type !== "swl") return true; // avg rows always pass through
    if (hasError) return true; // invalid range -- treat as unconstrained until fixed
    if (criterion === "elevation") {
      if (elevMin !== null && e.elevation_ft < elevMin) return false;
      if (elevMax !== null && e.elevation_ft > elevMax) return false;
    } else {
      if (ariMin !== null && (e.baseline_ari === null || e.baseline_ari < ariMin)) return false;
      if (ariMax !== null && (e.baseline_ari === null || e.baseline_ari > ariMax)) return false;
    }
    return true;
  });
}

function parseFloatOrNull(text) {
  if (text === null || text === undefined || text.trim() === "") return null;
  const n = parseFloat(text);
  return Number.isNaN(n) ? null : n;
}

// Updates the "N design scenarios available below" count shown under the initial
// filter -- recomputed on every keystroke/change in the 4 min/max fields, before any
// filter is applied it reflects every entry (see init()). Also shows/hides the inline
// error banner for an invalid (max < min) range on the active criterion (rule 4).
function updateInitialFilterCount() {
  const errorEl = document.getElementById("initial-filter-error");
  const message = initialFilterErrorMessage();
  if (message) {
    errorEl.textContent = message;
    errorEl.classList.add("visible");
  } else {
    errorEl.textContent = "";
    errorEl.classList.remove("visible");
  }
  const allowed = initialFilterAllowedEntries();
  document.getElementById("initial-filter-count").textContent =
    `${allowed.length} design scenario${allowed.length === 1 ? "" : "s"} available below`;
}

// Populates the Elevation min/max <select>s with every unique swl elevation_ft value
// in the manifest (rule 2: same discrete values as the later Elevation picker,
// derived dynamically rather than hardcoded so a future run's range stays correct).
function populateInitialElevationSelects() {
  const values = uniqueSorted(ENTRIES.filter((e) => e.analysis_type === "swl").map((e) => e.elevation_ft));
  populateSelect(document.getElementById("initial-elev-min"), values);
  populateSelect(document.getElementById("initial-elev-max"), values);
  const maxSelect = document.getElementById("initial-elev-max");
  if (values.length > 0) {
    maxSelect.value = String(values[values.length - 1]);
  }
}

// Enables the active criterion's inputs and disables/greys out the inactive one
// (rule 1: Elevation OR Baseline ARI, never both). Switching criterion also clears
// the inactive side's values so a stale min/max doesn't silently apply once
// re-activated later.
function updateInitialFilterCriterionVisibility() {
  const criterion = activeInitialFilterCriterion();
  const elevGroup = document.getElementById("initial-elev-group");
  const ariGroup = document.getElementById("initial-ari-group");
  elevGroup.classList.toggle("disabled", criterion !== "elevation");
  ariGroup.classList.toggle("disabled", criterion !== "baseline_ari");
}

function onInitialFilterCriterionChange() {
  updateInitialFilterCriterionVisibility();
  onInitialFilterChange();
}

// Rule 5: resets the initial-filter section only (criterion back to Elevation, both
// range pairs back to unconstrained/default) -- distinct from the existing empty-state
// "Reset filters" button, which resets the A/B facet pickers instead.
function resetInitialFilter() {
  document.querySelector('input[name="initial-filter-criterion"][value="elevation"]').checked = true;
  populateInitialElevationSelects();
  document.getElementById("initial-elev-min").selectedIndex = 0;
  document.getElementById("initial-ari-min").value = "";
  document.getElementById("initial-ari-max").value = "";
  updateInitialFilterCriterionVisibility();
  onInitialFilterChange();
}

function entriesForAnalysisType(analysisType) {
  return initialFilterAllowedEntries().filter((e) => e.analysis_type === analysisType);
}

// The 3 identifying filters, in dropdown order -- see merge_and_validate for why they
// always disambiguate to exactly one entry. selectId is a template with a `%s` suffix
// slot so the same field list drives both the "A" (suffix "") and "B" (suffix "-b")
// picker sets used in compare mode.
const FACET_FIELDS = [
  { field: "save_point_id", selectIdBase: "save-point-select" },
  { field: "elevation_ft", selectIdBase: "magnitude-select" },
  { field: "runup_ft", selectIdBase: "runup-select" },
];


// When the full held (save point, elevation, runup) triple is jointly inconsistent
// under the current scope, we must decide which value(s) to null out. Preference
// order matters: Save point is the primary/coarsest filter a user picks first, so
// prefer keeping it and sacrificing Runup, then Elevation, before ever giving up
// Save point -- rather than always nulling whichever field happens to come first in
// FACET_FIELDS order (which could wrongly blank a perfectly-still-valid Save point
// just because its stale Elevation+Runup combo no longer co-occurs with it).
// Listed smallest-drop-first, most-preferred first, largest/most-destructive last.
const PRIORITY_NULL_SETS = [
  [],
  ["runup_ft"],
  ["elevation_ft"],
  ["save_point_id"],
  ["elevation_ft", "runup_ft"],
  ["save_point_id", "runup_ft"],
  ["save_point_id", "elevation_ft"],
  ["save_point_id", "elevation_ft", "runup_ft"],
];

function currentFieldValues(suffix, scoped) {
  const initial = {};
  FACET_FIELDS.forEach(({ field, selectIdBase }) => {
    const el = document.getElementById(`${selectIdBase}${suffix}`);
    // A select with no <option>s yet (e.g. before the first population pass, or right
    // after switching analysis type -- see refreshFacetSelects) has no real selection
    // to constrain by -- treat it as "no constraint" (null), not as a literal
    // empty-string value nothing will ever match.
    if (el.options.length === 0) {
      initial[field] = null;
      return;
    }
    // A select WITH options can still hold a stale value that is no longer possible
    // at all under the current scope -- e.g. right after the top initial-filter
    // narrows entries (Baseline ARI/Elevation range change), a previously-selected
    // Elevation may no longer exist in any scoped entry. Using that stale value as a
    // hard constraint would wrongly zero out every other facet's options (e.g. Save
    // point going blank) instead of just letting this facet itself get re-narrowed.
    // Guard by checking the value still appears in *some* scoped entry (ignoring
    // every other facet -- this is solely an existence check, not a full filter).
    const stillPossible = scoped.some((e) => String(e[field]) === el.value);
    initial[field] = stillPossible ? el.value : null;
  });
  // Once ARI-filtering has narrowed the entry pool, Save point, Elevation and Runup
  // are no longer independent: even though each held value individually passed the
  // stillPossible check above, the exact combination may no longer co-occur anywhere
  // in scoped. Try nulling out the smallest/most-preferred subset of the held values
  // (per PRIORITY_NULL_SETS) that makes the remainder jointly satisfiable -- this
  // avoids always sacrificing whichever field happens to be checked first, so a
  // still-valid Save point (or Elevation) is not wrongly blanked just to resolve an
  // Elevation/Runup conflict.
  for (const nullSet of PRIORITY_NULL_SETS) {
    const trial = { ...initial };
    nullSet.forEach((field) => {
      trial[field] = null;
    });
    if (scoped.length > 0 && scoped.some((e) => matchesFilters(e, trial, null))) {
      return trial;
    }
  }
  return { save_point_id: null, elevation_ft: null, runup_ft: null };
}

function matchesFilters(entry, values, excludeField) {
  return FACET_FIELDS.every(({ field }) => {
    if (field === excludeField) return true;
    if (values[field] === null) return true;
    return String(entry[field]) === values[field];
  });
}

// Faceted-search style narrowing: each select's options are recomputed from entries
// matching every *other* currently-selected filter (not its own), so a user can never
// pick a combination with no matching row. Recomputed on every filter change. suffix
// is "" for the "A" picker set or "-b" for the "B" (compare) picker set -- each set
// narrows independently of the other.
function refreshFacetSelects(analysisType, suffix) {
  const scoped = entriesForAnalysisType(analysisType);
  const values = currentFieldValues(suffix, scoped);
  FACET_FIELDS.forEach(({ field, selectIdBase }) => {
    const selectEl = document.getElementById(`${selectIdBase}${suffix}`);
    const previous = selectEl.value;
    const allowed = uniqueSorted(
      scoped.filter((e) => matchesFilters(e, values, field)).map((e) => e[field])
    );
    populateSelect(selectEl, allowed);
    if (allowed.map(String).includes(previous)) {
      selectEl.value = previous;
    }
  });
}

// Clears a picker set's <option>s so a subsequent refreshFacetSelects computes fresh,
// unconstrained options -- used when switching analysis type, since a leftover
// selected value from the other analysis type (e.g. an avg row's save_point_id of
// "None") would otherwise wrongly constrain every other facet to zero matches.
function resetFacetSelects(suffix) {
  FACET_FIELDS.forEach(({ selectIdBase }) => {
    document.getElementById(`${selectIdBase}${suffix}`).innerHTML = "";
  });
}

function findEntry(filters, metric) {
  const pool = initialFilterAllowedEntries();
  if (metric === "threshold_ari_elevation") {
    // Rule 8: threshold-ARI-elevation is shared per save point regardless of
    // elevation/runup (see CONTEXT.md's "Threshold-ARI elevation" entry) -- match by
    // save_point_id alone, since the Elevation/Runup pickers are hidden for this
    // metric and their stale values must not exclude an otherwise-valid save point.
    return pool.find(
      (e) => e.analysis_type === filters.analysis_type && String(e.save_point_id) === filters.save_point_id
    );
  }
  return pool.find(
    (e) =>
      e.analysis_type === filters.analysis_type &&
      String(e.save_point_id) === filters.save_point_id &&
      String(e.elevation_ft) === filters.elevation_ft &&
      String(e.runup_ft) === filters.runup_ft
  );
}

function renderEmptyState(panelEl, message) {
  const wrap = document.createElement("div");
  wrap.className = "empty-state";
  const text = document.createElement("span");
  text.textContent = message;
  wrap.appendChild(text);
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Reset filters";
  button.addEventListener("click", resetAllFilters);
  wrap.appendChild(button);
  panelEl.appendChild(wrap);
}

function renderPanel(panelEl, entry, form, metric) {
  panelEl.innerHTML = "";
  if (!entry) {
    renderEmptyState(panelEl, "No matching row for this filter combination.");
    return;
  }
  const kind = KIND_BY_FORM_METRIC[`${form},${metric}`];
  const file = entry.files[kind];
  if (!file) {
    renderEmptyState(panelEl, "Not available for this row.");
    return;
  }
  if (file.type === "missing") {
    renderEmptyState(panelEl, file.message);
    return;
  }
  if (file.type === "image") {
    const img = document.createElement("img");
    img.src = file.path;
    panelEl.appendChild(img);
  } else {
    const table = document.createElement("table");
    const headRow = document.createElement("tr");
    headRow.appendChild(document.createElement("th"));
    file.data.col_labels.forEach((c) => {
      const th = document.createElement("th");
      th.textContent = c;
      headRow.appendChild(th);
    });
    table.appendChild(headRow);
    file.data.row_labels.forEach((r, i) => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.textContent = r;
      tr.appendChild(th);
      file.data.values[i].forEach((v) => {
        const td = document.createElement("td");
        td.textContent = v === null ? "" : v.toFixed(2);
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    panelEl.appendChild(table);
  }
  const caption = document.createElement("div");
  caption.className = "file-path-caption";
  caption.textContent = file.path;
  panelEl.appendChild(caption);
}

function render() {
  const analysisType = document.getElementById("analysis-select").value;
  const form = document.getElementById("form-select").value;
  const metric = document.getElementById("metric-select").value;
  const effectiveMetric = analysisType === "avg" ? "primary" : metric;

  const filtersA = currentFilters("");
  const entryA = findEntry(filtersA, effectiveMetric);
  renderPanel(document.getElementById("panel-a"), entryA, form, effectiveMetric);

  const compare = document.getElementById("compare-toggle").checked;
  document.getElementById("panel-b-column").style.display = compare ? "" : "none";
  if (compare) {
    const filtersB = currentFilters("-b");
    const entryB = findEntry(filtersB, effectiveMetric);
    renderPanel(document.getElementById("panel-b"), entryB, form, effectiveMetric);
  }
}

function updateVisibilityForAnalysisType() {
  const analysisType = document.getElementById("analysis-select").value;
  const isAvg = analysisType === "avg";
  ["save-point-wrap", "save-point-wrap-b"].forEach((id) => {
    document.getElementById(id).style.display = isAvg ? "none" : "";
  });
  document.querySelectorAll(".swl-only").forEach((opt) => {
    opt.disabled = isAvg;
  });
  const metricSelect = document.getElementById("metric-select");
  if (isAvg) {
    metricSelect.value = "primary";
  }
  // Clear both picker sets first: a value selected under the *other* analysis type
  // (e.g. an avg row's save_point_id of "None") must not leak in as a stale
  // constraint when recomputing options for the newly-selected analysis type.
  resetFacetSelects("");
  resetFacetSelects("-b");
  refreshFacetSelects(analysisType, "");
  refreshFacetSelects(analysisType, "-b");
  updateVisibilityForMetric();
}

// Rule 8: the Elevation/Runup pickers are irrelevant for the "Threshold ARI
// Elevation" metric (that output is shared per save point, not per elevation/runup
// combo -- see CONTEXT.md's "Threshold-ARI elevation" entry), so hide them while that
// metric is selected and restore them for any other metric. Also gated on
// analysis_type "avg" (which already always hides these -- see
// updateVisibilityForAnalysisType), so both conditions are checked together here.
function updateVisibilityForMetric() {
  const analysisType = document.getElementById("analysis-select").value;
  const metric = document.getElementById("metric-select").value;
  const isAvg = analysisType === "avg";
  const hideForMetric = isAvg || metric === "threshold_ari_elevation";
  ["runup-wrap", "runup-wrap-b"].forEach((id) => {
    document.getElementById(id).style.display = hideForMetric ? "none" : "";
  });
  const hideElevation = isAvg ? false : metric === "threshold_ari_elevation";
  ["magnitude-wrap", "magnitude-wrap-b"].forEach((id) => {
    document.getElementById(id).style.display = hideElevation ? "none" : "";
  });
}

function onAnalysisTypeChange() {
  updateVisibilityForAnalysisType();
  render();
}

function onMetricChange() {
  updateVisibilityForMetric();
  render();
}

function onFacetSelectChange(suffix) {
  const analysisType = document.getElementById("analysis-select").value;
  refreshFacetSelects(analysisType, suffix);
  render();
}

function onCompareToggleChange() {
  const analysisType = document.getElementById("analysis-select").value;
  const compare = document.getElementById("compare-toggle").checked;
  if (compare) {
    // The "B" picker set is only populated lazily (on first reveal), so it starts
    // from the current "B" selections (usually none yet) rather than stale state.
    refreshFacetSelects(analysisType, "-b");
  }
  render();
}

// Clears both picker sets and re-derives fresh, unconstrained options -- used by the
// empty-state "Reset filters" button so a user who narrows into a dead-end (no
// matching row) can recover in one click instead of manually undoing each dropdown.
function resetAllFilters() {
  const analysisType = document.getElementById("analysis-select").value;
  resetFacetSelects("");
  resetFacetSelects("-b");
  refreshFacetSelects(analysisType, "");
  refreshFacetSelects(analysisType, "-b");
  render();
}

// Handles any edit to the top-of-page initial filter's 4 min/max fields: updates the
// live row count, then re-derives both picker sets' options against the newly
// narrowed/widened entry set (same faceted-narrowing as onFacetSelectChange) and
// re-renders, since a currently-selected combination may no longer be allowed.
function onInitialFilterChange() {
  updateInitialFilterCount();
  const analysisType = document.getElementById("analysis-select").value;
  refreshFacetSelects(analysisType, "");
  refreshFacetSelects(analysisType, "-b");
  render();
}

function init() {
  const analysisTypes = uniqueSorted(ENTRIES.map((e) => e.analysis_type));
  populateSelect(document.getElementById("analysis-select"), analysisTypes);
  // Hide the Water Level Type picker entirely when the manifest only has one
  // analysis_type (e.g. no --avg-workbooks passed to build_dashboard) -- a
  // single-option dropdown with nothing to switch between is just clutter. It
  // reappears automatically on a rebuild that includes both swl and avg workbooks.
  document.getElementById("analysis-type-wrap").style.display =
    analysisTypes.length > 1 ? "" : "none";
  populateInitialElevationSelects();
  updateInitialFilterCriterionVisibility();
  updateVisibilityForAnalysisType();
  document.getElementById("analysis-select").addEventListener("change", onAnalysisTypeChange);
  FACET_FIELDS.forEach(({ selectIdBase }) => {
    document.getElementById(`${selectIdBase}`).addEventListener("change", () => onFacetSelectChange(""));
    document.getElementById(`${selectIdBase}-b`).addEventListener("change", () => onFacetSelectChange("-b"));
  });
  document.getElementById("form-select").addEventListener("change", render);
  document.getElementById("metric-select").addEventListener("change", onMetricChange);
  document.getElementById("compare-toggle").addEventListener("change", onCompareToggleChange);
  ["initial-elev-min", "initial-elev-max"].forEach((id) =>
    document.getElementById(id).addEventListener("change", onInitialFilterChange)
  );
  ["initial-ari-min", "initial-ari-max"].forEach((id) =>
    document.getElementById(id).addEventListener("input", onInitialFilterChange)
  );
  document.querySelectorAll('input[name="initial-filter-criterion"]').forEach((radio) =>
    radio.addEventListener("change", onInitialFilterCriterionChange)
  );
  document.getElementById("initial-filter-reset").addEventListener("click", resetInitialFilter);
  updateInitialFilterCount();
  render();
}

init();
</script>
</body>
</html>
"""


def render_dashboard_html(path: Path) -> None:
    """Write the static, self-contained dashboard.html.

    References manifest.js via a <script src="manifest.js"> tag (must sit alongside
    dashboard.html -- see write_manifest_js). All filter/render logic is plain vanilla
    JS driven by window.MANIFEST; no build step, no server, no install required.
    """
    path.write_text(_DASHBOARD_HTML_TEMPLATE, encoding="utf-8")


def build_dashboard(
    swl_workbook_paths: list[Path], avg_workbook_paths: list[Path], output_dir: Path
) -> None:
    """Build the full dashboard (manifest.js + dashboard.html) into output_dir.

    swl_workbook_paths / avg_workbook_paths are explicit lists of already-run
    batch_run_swl.py / batch_run_avg.py workbooks to include (see CONTEXT.md: folder
    inclusion is a deliberate per-invocation choice, not auto-scanned, since one-off
    elevation-override variants come and go).
    """
    entries_lists = [build_entries(wp) for wp in swl_workbook_paths]
    entries_lists += [build_avg_entries(wp) for wp in avg_workbook_paths]
    entries = merge_and_validate(entries_lists)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(entries, dashboard_dir=output_dir)
    write_manifest_js(manifest, output_dir / "manifest.js")
    render_dashboard_html(output_dir / "dashboard.html")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a self-contained results dashboard (dashboard.html + manifest.js) "
            "from one or more already-run batch_run_swl.py / batch_run_avg.py "
            "resources+config workbooks."
        )
    )
    parser.add_argument(
        "--swl-workbooks", nargs="+", type=Path, default=[],
        help="Path(s) to already-run batch_run_swl.py resources+config .xlsx workbook(s).",
    )
    parser.add_argument(
        "--avg-workbooks", nargs="+", type=Path, default=[],
        help="Path(s) to already-run batch_run_avg.py resources+config .xlsx workbook(s).",
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="Directory to write dashboard.html + manifest.js into.",
    )
    args = parser.parse_args(argv)
    if not args.swl_workbooks and not args.avg_workbooks:
        parser.error("at least one of --swl-workbooks/--avg-workbooks is required.")
    build_dashboard(args.swl_workbooks, args.avg_workbooks, args.output_dir)
    print(f"Dashboard written to {args.output_dir / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
