"""Build a self-contained results dashboard for batch_run_twl.py outputs.

Reads one or more batch_run_twl.py resources+config workbooks (already run, with
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
from great_lakes import batch_run_twl as twl
from great_lakes import common_twl

# Resolved equivalent_elevation keyword, mirrored from batch_run_twl.py's
# _BASELINE_MAGNITUDE_KEYWORD (kept as a local copy rather than importing the private
# name, same rationale as batch_run_twl.py's own _VALID_OPERATORS copy).
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
_GRID_KINDS = frozenset({"grid", "equivalent_elevation_grid", "elevation_delta_grid"})
# Primary output kinds (always attempted, whether or not equivalent_elevation is set).
# A missing primary file is treated as a soft failure (e.g. a plot that failed to
# render for a degenerate/flat grid) -- the dashboard shows a message instead of
# aborting the whole build. Missing equivalent_elevation/elevation_delta files, by
# contrast, are still a fail-loud data-integrity signal (see resolve_files).
_PRIMARY_KINDS = frozenset({"grid", "plot"})
# Sentinel marking a primary file that was expected but not found on disk.
MISSING = "__missing__"


def compute_magnitude_ft(resource: "twl.ResourceSpec") -> float:
    """Convert resource.magnitude_value (meters, IGLD85) to feet, NAVD88.

    Used for dashboard filtering/display, since the raw meters-IGLD85 value (and the
    filename numbers derived from it) aren't a human-friendly/authoritative NAVD88
    elevation on their own -- see CONTEXT.md's "Equivalent elevation" definition.
    """
    return common_twl.m_igld85_to_ft_NAVD88(resource.magnitude_value)


def compute_equivalent_elevation_basis(row: dict[str, Any], resource: "twl.ResourceSpec") -> str | None:
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
    override_ft = common_twl.m_igld85_to_ft_NAVD88(resource.equivalent_elevation)
    return f"{override_ft:.2f} ft override"


@dataclass(frozen=True)
class ManifestEntry:
    """One resources-sheet row's dashboard-relevant identity + where its outputs live.

    save_point_id, magnitude_ft, component_name (runup allowance), and
    equivalent_elevation_basis together are the dashboard's 4 identifying filters --
    see merge_and_validate, which enforces they always resolve to exactly one entry.
    """

    workbook_path: Path
    analysis_type: str  # "twl" or "avg" -- see build_entries / build_avg_entries
    resource_name: str
    component_name: str  # runup allowance label, e.g. "base"/"run2"/"run25"/"run3"
    save_point_id: Any
    magnitude_ft: float
    equivalent_elevation_basis: str | None
    qualified_name: str
    output_dir: Path
    # On-disk file-name stem (no suffix), per the workbook's config.filename_style --
    # equals qualified_name for "qualified_name" style (and always for avg entries,
    # which have no filename_style concept) or common_twl.output_file_stem's ft-based
    # stem for "elevation_runup_savepoint" style. resolve_files uses this (not
    # qualified_name) to find each entry's actual output files.
    file_stem: str
    # The actual crest elevation being evaluated: magnitude_ft + this component's
    # runup allowance (common_twl.RUNUP_FT_BY_COMPONENT), or just magnitude_ft for avg
    # entries (no runup allowance concept there). Used by the dashboard's "Elevation
    # (NAVD88)" picker instead of the raw magnitude_ft, since the runup allowance
    # itself is already a separate picker ("Runup (ft)").
    elevation_ft: float


def build_entries(workbook_path: Path) -> list[ManifestEntry]:
    """Read one workbook's config+resources sheets into a list of ManifestEntry.

    Does not touch the output files themselves (see resolve_files for that) -- this
    only resolves each row's identity and where its output folder *should* be, per the
    workbook's own config sheet.
    """
    config = twl.read_config_sheet(workbook_path)
    rows = twl.read_resources_sheet(workbook_path)
    entries = []
    for row in rows:
        resource = twl.parse_resource_row(row)
        output_dir = twl.resolve_output_folder(resource, config)
        magnitude_ft = compute_magnitude_ft(resource)
        runup_ft = common_twl.RUNUP_FT_BY_COMPONENT.get(resource.component_name, 0.0)
        entries.append(
            ManifestEntry(
                workbook_path=workbook_path,
                analysis_type="twl",
                resource_name=resource.resource_name,
                component_name=resource.component_name,
                save_point_id=resource.save_point_id,
                magnitude_ft=magnitude_ft,
                equivalent_elevation_basis=compute_equivalent_elevation_basis(row, resource),
                qualified_name=resource.qualified_name,
                output_dir=output_dir,
                file_stem=twl.resolve_output_stem(resource, config),
                elevation_ft=magnitude_ft + runup_ft,
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
        magnitude_ft = common_twl.m_igld85_to_ft_NAVD88(magnitude_value)
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
    """Resolve one entry's 6 possible output file paths, verifying they exist.

    The 4 equivalent_elevation/elevation_delta kinds resolve to None (not expected to
    exist) when entry.equivalent_elevation_basis is None. When they ARE expected
    (basis is set) but missing on disk, that's a fail-loud data-integrity signal --
    raises FileNotFoundError rather than silently omitting it. The 2 primary kinds
    (grid/plot) are always attempted; if missing (e.g. a run whose plot failed to
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
    return files


def merge_and_validate(entries_lists: list[list[ManifestEntry]]) -> list[ManifestEntry]:
    """Flatten entries from every included workbook, and validate the dashboard's 4
    identifying filters (save_point_id, magnitude_ft, component_name,
    equivalent_elevation_basis) always resolve to exactly one entry.

    Raises ValueError (listing every offending group) if any combination is shared by
    more than one entry -- the dashboard's filters must always disambiguate to a
    single row, per CONTEXT.md.
    """
    all_entries = [entry for entries in entries_lists for entry in entries]
    groups: dict[tuple[str, Any, float, str, str | None], list[ManifestEntry]] = {}
    for entry in all_entries:
        key = (
            entry.analysis_type,
            entry.save_point_id,
            round(entry.magnitude_ft, 2),
            entry.component_name,
            entry.equivalent_elevation_basis,
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
            "magnitude_ft, component_name, equivalent_elevation_basis); the "
            "dashboard's filters must always resolve to exactly one row:\n" + "\n".join(lines)
        )
    return all_entries


def read_grid_csv(path: Path) -> dict[str, Any]:
    """Parse a batch_run_twl.py `_grid.csv` (`temp_delta\\precip_delta` header row, one
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
  body { font-family: sans-serif; margin: 1.5rem; }
  .filters { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem; }
  .filters label { display: flex; flex-direction: column; font-size: 0.85rem; }
  .panels { display: flex; gap: 1.5rem; align-items: flex-start; }
  .panel-column { flex: 1; min-width: 0; }
  .panel { flex: 1; min-width: 0; }
  .panel img { max-width: 100%; }
  table { border-collapse: collapse; font-size: 0.8rem; }
  td, th { border: 1px solid #ccc; padding: 2px 6px; text-align: right; }
  #compare-toggle-wrap { margin-bottom: 1rem; }
  .file-path-caption { font-size: 0.75rem; color: #666; margin-top: 0.35rem; word-break: break-all; }
</style>
</head>
<body>
<h1>Long Tail Point Dashboard</h1>

<div class="filters">
  <label>Water Level Type
    <select id="analysis-select"></select>
  </label>
  <label>Analysis
    <select id="metric-select">
      <option value="primary">Return Interval</option>
      <option value="equivalent_elevation" class="twl-only">Equivalent Elevation</option>
      <option value="elevation_delta" class="twl-only">Elevation Delta</option>
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

<div class="panels">
  <div class="panel-column">
    <div class="filters">
      <label id="save-point-wrap">Save point
        <select id="save-point-select"></select>
      </label>
      <label>Elevation (NAVD88)
        <select id="magnitude-select"></select>
      </label>
      <label id="runup-wrap">Runup (ft)
        <select id="runup-select"></select>
      </label>
      <label id="basis-wrap">Equivalent-elevation basis
        <select id="basis-select"></select>
      </label>
    </div>
    <div class="panel" id="panel-a"></div>
  </div>
  <div class="panel-column" id="panel-b-column" style="display:none">
    <div class="filters">
      <label id="save-point-wrap-b">Save point
        <select id="save-point-select-b"></select>
      </label>
      <label>Elevation (NAVD88)
        <select id="magnitude-select-b"></select>
      </label>
      <label id="runup-wrap-b">Runup (ft)
        <select id="runup-select-b"></select>
      </label>
      <label id="basis-wrap-b">Equivalent-elevation basis
        <select id="basis-select-b"></select>
      </label>
    </div>
    <div class="panel" id="panel-b"></div>
  </div>
</div>

<script>
const ENTRIES = window.MANIFEST.entries;

const KIND_BY_FORM_METRIC = {
  "plot,primary": "plot",
  "plot,equivalent_elevation": "equivalent_elevation_plot",
  "plot,elevation_delta": "elevation_delta_plot",
  "grid,primary": "grid",
  "grid,equivalent_elevation": "equivalent_elevation_grid",
  "grid,elevation_delta": "elevation_delta_grid",
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
    component_name: document.getElementById(`runup-select${suffix}`).value,
    equivalent_elevation_basis: document.getElementById(`basis-select${suffix}`).value,
  };
}

function entriesForAnalysisType(analysisType) {
  return ENTRIES.filter((e) => e.analysis_type === analysisType);
}

// The 4 identifying filters, in dropdown order -- see merge_and_validate for why they
// always disambiguate to exactly one entry. selectId is a template with a `%s` suffix
// slot so the same field list drives both the "A" (suffix "") and "B" (suffix "-b")
// picker sets used in compare mode.
const FACET_FIELDS = [
  { field: "save_point_id", selectIdBase: "save-point-select" },
  { field: "elevation_ft", selectIdBase: "magnitude-select" },
  { field: "component_name", selectIdBase: "runup-select" },
  { field: "equivalent_elevation_basis", selectIdBase: "basis-select" },
];

function currentFieldValues(suffix) {
  const values = {};
  FACET_FIELDS.forEach(({ field, selectIdBase }) => {
    const el = document.getElementById(`${selectIdBase}${suffix}`);
    // A select with no <option>s yet (e.g. before the first population pass, or right
    // after switching analysis type -- see refreshFacetSelects) has no real selection
    // to constrain by -- treat it as "no constraint" (null), not as a literal
    // empty-string value nothing will ever match.
    values[field] = el.options.length > 0 ? el.value : null;
  });
  return values;
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
  const values = currentFieldValues(suffix);
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

function findEntry(filters) {
  return ENTRIES.find(
    (e) =>
      e.analysis_type === filters.analysis_type &&
      String(e.save_point_id) === filters.save_point_id &&
      String(e.elevation_ft) === filters.elevation_ft &&
      e.component_name === filters.component_name &&
      String(e.equivalent_elevation_basis) === filters.equivalent_elevation_basis
  );
}

function renderPanel(panelEl, entry, form, metric) {
  panelEl.innerHTML = "";
  if (!entry) {
    panelEl.textContent = "No matching row.";
    return;
  }
  const kind = KIND_BY_FORM_METRIC[`${form},${metric}`];
  const file = entry.files[kind];
  if (!file) {
    panelEl.appendChild(document.createTextNode("Not available for this row."));
    return;
  }
  if (file.type === "missing") {
    panelEl.appendChild(document.createTextNode(file.message));
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
  const entryA = findEntry(filtersA);
  renderPanel(document.getElementById("panel-a"), entryA, form, effectiveMetric);

  const compare = document.getElementById("compare-toggle").checked;
  document.getElementById("panel-b-column").style.display = compare ? "" : "none";
  if (compare) {
    const filtersB = currentFilters("-b");
    const entryB = findEntry(filtersB);
    renderPanel(document.getElementById("panel-b"), entryB, form, effectiveMetric);
  }
}

function updateVisibilityForAnalysisType() {
  const analysisType = document.getElementById("analysis-select").value;
  const isAvg = analysisType === "avg";
  ["save-point-wrap", "runup-wrap", "basis-wrap", "save-point-wrap-b", "runup-wrap-b", "basis-wrap-b"].forEach((id) => {
    document.getElementById(id).style.display = isAvg ? "none" : "";
  });
  document.querySelectorAll(".twl-only").forEach((opt) => {
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
}

function onAnalysisTypeChange() {
  updateVisibilityForAnalysisType();
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

function init() {
  populateSelect(document.getElementById("analysis-select"), uniqueSorted(ENTRIES.map((e) => e.analysis_type)));
  updateVisibilityForAnalysisType();
  document.getElementById("analysis-select").addEventListener("change", onAnalysisTypeChange);
  FACET_FIELDS.forEach(({ selectIdBase }) => {
    document.getElementById(`${selectIdBase}`).addEventListener("change", () => onFacetSelectChange(""));
    document.getElementById(`${selectIdBase}-b`).addEventListener("change", () => onFacetSelectChange("-b"));
  });
  ["form-select", "metric-select"].forEach((id) =>
    document.getElementById(id).addEventListener("change", render)
  );
  document.getElementById("compare-toggle").addEventListener("change", onCompareToggleChange);
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
    twl_workbook_paths: list[Path], avg_workbook_paths: list[Path], output_dir: Path
) -> None:
    """Build the full dashboard (manifest.js + dashboard.html) into output_dir.

    twl_workbook_paths / avg_workbook_paths are explicit lists of already-run
    batch_run_twl.py / batch_run_avg.py workbooks to include (see CONTEXT.md: folder
    inclusion is a deliberate per-invocation choice, not auto-scanned, since one-off
    elevation-override variants come and go).
    """
    entries_lists = [build_entries(wp) for wp in twl_workbook_paths]
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
            "from one or more already-run batch_run_twl.py / batch_run_avg.py "
            "resources+config workbooks."
        )
    )
    parser.add_argument(
        "--twl-workbooks", nargs="+", type=Path, default=[],
        help="Path(s) to already-run batch_run_twl.py resources+config .xlsx workbook(s).",
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
    if not args.twl_workbooks and not args.avg_workbooks:
        parser.error("at least one of --twl-workbooks/--avg-workbooks is required.")
    build_dashboard(args.twl_workbooks, args.avg_workbooks, args.output_dir)
    print(f"Dashboard written to {args.output_dir / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
