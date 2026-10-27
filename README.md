# great_lakes

Batch-generating and running `hydropattern` `.toml` configs against Great Lakes
lake-level timeseries — one `.toml` file and one hydropattern run per row of a
spreadsheet — plus standalone tools for storm water level (SWL) frequency-curve
analysis, SWL scenario fill-in/extrapolation, known-scenario directionality analysis,
and a results dashboard.

See [`CONTEXT.md`](./CONTEXT.md) for the domain vocabulary (**resource**, **resources
sheet**, **config sheet**, **subdirectory structure**) used throughout this document.

## Directory layout

```
├── README.md                  <- this file
├── CONTEXT.md                 <- domain glossary
├── docs/
│   ├── data_pipelines.md
│   └── adr/
│       ├── 0001-row-shift-extrapolation-for-out-of-hull-scenarios.md
│       └── 0002-sidecar-js-manifest-for-longtailpoint-dashboard.md
├── src/great_lakes/
│   ├── batch_run_avg.py             <- batch tool 1: parse -> build .toml -> run hydropattern
│   ├── batch_run_swl.py             <- batch tool 2: parse -> interpolate ARI curve -> plot
│   ├── batch_runner.py              <- shared run_batch loop + RowProcessor strategy + run readme
│   ├── common_swl.py                <- shared helpers: read <lake>_swl.xlsx / <avg-lake>_avg.csv
│   ├── fillin_swl.py                 <- batch tool 3: interpolate + extrapolate missing swl scenarios
│   ├── analyze_known_scenarios.py    <- known-vs-known SWL precip/temp directionality analysis
│   ├── build_dashboard.py            <- builds a self-contained results dashboard
│   ├── clean_lake_levels_all_scenarios.py  <- data/raw/ -> data/clean/ AVG cleaning script
│   ├── clean_swl_summary.py        <- data/raw/ -> data/clean/ SWL cleaning script
│   ├── build_avg_template.py        <- regenerates templates/template_avg.xlsx
│   └── build_swl_template.py        <- regenerates templates/template_swl.xlsx
├── templates/
│   ├── template_avg.xlsx           <- blank resources+config workbook template (batch_run_avg.py)
│   └── template_swl.xlsx           <- blank resources+config workbook template (batch_run_swl.py)
├── data/
│   ├── raw/                    <- source Excel workbooks (committed, not code)
│   ├── clean/                  <- cleaned per-lake data (gitignored, regenerable from raw/)
│   │   ├── superior_avg.csv        <- batch_run_avg.py / fillin_swl.py (timeseries -> AVG)
│   │   ├── michiganhuron_avg.csv
│   │   ├── stclair_avg.csv
│   │   ├── erie_avg.csv
│   │   ├── ontario_avg.csv
│   │   ├── superior_swl.xlsx       <- batch_run_swl.py / fillin_swl.py (ARI frequency curves)
│   │   ├── michigan_swl.xlsx
│   │   ├── huron_swl.xlsx
│   │   └── ontario_swl.xlsx
│   ├── extrapolated/            <- fillin_swl.py output (--extrapolate, default): 17 scenarios
│   │   ├── superior_swl.xlsx
│   │   ├── michigan_swl.xlsx
│   │   ├── huron_swl.xlsx
│   │   └── ontario_swl.xlsx
│   ├── filled/                 <- fillin_swl.py output (--no-extrapolate): 12 scenarios only
│   │   ├── superior_swl.xlsx
│   │   ├── michigan_swl.xlsx
│   │   ├── huron_swl.xlsx
│   │   └── ontario_swl.xlsx
│   └── analysis/                <- analyze_known_scenarios.py output (gitignored, regenerable)
└── longtailpoint/               <- an example project using this tooling (see its own README)
```

