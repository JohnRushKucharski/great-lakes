# assess-avg-resources

## Purpose

Assess many resources at once against the avg (average monthly) lake levels. Each row of
a resources worksheet is one `hydropattern` component (for example "Duluth Harbor, lake
level above 183 m"). The workflow generates one `.toml` config per row, runs
`hydropattern` on it, and writes the result grids and plots.

It reads the avg data product only. It does **not** include storm surge or wave set-up
(that is swl, see [`assess-swl-resources`](../assess-swl-resources/README.md)) and never
changes the data it reads. Terms (**resource**, **resources sheet**, **config sheet**,
**subdirectory structure**) are defined in [`GLOSSARY.md`](../../GLOSSARY.md).

## Status

Implemented, with the v1 worksheets. `inputs/templates/new_template_batch_run_avg.xlsx` is
a draft of the next worksheet version; `assess.py` does not read it yet.

## Inputs

- `data/avg/<lake>_avg.csv` (avg data product; meters, IGLD85).
- A resources+config worksheet. `inputs/templates/template_avg.xlsx` is the blank v1
  template (one example row). Copy it, never edit it in place:

  ```powershell
  Copy-Item analyses\assess-avg-resources\inputs\templates\template_avg.xlsx my_run.xlsx
  ```

Worksheets are hand-edited inputs; scripts never overwrite them. Case-study worksheets
(for example Long Tail Point) live with their case study.

### `resources` sheet: one row per hydropattern component

| Column | Required? | Notes |
| --- | --- | --- |
| `resource_name` | yes | Grouping label (e.g. a harbor/location name). Only affects output subfolder naming. |
| `component_name` | yes | Name of this hydropattern component/characteristic set. |
| `lake` | yes | One of `superior`, `michiganhuron`, `stclair`, `erie`, `ontario`. |
| `success_pattern` | no (default `false`) | |
| `verbose` | no (default `true`) | |
| `timing_first_month` / `timing_last_month` | no | Both required together to set a `timing` characteristic. |
| `magnitude_operator` / `magnitude_value` / `magnitude_ma_periods` | no | Operator and value required together to set a `magnitude` characteristic. `ma_periods` defaults to `1`. |
| `rate_of_change_operator` / `rate_of_change_value` / `rate_of_change_ma_periods` / `rate_of_change_look_back` / `rate_of_change_min_val` | no | Operator and value required together to set a `rate_of_change` characteristic. |
| `duration_operator` / `duration_value` | no | Both required together to set a `duration` characteristic. |
| `threshold` | no | Per-component plot color threshold (overrides the config sheet's plot settings for this row only). |

A row needs at least one characteristic (timing, magnitude, rate_of_change, duration) to
be meaningful, though this is not enforced.

### `config` sheet: options shared by every row (`option` / `value` columns)

| Option | Default | Notes |
| --- | --- | --- |
| `output_directory` | *(required)* | Base directory for generated `.toml` files and hydropattern outputs. |
| `subdirectory_structure` | `flat` | `flat` (all rows share `output_directory`), `resource` (one subfolder per `resource_name`), or `row` (nested `resource_name/component_name`). |
| `first_day_of_water_year` | `1` | Day-of-year (1-365) the water year starts on. |
| `metric_mode` | `portion` | `portion`, `percentage`, or `annual_probability` (portion of water years with at least 1 occurrence; not a return period, see [methods](methods/annual_probability_method.md)). An old `return_period` is read as `annual_probability` with a warning. |
| `excel` | `true` | Also write an Excel copy of each run's output. |
| `overwrite` | `false` | If `false`, a row whose expected output files already exist is skipped and reported as a failed row. |
| `plot_enabled` | `true` | Generate a climate-canvas response-surface plot per component. |
| `plot_interpolate` | `true` | Bilinearly interpolate the plotted response surface. |
| `plot_color_map` | `RdBu` | The default is reversed per component when `success_pattern` is false, so red always means less success (applied here since hydropattern 0.3 no longer does). Any other map is used as given. |
| `plot_color_map_ticks` | *(unset)* | Optional comma-separated explicit colorbar ticks, e.g. `-1.0, 0.0, 1.0`. |

Leave a cell blank to use its default.

## Run

No argument is required. From the repository root:

```powershell
uv run python analyses/assess-avg-resources/scripts/assess.py
uv run python analyses/assess-avg-resources/scripts/assess.py --resources my_run.xlsx
uv run python analyses/assess-avg-resources/scripts/build_template.py
```

| Option | Default |
| --- | --- |
| `--resources` | `inputs/templates/template_avg.xlsx` |
| `--data-dir` | `data/avg` |
| `--output-dir` | the workbook's `output_directory`; with the shipped template (no `--resources`), `outputs/` of this workflow |
| `--root` | the repository root (used by tests to run on a fixture tree) |

`build_template.py` rewrites the blank template; run it after the recognized columns or
options in `great_lakes.batch.avg` change. It overwrites
`inputs/templates/template_avg.xlsx` (not a hand-edited file).

One line is printed as each row starts and finishes, then a summary. The exit code is `0`
if every row succeeded and `1` if any failed. A failing row (bad data, a duplicate output
target, existing output with `overwrite=false`, a `hydropattern` error) does not stop the
batch; the others still run. Set `overwrite=true` to replace a row's existing output when
re-running.

## Outputs

`outputs/` (gitignored, regenerable) or the worksheet's `output_directory`. Each row writes
files named `<resource_name>_<component_name>...`, for example:

```
duluth_harbor_high_water.toml            <- generated hydropattern config
duluth_harbor_high_water_summary.xlsx    <- always written
duluth_harbor_high_water_output.xlsx     <- only if excel=true
duluth_harbor_high_water_grid.csv        <- only if plot_enabled=true
duluth_harbor_high_water_plot.png        <- only if plot_enabled=true
duluth_harbor_high_water_annual_probability.csv  <- only if metric_mode=annual_probability
```

Where they land depends on `subdirectory_structure`. Every run also writes a `README.txt`
in the output directory (run timestamp, inputs, succeeded/failed summary, naming scheme,
files written, and pre-existing files the run did not create), even if every row fails.

## Methods

Row parsing, `.toml` generation and the per-row run are in `great_lakes.batch.avg`; the
shared run loop and run record are in `great_lakes.batch.runner` and
`great_lakes.batch.run_readme`. `portion` and `percentage` are `hydropattern`'s own;
`annual_probability` is computed in `great_lakes.batch.annual_probability` from
hydropattern's summary workbook (see `methods/annual_probability_method.md`).

## Assumptions & limitations

- avg only: no storm surge or wave set-up; levels are monthly averages.
- Values in `magnitude_value` are in the units of the avg csvs (meters, IGLD85).
- Each row is independent: sharing a `resource_name` between rows only affects output
  folder naming.
