# assess-swl-resources

## Purpose

Assess many resources at once against swl (storm water level) frequency curves. Each row
of a resources worksheet is one save point and one magnitude threshold. The workflow finds
the ARI at the threshold, converts it to an annual exceedance probability, computes a
metric for each scenario, and writes a grid CSV and a response-surface plot.

swl includes storm surge and wave set-up. It excludes near-shore processes (run-up,
overtopping). USACE sources often call it "still water level" (also "SWL"); this repo says
*storm* water level to avoid confusion with avg (see [`GLOSSARY.md`](../../GLOSSARY.md)).

swl has no timeseries, so this workflow is standalone: it builds no `hydropattern` `.toml`
and a component has only a `magnitude` characteristic. For avg, see
[`assess-avg-resources`](../assess-avg-resources/README.md).

## Status

Implemented, with the v1 worksheets. `inputs/templates/new_template_batch_run_swl.xlsx` is
a draft of the next worksheet version; `assess.py` does not read it yet. A
`swl_method_quality` note is planned.

## Inputs

- `data/swl/complete/<lake>_swl.xlsx` (swl data product; 17 scenarios, meters, IGLD85).
  One sheet per scenario; rows are save points, columns are ARI (years).
- A resources+config worksheet. `inputs/templates/template_swl.xlsx` is the blank v1
  template. Copy it, never edit it in place:

  ```powershell
  Copy-Item analyses\assess-swl-resources\inputs\templates\template_swl.xlsx my_swl_run.xlsx
  ```

Worksheets are hand-edited inputs; scripts never overwrite them. Column details of the
template are in [`methods/template_swl_reference.md`](methods/template_swl_reference.md).

### `resources` sheet: one row per save point / magnitude threshold

| Column | Required? | Notes |
| --- | --- | --- |
| `resource_name` | yes | Grouping label. Used in output filenames. |
| `lake` | yes | One of `superior`, `michigan`, `huron`, `ontario` (no `stclair`/`erie`/combined lake for swl). |
| `magnitude_operator` | yes | `>`, `>=`, `<`, `<=` only; `=`/`!=` are rejected. |
| `magnitude_value` | yes | Water-level threshold, in the units of the swl workbook. |
| `component_name` | no (default `swl`) | Used in output filenames with `resource_name`. |
| `save_point_id` | no | Selects the save point by exact `ID`. Wins over `lat`/`lon`. |
| `lat` / `lon` | no (together, if `save_point_id` omitted) | Nearest save point by Euclidean distance in degrees. |
| `success_pattern` | no (default `false`) | Whether the magnitude condition being true counts as "success". |
| `threshold` | no | Plot reference line in **metric-mode units** (portion, percentage or ARI), not a water level. |
| `equivalent_elevation` | no | Blank skips it; `"baseline_magnitude"` or a number runs the [equivalent elevation](methods/equivalent_elevation_method.md) grid/plot. |

### `config` sheet: options shared by every row (`option` / `value` columns)

| Option | Default | Notes |
| --- | --- | --- |
| `output_directory` | *(required)* | Base directory for grid CSVs and plots. |
| `subdirectory_structure` | `flat` | `flat`, `resource`, or `row`, as in assess-avg-resources. |
| `metric_mode` | `return_period` | `portion`, `percentage`, or `return_period`. |
| `overwrite` | `false` | If `false`, a row whose output already exists is skipped and reported as failed. |
| `plot_interpolate` | `true` | Bilinearly interpolate the plotted surface. |
| `plot_color_map` | `RdBu` | Auto-reversed per resource from `metric_mode`/`success_pattern`. |
| `plot_color_map_ticks` | *(unset)* | Optional comma-separated colorbar ticks. |
| `fillin` | `false` | Estimate missing grid cells by Delaunay triangulation before plotting. |

Leave a cell blank to use its default.

## Run

No argument is required. From the repository root:

```powershell
uv run python analyses/assess-swl-resources/scripts/assess.py
uv run python analyses/assess-swl-resources/scripts/assess.py --resources my_swl_run.xlsx
uv run python analyses/assess-swl-resources/scripts/build_template.py
```

| Option | Default |
| --- | --- |
| `--resources` | `inputs/templates/template_swl.xlsx` |
| `--data-dir` | `data/swl/complete` |
| `--output-dir` | the workbook's `output_directory`; with the shipped template (no `--resources`), `outputs/` of this workflow |
| `--root` | the repository root (used by tests) |

`build_template.py` rewrites the blank template; run it after the recognized columns or
options in `great_lakes.batch.swl` change.

One line is printed as each row starts and finishes, then a summary. Exit code `0` if every
row succeeded, `1` if any failed. A failing row (bad data, a duplicate output target, a
threshold clamped to the curve range, existing output with `overwrite=false`) does not
stop the batch.

## Outputs

`outputs/` (gitignored, regenerable) or the worksheet's `output_directory`. Each row writes
two files named `<resource_name>_<component_name>...`, with `_<save_point_id>` appended
when the row selects by `save_point_id`:

```
duluth_harbor_swl_1_grid.csv      <- one metric per scenario
duluth_harbor_swl_1_plot.png      <- response-surface plot
```

Rows with `equivalent_elevation` also write `..._equivalent_elevation_grid.csv` and
`..._equivalent_elevation_plot.png`. No `.toml` or summary workbook is written. Every run
also writes a `README.txt` (see GLOSSARY "Run readme") with inputs, timestamp, summary,
naming scheme, files written and pre-existing files it did not create.

## Methods

- [`methods/aep_method.md`](methods/aep_method.md): ARI interpolation and the Poisson
  ARI-to-AEP conversion.
- [`methods/equivalent_elevation_method.md`](methods/equivalent_elevation_method.md).
- [`methods/template_swl_reference.md`](methods/template_swl_reference.md).

Code: `great_lakes.batch.swl`, with the shared run loop in `great_lakes.batch.runner`.

## Assumptions & limitations

- swl only: no timeseries, so no duration, rate_of_change or timing characteristics.
- A threshold outside the modeled ARI range (`0.1` to `1000`) is clamped with a warning.
- Poisson assumption: exceedances are independent with a constant rate.
- Never combine with avg: swl and avg are different quantities.
