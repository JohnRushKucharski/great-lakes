# How the annual exceedance probability (AEP) is calculated

Each save point's curve gives swl (storm water level) as a function of ARI (Average Return
Interval, years) at 13 fixed points (`0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500,
1000`). Going from a row's `magnitude_value` threshold to a probability takes two steps.

1. **Interpolate the ARI at the threshold.** `interpolate_ari` uses `numpy.interp` against
   the curve's (water level, ARI) points, treating ARI as linear in water level between the
   two bracketing points. A threshold outside the modeled range is clamped to the nearest
   end ARI (`0.1` or `1000`) with a `UserWarning`, not extrapolated.

2. **Convert that ARI to an AEP.** `exceedance_probability` uses the Poisson relation:

   ```
   AEP = 1 - exp(-1 / ARI)
   ```

   not the naive `AEP = 1 / ARI`.

## Why not `1 / ARI`?

ARI is the mean number of years between exceedance events under a Poisson process
(exceedances are independent and arrive at a constant rate `λ = 1 / ARI` per year). The
chance of at least one exceedance in a year is `1 - P(no exceedances) = 1 - exp(-λ)`.
`1 / ARI` is only the first-order approximation (`1 - exp(-x) ≈ x` for small `x`). It
breaks down for `ARI < 1` year, where `1 / ARI` exceeds `1.0` and is not a probability.
These ARI columns go down to `0.1` years, so the naive formula is unsafe here. The Poisson
form stays in `(0, 1)` for any `ARI > 0`.

The two converge for large ARI, so the choice matters below roughly ARI = 10 years:

| ARI (yr) | `1/ARI` | `1 - exp(-1/ARI)` |
| --- | --- | --- |
| 1000 | 0.0010 | 0.0010 |
| 100 | 0.0100 | 0.00995 |
| 10 | 0.100 | 0.0952 |
| 2 | 0.500 | 0.393 |
| 1 | 1.000 | 0.632 |
| 0.1 | 10.00 (invalid) | 0.99995 |

For `>`/`>=` magnitude operators this AEP is the probability the condition holds; for
`<`/`<=` it is the complement (`1 - AEP`). `compute_metric` then converts that probability
into the configured `metric_mode` (`portion`, `percentage`, or `return_period`) the way
`hydropattern.formatters.compute_metric_series` does for timeseries components.
