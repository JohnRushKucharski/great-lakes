# Equivalent elevation

Enabled per row by the `equivalent_elevation` resources-sheet column: `"baseline_magnitude"`
(case-insensitive) or a number. A blank cell skips it. The row then also writes:

```
duluth_harbor_swl_1_equivalent_elevation_grid.csv   <- one water level per scenario
duluth_harbor_swl_1_equivalent_elevation_plot.png   <- response-surface plot
```

## Question answered

The row's baseline-ARI lookup value corresponds to some ARI under the baseline (`_0_0`)
scenario. What water level is equally likely (same ARI) under every other scenario?

## Method

The lookup value is `magnitude_value` for `"baseline_magnitude"`, or the cell's own number
for a numeric override. The override replaces `magnitude_value` for this analysis only; the
primary grid and plot always evaluate `magnitude_value`.

1. Find the baseline scenario's ARI at the lookup value (`interpolate_ari`, the same lookup
   the primary grid uses).
2. Look that ARI up on every scenario's own water-level-vs-ARI curve (`interpolate_level`,
   the reverse interpolation) to get that scenario's equivalent elevation.

The baseline scenario's own cell is always the lookup value itself.

## Plot differences from the primary plot

- The z-axis label is `"Equivalent Elevation"`, not the `metric_mode` units.
- The plot threshold is the baseline-ARI lookup value (a water level, not a metric value).
- It uses `plot_color_map` as configured, with no automatic RdBu reversal and no
  `plot_color_map_ticks`. Those are keyed to `success_pattern`/`metric_mode`, which do not
  apply to a raw elevation.
