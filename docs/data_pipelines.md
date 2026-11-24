# Great Lakes data pipelines: reproducibility guide

This is the end-to-end map for reproducing any Great Lakes output from raw data. If you
are trying to answer "what do I run, with what inputs, in what order, to get X", start
here. For full per-option detail on any one workflow, see its README (linked from the
root [`README.md`](../README.md)); this doc's job is the path and how the stages connect.

## Pipeline diagram

```text
+------------------------------+
| data/raw/*.xlsx, *.xlsm      |
| (committed, read-only)       |
+------------------------------+
                |
                | STEP 1: workflows/analysis/data-products/avg/scripts/clean.py
                |         workflows/analysis/data-products/swl/scripts/clean.py
                v
+-------------------------------------------+
| data/avg/*_avg.csv                        |
| data/swl/clean/*_swl.xlsx (5 scenarios)   |
| (committed)                               |
+-------------------------------------------+
                  |
                  | STEP 2: workflows/analysis/data-products/swl/scripts/complete.py
                  |         (Delaunay fill, then row-shift extrapolation)
                  v
+---------------------------------------------------------------------------------+
| data/swl/complete/*_swl.xlsx (17 scenarios, committed)                          |
| workflows/analysis/data-products/swl/outputs/filled/ (12 scenarios, gitignored) |
+---------------------------------------------------------------------------------+
                         |
                         | STEP 3: fill in a copy of
                         |         workflows/evaluation/{avg,swl}/batch-resources/inputs/templates/template_*.xlsx
                         |         by hand -> resources+config .xlsx (one row per component)
                         v
+------------------------+
| resources+config .xlsx |
+------------------------+
             |
             | STEP 4: workflows/evaluation/avg/batch-resources  /  workflows/evaluation/swl/batch-resources
             |         (assess.py)
             v
+------------------------------------------------+
| output_directory/                              |
|   <resource>_<component>.toml     (avg only)   |
|   grid CSVs, plot PNGs                         |
|   summary/output .xlsx            (avg only)   |
|   README.txt                      (run readme) |
+------------------------------------------------+
                         |
                         | STEP 6: build_dashboard.py
                         |         (reads one or more already-run resources+config workbooks
                         |         and their output_directory contents)
                         v
+------------------------------------------------------+
| dashboard.html + manifest.js   (e.g. overtopping/outputs/) |
+------------------------------------------------------+
```

**Figures and gates (side branches off steps 1-2):** `plot_figures.py` in each product
writes the tracked summary figures next to the data (`data/avg/figures/`,
`data/swl/{clean,complete}/figures/`) and bulk figures to
`workflows/analysis/data-products/*/outputs/`.
`workflows/analysis/data-products/swl/scripts/compare_fill_to_climate_canvas.py` and
`check_ari_curves.py`
are **gates**: they fail (exit code 1) if the fill disagrees with climate_canvas by more
than 0.05 ft, or if any swl ARI curve has a missing or decreasing value.
`workflows/analysis/data-products/swl/methods/summarize_precip_temp_effects.py` summarizes
known-scenario
directionality. None feed steps 3/4/6.

Scripts are run by path from the repository root, for example
`uv run python workflows/analysis/data-products/<product>/scripts/<name>.py`; the library under
`src/great_lakes/` is import-only. Each workflow's README has the full detail.

Every arrow above is a script you invoke directly; nothing runs automatically as a side
effect of another stage. Skipping a stage (e.g. re-using already-cleaned `data/avg/`
files) is fine; each stage only needs its documented inputs to exist, regardless of how
they were produced.

## Step-by-step: raw data to outputs

### 0. Install

```powershell
uv sync --group test --group dev
```

### 1. Clean the raw workbooks (only if `data/raw/*` changed)

```powershell
uv run python workflows/analysis/data-products/avg/scripts/clean.py --overwrite
uv run python workflows/analysis/data-products/swl/scripts/clean.py --overwrite
```
Inputs: `data\raw\lake_levels_all_scenarios_9jul2026.xlsx`,
`data\raw\still_water_summary__22may2026.xlsm` (committed).
Outputs: `data\avg\{superior,michiganhuron,stclair,erie,ontario}_avg.csv`,
`data\swl\clean\{superior,michigan,huron,ontario}_swl.xlsx` (committed). The swl clean
step drops save points whose ARI values are all missing in the source (3 in Michigan).

