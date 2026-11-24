# great_lakes

Tooling (dependent on `hydropattern` via a pinned git dependency) for batch-generating
and running hydropattern `.toml` configs against Great Lakes lake-level timeseries, one
`.toml`/run per row of a spreadsheet (`workflows/evaluation/avg/batch-resources`) — plus a
second, standalone workflow (`workflows/evaluation/swl/batch-resources`) that evaluates storm
water level
(SWL) frequency curves instead.

## Language

**Storm water level (SWL)**:
Water level including storm surge and wave set-up, as a frequency (ARI) curve per save
point. Excludes near-shore processes (run-up, overtopping). Replaces this repo's earlier
name "total water level (twl)"; USACE sources often call it "still water level" (same
"SWL" abbreviation), which is easily mistaken for average (monthly) water levels.
_Avoid_: Total water level, twl (old name), still water level (except when mapping
source/USACE usage to this term), average water level (that's **avg** data).

**Long Tail Point (LTP)**:
The Green Bay, WI site of two case studies in this repo: a beach-nourishment overtopping
analysis and a Dead Horse Bay habitat (restoration) analysis. Write "Long Tail Point" in
prose (first use), "LTP" thereafter.
_Avoid_: longtail, longtailpoint (in docs, folders, and identifiers).

**Workflow**:
A folder with `README.md`, `inputs/`, `scripts/`, `methods/`, and `outputs/` that turns
its inputs into outputs when its scripts are run. The unit a user runs.
_Avoid_: Pipeline, tool, batch tool.

**Data product**:
A cleaned or completed dataset, tracked in `data/`, that other workflows consume (avg,
swl clean, swl complete).
_Avoid_: Output (alone; ambiguous with any workflow output).

**Evaluation**:
Workflows that apply resource rules (hydropattern components, ARI thresholds) to data.
They live under `workflows/evaluation/`.

**Analysis**:
Workflows that produce or describe the data products themselves (cleaning, completing,
gates, statistics). They live under `workflows/analysis/` (`data-products/` and
`data-analysis/`). The word is still fine in prose for any examination of data.

**Single-resource** / **batch-resources**:
Evaluating one resource (a stub, not built) vs many rows of a resources workbook
(implemented; formerly `assess-avg-resources` and `assess-swl-resources`).

**Case study**:
A project-specific set of workflows and deliverables (Long Tail Point overtopping, Long
Tail Point habitat). Case studies never share memos, drafts, or scripts.

**Deliverable**:
A final document or package given to a person (a memo, the dashboard zip). The hand-edited
`.docx` is the master memo text; scripts never overwrite it.
_Avoid_: Report (alone), output.

**Gate**:
A pass/fail check in a workflow's `scripts/`. A failing gate stops the workflow.
_Avoid_: Validation (alone; fit-quality checks without a verdict are method notes).

**Method note**:
A document in `methods/` explaining how a result was derived or how well it fits. Not a
pass/fail check.

## Language

**Resource**:
A named grouping label for one or more rows in the resources sheet, used only to name
output subfolders when the config sheet's subdirectory structure is `resource` or `row`.
Sharing a resource name across rows has no effect on `.toml` generation — each row still
produces its own independent `.toml` and hydropattern run.
_Avoid_: Project (too generic — a resource is the Great-Lakes-specific unit of grouping).

**Resources sheet**:
The `template_avg.xlsx` sheet (in `workflows/evaluation/avg/batch-resources/inputs/templates/`) where each row fully specifies one hydropattern
component (name, lake, characteristics, plot threshold) to generate into its own `.toml`
file and run independently.

**Config sheet**:
The `template_avg.xlsx` sheet (same folder) holding options shared across every row of the
resources sheet (output directory, subdirectory structure, overwrite, first day of water
year, metric mode, excel/plot output toggles).

**Subdirectory structure**:
The config sheet option controlling where each row's generated `.toml` and hydropattern
output land, relative to the config's base output directory:
- `"flat"`: directly in the base output directory.
- `"resource"`: one subfolder per resource name.
- `"row"`: one subfolder per resource name, nested with one subfolder per component name.

**Annual probability** (`metric_mode="annual_probability"`, avg only):
The portion of complete water years in which a component's pattern occurs at least once,
per scenario, in [0, 1]. An **occurrence** is a run of consecutive success timesteps
(hydropattern calls these events). It is **not a return period**: monthly lake levels are
persistent, so occurrences are not independent. Replaces the avg `return_period` mode; the
swl `return_period` is a true ARI-based return period and is unchanged. See
`workflows/evaluation/avg/batch-resources/methods/annual_probability_method.md`.

**Save point**:
A single row in a swl lake workbook sheet (`great_lakes.batch.swl`) — a fixed lat/lon location with an
`ID`, whose water-level-vs-ARI curve is looked up by a resources-sheet row via
`save_point_id` (exact match, wins if given) or nearest `lat`/`lon` (Euclidean distance,
fallback).
_Avoid_: Location, site (too generic — save point is the swl-data-specific unit each
sheet row represents).

**ARI (Average Return Interval)**:
The swl workbook's column headers (in years) — the inverse of exceedance probability for
a given water level at a save point. `great_lakes.batch.swl` linearly interpolates in ARI-space
against a save point's (water level, ARI) pairs to find the ARI at a resource row's
magnitude threshold. Out-of-range thresholds are clamped to the nearest end ARI (`0.1` or
`1000`) with a warning, never extrapolated.

**Equivalent elevation**:
An optional (resources-sheet `equivalent_elevation` column, blank by default) second
scenario-grid metric alongside a resource row's primary exceedance-probability/ARI
metric. The column is blank (skip), `"baseline_magnitude"` (case-insensitive; use the
row's `magnitude_value`), or a number (override `magnitude_value` for this analysis
only — the primary metric always uses `magnitude_value`). Computed by first finding
the baseline (`_0_0`) scenario's ARI at the resolved baseline-ARI lookup value, then
interpolating the water level at that same ARI under every other scenario's own curve
— the reverse direction of the ARI lookup used for the primary metric. Answers "what
water level is equally likely, under this scenario, as the lookup value is under the
baseline scenario?" All swl-workbook levels, `magnitude_value`, and `equivalent_elevation`
are in meters, IGLD85 datum (the analysis itself never converts units), but the written
output is converted to feet, NAVD88 datum (see `units.m_igld85_to_ft_NAVD88`, a flat
+0.44ft offset plus the case-study 3.281 ft/m scale — see
`case-studies/long-tail-point/overtopping/inputs/longtail_waterlevel.xlsx` Sheet2's "NAVD88 to IGLD85" table) since a water
level, unlike the primary metric's portion/percentage/return_period units, has physical
elevation units to convert. Written to its own grid csv + plot png
(`..._equivalent_elevation_grid.csv` / `_equivalent_elevation_plot.png`), with plot
z-axis label `"Equivalent Elevation (ft, NAVD88)"` and plot threshold equal to the
resolved baseline-ARI lookup value itself (converted to ft NAVD88) rather than a
metric-mode-units value.
_Avoid_: Equivalent ARI, equivalent magnitude (the output is a water level, not an ARI
or the metric-mode value the primary grid produces).

**Elevation delta**:
A third grid csv + plot png (`..._elevation_delta_grid.csv` / `_elevation_delta_plot.png`),
written alongside equivalent elevation whenever a resource row's `equivalent_elevation`
column is not blank (same gating). Each scenario cell is that scenario's equivalent
elevation (in ft, NAVD88) minus the resolved baseline-ARI lookup value itself (also
converted to ft, NAVD88) — i.e. how much higher or lower this scenario's equivalent
elevation is than the comparison/lookup elevation, not a difference between two
scenarios. Plot z-axis label `"Elevation Delta (ft, NAVD88)"`; plot threshold (colorbar
center) is always `0` (no delta), regardless of the resource row's `threshold` or the
equivalent elevation plot's own threshold.
_Avoid_: Elevation change, elevation difference (delta is the established short form
used elsewhere in this codebase's math write-ups; keep consistent).

**Threshold-ARI elevation**:
A fourth grid csv + plot png (`savepoint<ID>_ari15_elevation_grid.csv` /
`_ari15_elevation_plot.png`, named for this batch's `threshold=15`; the file name isn't
generic since only one per-run target ARI exists at a time), written once per unique
**save point** (not per resource row) whenever a row's `equivalent_elevation` column is
not blank. Reuses `resource.threshold` (already a per-row ARI in years for
`metric_mode="return_period"` runs) as the target ARI: the baseline scenario's water
level at that ARI, and every other scenario's equivalent water level at that same ARI
(same reverse-interpolation as **equivalent elevation**, parameterized by a target ARI
directly instead of a magnitude threshold first converted to an ARI). Colorbar is
centered on the baseline scenario's own value (white at baseline), unlike **elevation
delta**'s fixed `0` center. Depends only on save point + `resource.threshold`, not
magnitude/runup, so all rows sharing a save point produce (and reuse) the same one
grid/plot rather than one per row.
_Avoid_: ARI-15 elevation, fixed-ARI elevation (the ARI is `resource.threshold`, not a
hardcoded 15, even though 15 is this batch's value).

**Runup allowance**:
The `longtailpoint`-specific meaning of `component_name` in a swl resources sheet: an
assumed wave-runup amount, in feet, added on top of storm water level to obtain the
water level being evaluated. Values used so far: `base` (0 ft), `run2` (2 ft),
`run25` (2.5 ft), `run3` (3 ft). The dashboard's "Runup (ft)" picker filters/displays
the numeric ft value (`RUNUP_FT_BY_COMPONENT`'s value), not the raw `component_name`
code, since the code itself is an internal label with no meaning to a dashboard user.
_Avoid_: Runup scenario (collides with **scenario**, which always means precip/temp
climate scenario in this codebase — runup allowance varies independently of that grid).

**Equivalent-elevation basis**:
A per-row *display/filter* label describing what elevation a row's **equivalent
elevation**/**elevation delta** outputs were computed against — derived from the row's
resolved `equivalent_elevation` value, not the raw resources-sheet cell itself. One of:
blank (`equivalent_elevation` is `None`; no equivalent-elevation/elevation-delta outputs
exist for this row), `"baseline_magnitude"` (row's own `magnitude_value` was used), or an
explicit override elevation (always displayed/compared in ft, NAVD88, even though the
resources-sheet cell holds it in meters, IGLD85). Two rows can share every other
attribute (save point, magnitude, runup allowance) yet differ only by basis — e.g. one
workbook run with every row's basis `"baseline_magnitude"`, another with every row's
basis overridden to the same fixed elevation — since `equivalent_elevation` is resolved
independently per row, not fixed per workbook.
_Avoid_: Equivalent elevation value, baseline elevation (conflates the resolved
per-row *label/basis* with the **equivalent elevation** output it produces).

**Known scenario**:
One of the 5 (of 17 total) precip/temp scenarios a `<lake>_swl.xlsx` workbook already has
a sheet for, per save point (`baseline-_0_0`, `nearterm-_5_1.5`, `moderate_low-_10_5`,
`extreme_low-_0_7`, `extreme_high-_20_5`) — identical set across all 4 lake swl workbooks.
_Avoid_: Source scenario, observed scenario.

**Target scenario**:
One of the 12 remaining precip/temp scenarios a `<lake>_swl.xlsx` workbook has no sheet
for, whose water-level-vs-ARI curve is being estimated per save point. Splits into
**in-hull** (7 scenarios, within the 5 known scenarios' convex hull — estimated via
Delaunay-linear interpolation, sheet name `filled-_<precip>_<temp>`) and **out-of-hull**
(5 scenarios, outside it — Delaunay-linear can't extrapolate there; estimated instead via
**row-shift extrapolation**, sheet name `extrapolated-_<precip>_<temp>`; see
`docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md`).
_Avoid_: Missing scenario, estimated scenario.

**Warming row (dT row)**:
The set of scenarios (known, filled, or target) that share the same temp_delta, varying
only by precip_delta — e.g. the dT=7 row is `_0_7, _5_7, _10_7, _15_7, _20_7`. Row-shift
extrapolation always shifts within a single warming row; it never crosses rows.

**Anchor scenario**:
For an out-of-hull target scenario, the known-or-already-filled scenario on the *same
warming row* nearest to it by precip_delta distance. Its full water-level-vs-ARI sheet
is the starting point that row-shift extrapolation shifts by a lake-average delta to
estimate the target. Requires the in-hull interpolation stage to run first, since some
anchors (e.g. `_10_3` anchoring `_15_3`) are themselves Delaunay-filled scenarios, not
known ones.
_Avoid_: Base scenario, reference scenario (reference scenario collides with the
`reference_timeseries` vocabulary used elsewhere in hydropattern core).

**Run readme**:
The `README.txt` an assess run (a batch-resources workflow, avg or swl) writes at the
root of the config's `output_directory` after every invocation of `run_batch`, whether
or not any row succeeded. Documents: the resources/config workbook and data directory
used as inputs, the run's timestamp, a per-row succeeded/failed summary (with failure
messages), the output filename-naming scheme in effect, the list of files this run
wrote (from each succeeded row's output paths), and any pre-existing files found under
`output_directory` that don't match a name this run recognizes (flagged as not created
by this run, distinct from files skipped because `overwrite=False`, which are already
covered by the per-row failure message).
_Avoid_: Naming readme, manifest (manifest collides with `build_dashboard.py`'s
`manifest.js`, which is a different, dashboard-specific artifact).

**Average lake level (AVG(l,s))**:
The mean of the full synthetic scenario record (all ~12,360 monthly rows spanning
1970-2999) in `data/avg/<avg-lake>_avg.csv` for lake `l`'s scenario `s` column — a
single scalar per lake+scenario, independent of save point or ARI. `michigan` and
`huron` (separate `<lake>_swl.xlsx` workbooks) both read the same `michiganhuron_avg.csv`
column, since Michigan-Huron is one hydraulically-connected lake with one water level.
_Avoid_: Mean lake level (AVG is the established short form used in row-shift
extrapolation's math; keep both docs and code consistent).

**Floor**:
The bed elevation (ft, IGLD85) at which a planted zone or woody debris structure sits in
the Dead Horse Bay habitat analysis. Depth is water level minus floor.
_Avoid_: Base, bottom, elevation (alone; ambiguous with water-level elevation).

**Reliability class**:
How often a floor supports a habitat across the years of a scenario: reliable (>= 75% of
years), marginal (50-75%), unreliable (< 50%).
_Avoid_: Success rate, suitability class.

**Robust set**:
The six scenarios used to judge robustness: 1.5 C/0, 1.5 C/5, 3 C/0, 3 C/5, 3 C/10,
3 C/15 (temperature/precipitation). 5 C and 7 C are stress-test context only.
_Avoid_: Core scenarios, main scenarios.

**Robustness tier**:
The widest scenario group in which a floor is reliable in every scenario: brittle
(baseline only) < minimal (both 1.5 C) < robust (all 1.5 C and 3 C) < very robust
(also some 5 C/7 C). Name the tier whenever "robust" is used as an adjective.
_Avoid_: Lowest (old name for minimal), unqualified "robust".

**Dry / wet scenario**:
Within a warming level (+X C), "dry" is the scenario with +0% precipitation and "wet" is
the one with the largest precipitation increase (e.g. 3 C dry = 3C/0, 3 C wet = 3C/15).
Scenario codes read warming (C) / precipitation change (%). Prose uses dry/wet; tables and
figures use the codes.
_Avoid_: Using dry/wet without the warming level.

## Example dialogue

> **Dev**: Two rows in the resources sheet share the name "Duluth Harbor" but have
> different component names. Do they get merged into one `.toml`?
> **Domain expert**: No — every row is independent. "Duluth Harbor" here is just a
> **resource** label; it only affects output folder naming when the **subdirectory
> structure** is `resource` or `row`. Each row still gets its own `.toml` and its own
> hydropattern run.
