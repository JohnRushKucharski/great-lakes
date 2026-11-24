# Filled (hydropattern) vs climate_canvas interpolation -- comparison

**Question:** for the 7 in-hull scenarios, are the filled swl values (the Delaunay fill in
`great_lakes.swl.complete`, saved to `data-products/swl/outputs/filled/`) the same as what
climate_canvas's own `interpolate=True, fillin=True` plot would show?

**Answer: yes, effectively identical.** Both use Delaunay-linear (barycentric)
interpolation over the same 5 known scenario points:

- `great_lakes.swl.complete`: builds a `scipy.spatial.Delaunay` triangulation over the 5
  known (precip_delta, temp_delta) points and evaluates it at each of the 7 in-hull
  target coordinates. See `docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md`.
- `climate_canvas.data_utilities.interpolator(..., fillin=True)`: tries bilinear grid
  lookup first, then falls back to its own `delaunay_fill()` (also Delaunay-linear over
  the same known points) whenever a cell has a missing corner -- true for every in-hull
  scenario here.

## Verification (a gate)

`data-products/swl/scripts/compare_fill_to_climate_canvas.py` evaluates both methods at
each in-hull scenario coordinate, for each lake's centroid save point x ARI 1/10/50/100,
and fails if any difference exceeds `great_lakes.swl.gates.TOLERANCE_FT` (0.05 ft).
Last run: 4 lakes x 4 ARIs x 7 scenarios = 112 rows, values in feet:

| | value |
|---|---|
| max \|diff\| | 0.0164 ft (~5 mm) |
| mean \|diff\| | 0.0084 ft (~2.6 mm) |

Per-row detail is written to `data-products/swl/outputs/gates/fill_vs_climate_canvas/`. The differences are
floating-point/rounding noise (build order of the interpolators), not a methodological gap.

Run it:

```powershell
uv run python data-products/swl/scripts/compare_fill_to_climate_canvas.py
```

## Caveat: the rendered interpolated plot

The comparison evaluates the interpolator function at the exact scenario coordinates.
Rendered `interpolated/` figures resample onto an evenly spaced fine grid, so a pixel
read off the plot is a nearby resampled point, not necessarily that exact coordinate.
