# swl method quality: regression on avg and leave-one-out checks

Run by `workflows/analysis/data-products/swl/scripts/assess_method_quality.py`
(see [`../README.md`](../README.md)). Code: `great_lakes.swl_method_quality`.

These checks ask how far the 12 estimated swl scenarios can be trusted, at one save point
(default 4999, Michigan). swl is storm water level (surge and wave set-up, no near-shore
run-up or overtopping); avg is the average monthly lake level. The two are never mixed:
avg only supplies the scenario-wise average level used as the regression predictor.

## B1: regression of swl on avg

For the 5 modeled (known) scenarios, the full-record mean avg (ft, NAVD88) is the predictor
and the swl at one ARI is the response. An ordinary least squares line is fitted at each
ARI and a 95% prediction interval is computed for each of the 12 estimated scenarios.

- `B1_known_residuals.csv`: fit residuals of the 5 known scenarios.
- `B1_regression_predictions.csv`: predicted swl and 95% interval for each estimated
  scenario and ARI.
- `B1_swl_avg_regression.png`: the regression at `--ari` (default 15 years).

## LOO: leave-one-out checks

Two checks hold known scenarios out and re-estimate them. Errors are in feet (NAVD88):

- `LOO_row_shift.csv`: the row-shift method used for out-of-hull scenarios. The `_10_5` and
  `_20_5` scenarios (same warming row) are each predicted from the other by adding the
  difference in their mean avg, at every ARI.
- `LOO_interpolation.csv`: Delaunay-linear interpolation. `_5_1.5` and `_10_5` are each
  held out and interpolated from the barycentric weights of the remaining known scenarios.

Vertices are visited in the fixed order of
`great_lakes.swl.complete.ALL_SCENARIO_SUFFIXES`, so results are reproducible.

## Limits

Five known points give a very small regression sample; prediction intervals are wide by
construction. These are diagnostics, not corrections: the `data/swl/complete` workbooks are
not changed by them.