`data/clean/`, `data/filled/`, `data/extrapolated/`, and `data/analysis/` are all
gitignored — they're regenerable from `data/raw/` via the scripts documented below, so
they're kept locally as insurance but not committed. `data/raw/`'s source workbooks
*are* committed (they're the ground-truth inputs); the scripts that clean them live in
`src/great_lakes/` alongside the rest of the code (so they're covered by the same
mypy/ruff checks as everything else), not in `data/raw/` itself.

## Installation

```powershell
uv sync --group test --group dev
```

`hydropattern` is a pinned git dependency (see `pyproject.toml`); `pandas`,
`openpyxl`, `scipy` (Delaunay triangulation, via `climate-canvas`), `python-calamine`
(fast `.xlsx` reading), and `xlsxwriter` (workbook writing) are all direct dependencies.

You only need to re-run the cleaning scripts if the raw source workbooks in
`data/raw/` change:

```powershell
uv run python -m great_lakes.clean_lake_levels_all_scenarios
uv run python -m great_lakes.clean_swl_summary
```


# Batch tool 1: batch_run_avg.py

## 1. Fill in the template workbook

Copy `templates/template_avg.xlsx` to a new file (don't edit the template in place) and
fill it in:

```powershell
Copy-Item templates\template_avg.xlsx my_run.xlsx
```

The workbook has two sheets:

### `resources` sheet — one row per hydropattern component

| Column | Required? | Notes |
| --- | --- | --- |
| `resource_name` | yes | Grouping label (e.g. a harbor/location name). Only affects output subfolder naming. |
| `component_name` | yes | Name of this hydropattern component/characteristic set. |
| `lake` | yes | One of `superior`, `michiganhuron`, `stclair`, `erie`, `ontario`. |
| `success_pattern` | no (default `false`) | |
| `verbose` | no (default `true`) | |
| `timing_first_month` / `timing_last_month` | no | Both required together to set a `timing` characteristic. |
| `magnitude_operator` / `magnitude_value` / `magnitude_ma_periods` | no | Operator+value required together to set a `magnitude` characteristic. `ma_periods` defaults to `1`. |
| `rate_of_change_operator` / `rate_of_change_value` / `rate_of_change_ma_periods` / `rate_of_change_look_back` / `rate_of_change_min_val` | no | Operator+value required together to set a `rate_of_change` characteristic. |
| `duration_operator` / `duration_value` | no | Both required together to set a `duration` characteristic. |
| `threshold` | no | Per-component plot color threshold (overrides the config sheet's plot settings for this row only). |

A row needs at least one characteristic (timing/magnitude/rate_of_change/duration) to be
meaningful, though this isn't enforced — an "empty" component will still generate and run.

### `config` sheet — options shared by every row (`option` / `value` columns)

| Option | Default | Notes |
| --- | --- | --- |
| `output_directory` | *(required)* | Base directory for generated `.toml` files and hydropattern outputs. |
| `subdirectory_structure` | `flat` | `flat` (all rows share `output_directory`), `resource` (one subfolder per `resource_name`), or `row` (nested `resource_name/component_name`). |
| `first_day_of_water_year` | `1` | Day-of-year (1-365) the water year starts on. |
| `metric_mode` | `portion` | `portion`, `percentage`, or `return_period`. |
| `excel` | `true` | Also write an Excel copy of each run's output. |
| `overwrite` | `false` | If `false`, a row whose expected output files already exist is skipped and reported as a failed row (see below). |
| `plot_enabled` | `true` | Generate a climate-canvas response-surface plot per component. |
| `plot_interpolate` | `true` | Bilinearly interpolate the plotted response surface. |
| `plot_color_map` | `RdBu` | hydropattern auto-reverses this per component based on `metric_mode`/`success_pattern` — see `docs/user/reference.md` in the main repo. |
| `plot_color_map_ticks` | *(unset)* | Optional comma-separated explicit colorbar ticks, e.g. `-1.0, 0.0, 1.0`. |

Leave a cell blank to use its default.

## 2. Run it

```powershell
uv run python -m great_lakes.batch_run_avg my_run.xlsx data\clean
```

Arguments:
1. Path to your filled-in resources+config workbook.
2. Path to the directory containing the lake `*_avg.csv` files (normally `data/clean`).

As it runs, you'll see one line per row as it starts and finishes, so you can follow
along in real time (a row can take a while — each one runs a full hydropattern analysis,
optionally including a plot):

```
[1/3] duluth_harbor/high_water: running
[1/3] duluth_harbor/high_water: succeeded
[2/3] buffalo_shore/low_water: running
[2/3] buffalo_shore/low_water: succeeded
[3/3] bad_row/?: running
[3/3] bad_row/?: failed
```

At the end, a summary is printed and the process exit code is `0` if every row succeeded,
`1` if any row failed:

```
2 succeeded, 1 failed out of 3 row(s).
  Row 3 ('bad_row', None): 'component_name' is required but missing or blank.
```

A row failing (bad data, a duplicate output target, pre-existing output with
`overwrite=false`, or a hydropattern error) does **not** stop the batch — every other row
still runs, and the failure is reported in the final summary.

## 3. Check the output

Each row's outputs are named `<resource_name>_<component_name>...`, e.g. for
`resource_name=duluth_harbor`, `component_name=high_water`:

```
duluth_harbor_high_water.toml            <- the generated hydropattern config
duluth_harbor_high_water_summary.xlsx    <- always written
duluth_harbor_high_water_output.xlsx     <- only if excel=true
duluth_harbor_high_water_grid.csv        <- only if plot_enabled=true
duluth_harbor_high_water_plot.png        <- only if plot_enabled=true
```

Where these land depends on `subdirectory_structure` (see the config sheet table above).

Every run also writes a `README.txt` in `output_directory` (see CONTEXT.md's "Run
readme" entry) — a reproducibility record covering: inputs used, a timestamp, the
succeeded/failed summary, the naming scheme, every file this run wrote, and any
pre-existing files in that directory tree the run didn't recognize as its own (useful
for spotting stale output left over from a prior run). It's written even if every row
fails or the sheet has zero rows.

## Re-running with new/changed rows

Set `overwrite=true` in the config sheet to let a re-run replace a row's existing output;
otherwise a row whose output files already exist is skipped and reported as failed (with
the specific filenames that were found), so you don't silently clobber a prior run.

## Regenerating the template

If `batch_run_avg.py`'s recognized resources-sheet columns or config-sheet options ever
change, regenerate the shipped template so it stays in sync:

```powershell
uv run python -m great_lakes.build_avg_template
```

## Running the tests

```powershell
uv run pytest tests/test_batch_run_avg.py
```

# Batch tool 2: batch_run_swl.py

`batch_run_swl.py` evaluates static water-level frequency curves (storm water level, or
**SWL**), not timeseries. SWL data include storm surge and wave set-up but exclude
near-shore processes (run-up, overtopping). USACE sources often call this "still water
level" (also "SWL"); that name is easy to confuse with average (monthly) water levels,
which is why this repo says *storm* water level. Each `data/clean/<lake>_swl.xlsx` workbook has one sheet per
**scenario** (5, not 17 — swl only has climate-scenario variants, no water-year timing
dimension), and each sheet is a table of **save points** (rows) against **Average Return
Interval** (ARI, in years — the column headers) with the water level at that save point
for that ARI as the cell value.

Because there is no timeseries, this tool is **standalone**: it does not build or run a
`hydropattern` `.toml` config at all. Instead, for each resource row it looks up the save
point's ARI curve, linearly interpolates in ARI-space to find the ARI associated with the
row's magnitude threshold, converts that ARI to an annual exceedance probability (see
below), computes a metric exactly the way `hydropattern` does internally, and writes a
grid CSV + response-surface plot — nothing else. A swl "component" therefore has only a
`magnitude` characteristic (no `duration`, `rate_of_change`, or `timing` — those all
require a timeseries).

## How the annual exceedance probability is calculated

Each save point's curve gives water level as a function of ARI (Average Return Interval,
in years) at 13 fixed points (`0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000`).
Going from a row's `magnitude_value` threshold to a probability is a two-step process:

1. **Interpolate the ARI at the threshold.** `interpolate_ari` does this in ARI-space —
   `numpy.interp` against the curve's (water level, ARI) points, treating ARI as linear in
   water level between the two bracketing curve points. A threshold outside the curve's
   modeled range is clamped to the nearest end ARI (`0.1` or `1000`) with a `UserWarning`,
   rather than extrapolated.

2. **Convert that ARI to an annual exceedance probability (AEP).** `exceedance_probability`
   uses the Poisson relation:

   ```
   AEP = 1 - exp(-1 / ARI)
   ```

   rather than the naive approximation `AEP = 1 / ARI`.

   **Why not `1 / ARI`?** ARI is the mean number of *years between* exceedance events under
   a Poisson process (a standard assumption in flood/coastal-hazard frequency analysis:
   exceedances are independent, identically distributed events arriving at a constant
   average rate `λ = 1 / ARI` per year). The chance of **at least one** exceedance in a
   given year is `1 - P(no exceedances) = 1 - exp(-λ)` (the Poisson probability of zero
   events). `1 / ARI` is only the first-order Taylor approximation of this
   (`1 - exp(-x) ≈ x` for small `x`), valid when `ARI` is large enough that `λ = 1/ARI` is
   small. It breaks down once `ARI < 1` year (`λ > 1`), where `1 / ARI` exceeds `1.0` and is
   no longer a valid probability — this dataset's ARI columns go as low as `0.1` years, so
   the naive formula is not safe to use here. The Poisson form stays correctly bounded in
   `(0, 1)` for any `ARI > 0`.

   The two formulas converge for large ARI (`1-exp(-x) ≈ x` when `x` is small), so this
   only meaningfully changes results below roughly ARI = 10 years:

   | ARI (yr) | `1/ARI` | `1 - exp(-1/ARI)` |
   | --- | --- | --- |
   | 1000 | 0.0010 | 0.0010 |
   | 100 | 0.0100 | 0.00995 |
   | 10 | 0.100 | 0.0952 |
   | 2 | 0.500 | 0.393 |
   | 1 | 1.000 | 0.632 |
   | 0.1 | 10.00 (invalid) | 0.99995 |

   For `>`/`>=` magnitude operators this AEP *is* the probability the condition holds; for
   `<`/`<=` it's the complement (`1 - AEP`). `compute_metric` then converts that probability
   into the configured `metric_mode` (`portion`, `percentage`, or `return_period`) exactly
   as `hydropattern.formatters.compute_metric_series` does for timeseries-based components.

## 1. Fill in the template workbook

Copy `templates/template_swl.xlsx` to a new file (don't edit the template in place) and
fill it in:

```powershell
Copy-Item templates\template_swl.xlsx my_swl_run.xlsx
```

The workbook has two sheets:

### `resources` sheet — one row per save point / magnitude threshold

| Column | Required? | Notes |
| --- | --- | --- |
| `resource_name` | yes | Grouping label (e.g. a harbor/location name). Used in output filenames. |
| `lake` | yes | One of `superior`, `michigan`, `huron`, `ontario` (no `stclair`/`erie`/combined lake for swl data). |
| `magnitude_operator` | yes | One of `>`, `>=`, `<`, `<=` only — `=`/`!=` are rejected (no sensible probability against a continuous exceedance curve). |
| `magnitude_value` | yes | The water-level threshold, in the same units as the swl workbook. |
| `component_name` | no (default `swl`) | Used in output filenames alongside `resource_name`. |
| `save_point_id` | no | Selects the save point by exact `ID` match. Wins over `lat`/`lon` if both given. |
| `lat` / `lon` | no (required together if `save_point_id` omitted) | Selects the nearest save point by simple Euclidean distance in degrees. |
| `success_pattern` | no (default `false`) | Same meaning as in `hydropattern`: whether the magnitude condition being **true** counts as "success". |
| `threshold` | no | Climate-canvas plot reference line — in **metric-mode units** (a portion 0–1, a percentage 0–100, or an ARI in years), **not** a water level. |
| `equivalent_elevation` | no | Per-row toggle for the "equivalent elevation" second grid/plot (see below). Blank (default) skips it entirely. `"baseline_magnitude"` (case-insensitive) runs it using `magnitude_value` as the baseline-ARI lookup value. A number overrides `magnitude_value` for that lookup only — the primary grid/plot is unaffected either way. |

### `config` sheet — options shared by every row (`option` / `value` columns)

| Option | Default | Notes |
| --- | --- | --- |
| `output_directory` | *(required)* | Base directory for the generated grid CSVs and plots. |
| `subdirectory_structure` | `flat` | `flat`, `resource`, or `row` — same meaning as `batch_run_avg.py`. |
| `metric_mode` | `return_period` | `portion`, `percentage`, or `return_period`. |
| `overwrite` | `false` | If `false`, a row whose output files already exist is skipped and reported as a failed row. |
| `plot_interpolate` | `true` | Bilinearly interpolate the plotted response surface. |
| `plot_color_map` | `RdBu` | Auto-reversed per resource based on `metric_mode`/`success_pattern`, same as `batch_run_avg.py`. |
| `plot_color_map_ticks` | *(unset)* | Optional comma-separated explicit colorbar ticks. |
| `fillin` | `false` | If `true`, estimate missing (NaN) grid cells in the response surface via Delaunay triangulation before plotting (climate-canvas's `--fillin` option). Applies to every plot png the row produces. |

Leave a cell blank to use its default.

## 2. Run it

```powershell
uv run python -m great_lakes.batch_run_swl my_swl_run.xlsx data\clean
```

Arguments:
1. Path to your filled-in resources+config workbook.
2. Path to the directory containing the lake `*_swl.xlsx` files (normally `data/clean`).

As it runs, you'll see one line per row as it starts and finishes, and a final summary,
same as `batch_run_avg.py`. A row failing (bad data, an out-of-range threshold that had to
be clamped, a duplicate output target, or pre-existing output with `overwrite=false`) does
**not** stop the batch.

## 3. Check the output

Each row produces exactly two files, named `<resource_name>_<component_name>...` (with
`_<save_point_id>` appended when the row selects its save point by `save_point_id` --
this disambiguates rows that reuse the same `resource_name`+`component_name` label
across multiple save points):

```
duluth_harbor_swl_1_grid.csv      <- one exceedance-probability/ARI metric per scenario
duluth_harbor_swl_1_plot.png      <- climate-canvas response-surface plot
```

No `.toml`, no summary/output Excel workbook, and no raw per-scenario CSVs are written —
this tool's output is deliberately minimal since there's no hydropattern run to summarize.

Every run also writes a `README.txt` in `output_directory`, same as `batch_run_avg.py`
(see CONTEXT.md's "Run readme" entry) — inputs, timestamp, succeeded/failed summary,
the naming scheme for the row's `filename_style`, files this run wrote, and any
pre-existing files it didn't recognize as its own.

### Equivalent elevation (`equivalent_elevation` resources-sheet column)

If a row's `equivalent_elevation` cell is non-blank (`"baseline_magnitude"` or a number),
that row also produces:

```
duluth_harbor_swl_1_equivalent_elevation_grid.csv   <- one water level per scenario
duluth_harbor_swl_1_equivalent_elevation_plot.png   <- climate-canvas response-surface plot
```

This answers: "the row's baseline-ARI lookup value corresponds to some ARI under the
baseline (`_0_0`) scenario — what water level is equally likely (same ARI) under every
*other* scenario?" The baseline-ARI lookup value is `magnitude_value` itself when the
cell is `"baseline_magnitude"` (case-insensitive), or the cell's own number when it's a
numeric override — the override replaces `magnitude_value` for this analysis only; the
primary grid/plot always evaluates `magnitude_value` regardless of `equivalent_elevation`.
Concretely: the baseline scenario's ARI at that lookup value is found first (the same
`interpolate_ari` lookup the primary grid uses), then that ARI is looked up against every
scenario's own water-level-vs-ARI curve (the reverse interpolation, `interpolate_level`)
to get that scenario's equivalent elevation. The baseline scenario's own cell in this grid
is therefore always the lookup value itself (interpolating a curve at the ARI you just
read off of it returns the same point).

The equivalent-elevation plot differs from the primary plot in three ways: its z-axis
label is `"Equivalent Elevation"` (not `metric_mode`'s units), its plot threshold is the
row's baseline-ARI lookup value itself (a water level, not a metric-mode-units value),
and it always
uses `plot_color_map` as configured with no automatic RdBu-direction reversal and no
`plot_color_map_ticks` — the auto-reversal and tick logic are keyed to
`success_pattern`/`metric_mode` semantics, which don't apply to a raw elevation value.

## Regenerating the template

```powershell
uv run python -m great_lakes.build_swl_template
```

## Running the tests

```powershell
uv run pytest tests/test_batch_run_swl.py
```

# Batch tool 3: fillin_swl.py

Each `data/clean/<lake>_swl.xlsx` workbook only has **5 of 17** possible climate
scenarios (the **known scenarios**). `fillin_swl.py` estimates the other 12 (**target
scenarios**), per save point and per ARI column, and writes a new
`data/filled/<lake>_swl.xlsx` workbook with all 17 scenario sheets. Nothing else reads
`data/filled/` yet — `batch_run_swl.py` still points at `data/clean/` — so this is a
standalone enrichment step for now.

Every one of the 17 scenarios is a point on a fixed (`precip_delta`, `temp_delta`) grid.
Plotting the 5 known scenarios' coordinates, the 12 targets split into two groups that
need two different methods:

- **7 in-hull targets** sit inside the convex hull of the 5 known points — a proper
  interpolation (Delaunay-linear) applies.
- **5 out-of-hull targets** sit outside that hull — no interpolation method can honestly
  produce them; extrapolation is required, and extrapolation always trades away some
  confidence in exchange for coverage.

## Stage 1 — Delaunay-linear interpolation (7 in-hull scenarios)

**Theory.** The 5 known (precip_delta, temp_delta) points are triangulated once (scipy's
`Delaunay`). Each in-hull target point falls inside exactly one triangle. Its
**barycentric weights** relative to that triangle's 3 vertices are 3 non-negative numbers
that sum to 1.0 and reconstruct the point's coordinates as a weighted sum of the vertices'
coordinates. Because the same 3 points and weights also work directly on the *known SWL
values* (not just the coordinates), the target scenario's SWL at any save point/ARI cell
is just that same weighted sum of the 3 known scenarios' values at that cell. This is
mathematically equivalent to fitting one flat plane through the 3 known z-values above
that triangle and reading the target point's height off that plane.

**Math.** For target point `T` inside triangle `(A, B, C)` with barycentric weights
`(wA, wB, wC)` (`wA + wB + wC = 1`, all `>= 0`):

```
SWL(l, T, p, r) = wA * SWL(l, A, p, r) + wB * SWL(l, B, p, r) + wC * SWL(l, C, p, r)
```

**Worked example** (a simple hand-computable triangle, not real lake data — see
`SIMPLE_TRIANGLE_*` fixtures in `tests/test_fillin_swl.py`): vertices `A=(0,0)->100`,
`B=(10,0)->110`, `C=(0,10)->130` describe the plane `z = 100 + x + 3y`. Target point
`(2, 2)` gets barycentric weights `(wA, wB, wC) = (0.6, 0.2, 0.2)`:

```
z(2,2) = 0.6*100 + 0.2*110 + 0.2*130 = 108.0
```

...which matches the plane formula directly (`100 + 2 + 3*2 = 108`).

**Assumptions/limitations.** Delaunay-linear only assumes the SWL response surface is
*locally* flat within each individual triangle — it makes no claim about linearity
anywhere else on the grid, and different triangles can (and do) have different slopes.
Its one hard limitation is exactly the reason this tool needs a Stage 2 at all: it
**cannot extrapolate** beyond the convex hull of the known points, by construction.

## Stage 2 — Row-shift extrapolation (5 out-of-hull scenarios)

**Theory.** See
[`docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md`](docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md)
for the full rationale. In short: a save point's SWL is treated as `AVG(l, s)` (the mean
lake level under scenario `s`, from `data/clean/<avg-lake>_avg.csv`) plus a "waves" term
that captures storm-driven water level above/below the mean. The assumption is that the
waves term stays constant across scenarios on the same **warming row** (same
`temp_delta`) — i.e. a given amount of warming doesn't change storminess, only the mean
lake level does. Under that assumption, an out-of-hull target scenario's SWL equals a
resolved **anchor scenario**'s SWL (nearest known-or-already-filled scenario on the same
warming row, by `|precip_delta|` distance) plus the difference in average lake level
between the two.

**Math.** For target `s` with anchor `a` (`a` and `s` share `temp_delta`):

```
~SWL(l, s, p, r) = SWL(l, a, p, r) + [AVG(l, s) - AVG(l, a)]
```

Because `AVG(l, s) - AVG(l, a)` doesn't depend on save point `p` or return interval `r`,
this collapses to one additive scalar shift applied uniformly to every cell of the
anchor's sheet — no per-cell computation is needed at runtime.

**Worked example** (see `test_extrapolate_scenarios_shifts_anchor_values_by_avg_delta` in
`tests/test_fillin_swl.py`): anchor `_0_7` has SWL values `100.0`/`200.0` at two save
points for one ARI column. `AVG(l, "_0_7") = 180.0` and `AVG(l, "_10_7") = 185.0`, a
`+5.0` delta:

```
~SWL(l, "_10_7", p, r) = 100.0 + (185.0 - 180.0) = 105.0
~SWL(l, "_10_7", p2, r) = 200.0 + (185.0 - 180.0) = 205.0
```

**Anchor selection.** `select_anchor_scenario()` looks for the nearest *resolved*
scenario (known, or already Delaunay-filled) on the same warming row. This matters
because the dT=3 row's out-of-hull point (`_15_3`) anchors to `_10_3`, which is itself a
Stage-1 **filled** scenario, not a known one — so Stage 2 must always run *after* Stage 1.
If no resolved scenario shares the target's warming row, `extrapolate_scenarios()` raises
a `ValueError` rather than silently guessing.

**Assumptions/limitations.** This method is a genuine extrapolation, not an
interpolation — the constant-waves-along-a-row assumption is physically reasonable but
unverified against any additional dT=7/dT=3-row known scenario, since only one point on
each affected row is known. To flag this lower confidence to downstream consumers,
extrapolated sheets get a **distinct** `extrapolated-_<precip_delta>_<temp_delta>` name
prefix, instead of Stage 1's `filled-` prefix.

## CLI usage

```powershell
# extrapolation on (default) -> defaults to data\extrapolated
uv run python -m great_lakes.fillin_swl data\clean

# extrapolation off -> defaults to data\filled
uv run python -m great_lakes.fillin_swl data\clean --no-extrapolate

# explicit output_dir always overrides the default, either way
uv run python -m great_lakes.fillin_swl data\clean data\filled
```

Arguments:
1. `data_dir` — directory containing the known `<lake>_swl.xlsx` and `<avg-lake>_avg.csv`
   files (normally `data/clean`).
2. `output_dir` *(optional)* — directory to write the filled `<lake>_swl.xlsx` workbooks
   to. When omitted, defaults to a sibling of `data_dir`: `data/extrapolated` when
   `--extrapolate` (the default), or `data/filled` with `--no-extrapolate` — since the two
   modes produce workbooks with a different number of sheets, they default to different
   directories rather than silently overwriting each other. Pass `output_dir` explicitly to
   override either default.

Flags:
- `--overwrite` / (default: refuse and raise if an output file already exists).
- `--extrapolate` (default) / `--no-extrapolate` — run Stage 2, producing 17 sheets per
  lake (5 known + 7 filled + 5 extrapolated). `--no-extrapolate` skips Stage 2, producing
  12 sheets (5 known + 7 filled) — the extrapolated scenarios are simply omitted, not
  replaced by anything else.

A progress bar (typer's built-in `typer.progressbar`) ticks once per save-point row,
across all 4 lakes, while the tool runs.

## Running the tests

```powershell
uv run pytest tests/test_fillin_swl.py tests/test_common_swl.py
```