### 2. Complete the swl scenarios

```powershell
uv run python workflows/analysis/data-products/swl/scripts/complete.py --overwrite
```
Inputs: `data\swl\clean\*_swl.xlsx` + `data\avg\*_avg.csv` (step 1's outputs).
Outputs: `data\swl\complete\*_swl.xlsx` (17 scenarios) and
`workflows\analysis\data-products\swl\outputs\filled\*_swl.xlsx` (12 scenarios, gitignored).
See
[`scenario_completion.md`](../workflows/analysis/data-products/swl/methods/scenario_completion.md)
for the
interpolation/extrapolation math.

### 3. Fill in a resources+config workbook

```powershell
Copy-Item workflows\evaluation\avg\batch-resources\inputs\templates\template_avg.xlsx my_run.xlsx   # or workflows\evaluation\swl\batch-resources ... template_swl.xlsx
```
This is the one **manual, human-authored input** in the whole pipeline: one row per
hydropattern component/analysis you want, plus a `config` sheet of shared options
(`output_directory`, `overwrite`, plot settings, etc.). See the "resources sheet" /
"config sheet" tables in
[`workflows/evaluation/avg/batch-resources/README.md`](../workflows/evaluation/avg/batch-resources/README.md) and
[`workflows/evaluation/swl/batch-resources/README.md`](../workflows/evaluation/swl/batch-resources/README.md) for every column.
Regenerate a template with that workflow's `scripts/build_template.py` if the
recognized columns ever change.

### 4. Run the batch analysis

```powershell
uv run python workflows/evaluation/avg/batch-resources/scripts/assess.py --resources my_run.xlsx
uv run python workflows/evaluation/swl/batch-resources/scripts/assess.py --resources my_swl_run.xlsx
```
(The swl batch-resources workflow reads `data\swl\complete` by default; pass `--data-dir data\swl\clean` for known scenarios only.)

Inputs: the workbook from step 3, plus the matching data directory from step 1/2.
Outputs, written to the workbook's `output_directory`: per-row `.toml` + grid CSV +
plot PNG (+ summary/output `.xlsx` for avg), and a `README.txt` **run readme** (see
GLOSSARY.md's "Run readme" entry) documenting exactly what ran, with what inputs, what
succeeded/failed, every file the run wrote, and any pre-existing files in that
directory tree the run doesn't recognize as its own (a stale-output flag). Read the run
readme first when checking whether an output tree reflects a specific run.

### 5. Gates and known-scenario directionality (optional)

```powershell
uv run python workflows/analysis/data-products/swl/scripts/compare_fill_to_climate_canvas.py
uv run python workflows/analysis/data-products/swl/scripts/check_ari_curves.py
uv run python workflows/analysis/data-products/swl/methods/summarize_precip_temp_effects.py
```
Inputs: `data\swl\{clean,complete}` and `workflows\analysis\data-products\swl\outputs\filled`.
Outputs: under `workflows\analysis\data-products\swl\outputs\{gates,methods}\`. Every output
folder gets a `README.txt`
run record.

### 6. Build the results dashboard

```powershell
uv run python case-studies/long-tail-point/overtopping/scripts/build_dashboard.py
```
The library (`great_lakes.build_dashboard.build_dashboard`) is import-only; each case study
has a script that passes its own workbooks. `package_dashboard.py` zips the result.
Inputs: one or more **already-run** (step 4 complete) resources+config workbooks; the
tool reads each workbook's own `output_directory` for the grids/plots it produced.
Outputs: `dashboard.html` + `manifest.js` in `--output-dir`.

## Reproducing a specific output

Given any output file, walk the diagram backwards: a grid CSV/plot PNG's
`output_directory` has a run readme naming the resources+config workbook and data
directory that produced it (step 3/4's inputs); that workbook was filled in from a
template built by step 3's template-builder from whichever `great_lakes.batch` version
was current; that data directory came from step 1/2 acting on the committed
`data/raw/` workbooks. Nothing in this chain depends on machine-specific state:
every stage's output is fully determined by its documented inputs.

## Known limits

- The avg csvs carry no units label; units (meters, IGLD85) are fixed by convention. See
  [`data/README.md`](../data/README.md).
- There is no image-regression test for the plots; figures are checked by eye.

The dated audit of an earlier version of this pipeline was removed in the reorganization;
it is available in git history before the phase 6 commit.
