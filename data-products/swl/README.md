# swl data product

## Purpose

Storm water level (swl) frequency curves (water level by ARI) at save points on four lakes
(superior, michigan, huron, ontario) under 17 precip/temp scenarios. swl includes storm
surge and wave set-up; it excludes near-shore processes (run-up, overtopping). USACE
calls this "still water level" (see `GLOSSARY.md`). It is **not** the avg level and is not
processed by `hydropattern`.

## Status

Phase 3 complete: cleaning, completion, figures, two gates and the known-scenario
summary.

## Inputs

`data/raw/still_water_summary__22may2026.xlsm` (meters, IGLD85) and `data/avg/*_avg.csv`.
See `inputs/README.md`.

## Run

```powershell
uv run python data-products/swl/scripts/clean.py [--overwrite]
uv run python data-products/swl/scripts/complete.py [--overwrite]
uv run python data-products/swl/scripts/plot_figures.py [--units ft] [--datum NAVD88] [--summary-only]
uv run python data-products/swl/scripts/compare_fill_to_climate_canvas.py
uv run python data-products/swl/scripts/check_ari_curves.py
uv run python data-products/swl/methods/summarize_precip_temp_effects.py
```

Run `data-products/avg/scripts/clean.py` first (completion needs `data/avg`). Both gates
exit with code 1 on failure. `--units` and `--datum` are separate; defaults are ft and
NAVD88. Pass `--root` to run against another repository root.

## Outputs

| Path | Tracked | Contents |
|---|---|---|
| `data/swl/clean/<lake>_swl.xlsx` | yes | 5 known scenarios per lake |
| `data/swl/complete/<lake>_swl.xlsx` | yes | all 17 scenarios per lake |
| `data/swl/{clean,complete}/figures/<lake>.png` | yes | 2x2 summary (ARI 1, 10, 100, 1000), default ft/NAVD88 |
| `outputs/filled/<lake>_swl.xlsx` | no | 12 scenarios (known + Delaunay filled) |
| `outputs/figures/<clean\|complete>/<lake>_<ari>.png` | no | one figure per lake and ARI |
| `outputs/gates/fill_vs_climate_canvas/` | no | fill comparison csv + README.txt |
| `outputs/gates/ari_curves/` | no | README.txt; `ari_curve_violations.csv` only on failure |
| `outputs/methods/` | no | known-scenario directionality csv and xlsx |

Every script that writes to an `outputs/` folder also writes a `README.txt` there: run
timestamp, inputs, files written, and a flag for stale files left by earlier runs.

Figures show discrete scenario cells; estimated (filled or extrapolated) cells carry a
small dot (see each legend).

## Methods

- Fill and extrapolation: `README.md` ("Scenario completion") and
  `docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md`.
- Fill gate: `methods/compare_fill_to_climate_canvas.md`.
- `methods/summarize_precip_temp_effects.py` summarizes whether higher precip or
  temperature raises or lowers swl across the known scenarios.

## Assumptions & limitations

- **Dropped save points.** Three Michigan save points (IDs 37715, 37727, 37728) have no
  value at any ARI in the source and implausible coordinates (lat about 4, lon about -8).
  The clean step drops them (19517 to 19514 rows); `data/raw/` is unchanged.
- **Gates.** Fill gate: Delaunay fill must match climate_canvas within 0.05 ft
  (`swl.gates.TOLERANCE_FT`). ARI-curve gate: no missing or decreasing value along ARI,
  for any save point and scenario.
- Extrapolated scenarios (5 of 17) assume constant storminess along a warming row, so
  they have lower confidence than known and filled ones.
- Default figures are ft/NAVD88; the older figures were ft/IGLD85 (about +0.44 ft).
