# template_swl.xlsx reference

Workbook for `batch_run_swl.py`. Two sheets: `resources` (one row = one grid+plot job) and `config` (key/value options).

## resources sheet

| Column | Required | Default | Type | Constraints |
|---|---|---|---|---|
| `resource_name` | yes | — | str | any string |
| `component_name` | no | `"swl"` | str | any string |
| `lake` | yes | — | str | one of `huron`, `michigan`, `ontario`, `superior` |
| `save_point_id` | conditional | — | any | must give this **or** `lat`+`lon` (both). `save_point_id` wins if both given |
| `lat` | conditional | — | float | required together with `lon` if no `save_point_id` |
| `lon` | conditional | — | float | required together with `lat` if no `save_point_id` |
| `magnitude_operator` | yes | — | str | one of `>`, `>=`, `<`, `<=` (`=`/`!=` not supported) |
| `magnitude_value` | yes | — | float | water-level threshold, same units as swl data |
| `success_pattern` | no | `False` | bool | `True` = low-water pattern (metric = p_exceed); `False` = high-water (metric = 1-p_exceed) |
| `threshold` | no | blank (skip) | float | climate-canvas plot reference line, in **metric_mode** units (portion 0-1 / percentage 0-100 / return_period years) — NOT a water level |
| `equivalent_elevation` | no | blank (skip analysis) | blank / `"baseline_magnitude"` / float | blank = skip; `"baseline_magnitude"` (case-insensitive) = use row's own `magnitude_value`; number = override baseline lookup value for this analysis only |

Unrecognized columns or missing required columns raise a validation error.

## config sheet

Key/value pairs (`option`, `value` columns). Blank/omitted falls back to default. `output_directory` has no default — required.

| Option | Default | Type | Constraints |
|---|---|---|---|
| `output_directory` | — (required) | str | any valid path |
| `subdirectory_structure` | `flat` | str | one of `flat`, `resource`, `row` |
| `metric_mode` | `return_period` | str | one of `portion`, `percentage`, `return_period` |
| `filename_style` | `qualified_name` | str | one of `qualified_name`, `elevation_runup_savepoint`, `savepoint_elevation_runup` |
| `overwrite` | `False` | bool | — |
| `plot_interpolate` | `True` | bool | — |
| `plot_color_map` | `RdBu` | str | any matplotlib colormap name |
| `plot_color_map_ticks` | blank (auto) | comma-separated floats | e.g. `-1.0, 0.0, 1.0` |
| `fillin` | `False` | bool | Delaunay-fill missing grid cells before plotting |
| `show_values` | `False` | bool | label each grid cell with its value |
| `value_decimals` | `2` | int | decimals shown when `show_values=True` |

Unrecognized options, or duplicate option keys, raise a validation error.

> Note: `filename_style`, `show_values`, `value_decimals` are valid `BatchConfig`
> options in `batch_run_swl.py` but not yet pre-listed (with comments) in
> `build_swl_template.py`'s `CONFIG_ROWS` / generated `config` sheet. Add them there
> if you want them documented in the workbook itself.
