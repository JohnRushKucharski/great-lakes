# Filled (hydropattern) vs climate_canvas interpolation -- comparison

> **Location note:** this doc moved here (from
> `data/analysis/twl/FILLED_VS_CLIMATE_CANVAS.md`) when the Great Lakes analysis
> scripts were integrated into the `great_lakes` package (see
> `docs/data_pipelines.md`). The script it documents is now
> `great_lakes.analysis.twl.compare_filled_vs_climate_canvas`
> (`src/great_lakes/analysis/twl/compare_filled_vs_climate_canvas.py`), and its
> output CSV now lives at `<filled_data_dir>/img/comparison/filled_vs_climate_canvas_comparison.csv`
> (default `data/filled/img/comparison/...`) instead of the old
> `data/analysis/twl/filled_vs_climate_canvas_comparison.csv`. The centroid save
> point plots referenced below are produced by
> `great_lakes.analysis.twl.plot_known_scenarios` (formerly
> `plot_center_save_points.py`), now writing to `<data_dir>/img/twl/known/`. All
> paths/filenames below have been updated to match; the analysis and its
> conclusion are unchanged.

**Question:** for the 7 in-hull scenarios, is `data/filled/*.xlsx` (hydropattern's
own `fillin_twl.py` fill) the same as what climate_canvas's own
`interpolate=True, fillin=True` plot would show?

**Answer: yes, effectively identical.** Both use the same method -- Delaunay-linear
(barycentric) interpolation over the same 5 known scenario points:

- `fillin_twl.py`: builds a `scipy.spatial.Delaunay` triangulation over the 5 known
  (precip_delta, temp_delta) points, evaluates it directly at each of the 7 in-hull
  target coordinates. See `docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md`.
- `climate_canvas.data_utilities.interpolator(..., fillin=True)`: tries bilinear grid
  lookup first, falls back to its own `delaunay_fill()` (also a Delaunay-linear fit
  over the same known points) whenever a cell has a missing corner -- true for every
  in-hull scenario here, since none of them land on the sparse known grid's own
  row/column lines.

Same math, same input points -> same answer.

## Verification

`great_lakes.analysis.twl.compare_filled_vs_climate_canvas` evaluates both methods
at each of the 7 in-hull scenario coordinates, for each lake's centroid save point
(same points used by `great_lakes.analysis.twl.plot_known_scenarios`) x ARI
1/10/50/100. Result across all 4 lakes x 4 ARIs x 7 scenarios (112 rows), values in
feet:

| | value |
|---|---|
| max \|diff\| | 0.0164 ft (~5 mm) |
| mean \|diff\| | 0.0080 ft (~2.4 mm) |

Full per-row detail: `filled_vs_climate_canvas_comparison.csv` (written to
`<filled_data_dir>/img/comparison/`, default `data/filled/img/comparison/`).

These sub-0.02-ft differences are floating-point/rounding noise (e.g. climate_canvas's
`interpolator` build order vs `fillin_twl.py`'s), not a methodological gap.

## Caveat: the rendered interpolated plot itself

The comparison above evaluates climate_canvas's interpolator function directly at
the exact in-hull scenario coordinates. The actual
`<data_dir>/img/twl/known/interpolated/<lake>_<ari>.png` plots don't necessarily
sample a pixel exactly at those coordinates -- they resample onto an evenly-spaced
fine grid (`climate_canvas.data_utilities.evenly_space`) sized by
`resample_resolution`, snapping only the *known* (5-point) knot values onto that
grid. So a color read off the plot at, say, `(precip=15, temp=5)` is visually close
to but not guaranteed to land exactly on that fine grid's pixel center -- the
underlying value there (if you evaluated the interpolator function directly, as this
script does) matches `data/filled/`, but the pixel you eyeball on the PNG is a
nearby resampled point, not necessarily that exact coordinate.

## Conclusion

If you'd plotted the `data/filled/` in-hull values directly (instead of relying on
climate_canvas's own interpolate+fillin), you would have gotten essentially the same
result -- both are the same Delaunay-linear fit over the same known points. No
discrepancy to investigate; the two "interpolated" plots (climate_canvas's, and
one hypothetically built from `data/filled/`) would look the same.
