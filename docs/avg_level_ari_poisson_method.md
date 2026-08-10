# Poisson/Peaks-Over-Threshold method for average-lake-level ARIs

> **Location note:** this doc moved here (from `data/analysis/avg/declustered/METHOD.md`)
> when the Great Lakes analysis scripts were integrated into the `great_lakes`
> package (see `docs/data_pipelines.md`). The script it documents is now
> `great_lakes.analysis.avg.plot_levels` (`src/great_lakes/analysis/avg/plot_levels.py`),
> and its outputs now live under `<data_dir>/img/avg/` (default
> `data/clean/img/avg/`) instead of the old `data/analysis/avg/`. All paths/filenames
> below have been updated to match; the method itself is unchanged.

This documents the method `great_lakes.analysis.avg.plot_levels` uses to compute
the average lake level associated with a given ARI (average recurrence interval,
in years) from the monthly average-lake-level time series in `data/clean/*_avg.csv`,
for both the declustered (`ari/declustered/high/`, `ari/declustered/low/`) and
non-declustered/"clustered" (`ari/clustered/high/`, `ari/clustered/low/`) plots.
All example numbers below are computed from Lake Superior's baseline (`_0_0`)
scenario, 1970-2999 (1030 years, 12,360 monthly values), in feet.

## Why not annual maximum series (block maxima)?

The standard "AMS" approach picks one value per year (the annual max, or min)
and fits a distribution to that reduced, 1-point-per-year sample. It was
explicitly ruled out for this analysis. Instead this uses the **peaks-over-
threshold (POT) / Poisson-process method**: every value in the *full* monthly
record is (potentially) an "event," not just one per year. This uses far more
of the data (up to 12x more raw events per year) at the cost of those events
not being independent draws from one annual extreme-value distribution -- see
"Declustering" below for how that's handled.

## The Poisson-process return-period formula

Model the count of times per year the series exceeds (high tail) or falls
below (low tail) a candidate level `x` as a **Poisson process** with annual
rate `λ(x)`. Under a Poisson process, the probability of *at least one*
exceedance in a given year (the annual exceedance probability, `AEP`) is:

```
AEP(x) = 1 - exp(-λ(x))
```

The ARI (in years) is defined as the reciprocal of the AEP:

```
ARI(x) = 1 / AEP(x)
```

**To find the level `x` for a target ARI**, invert both equations. Let
`years` = length of record in years, and `k(x)` = expected total number of
exceedances of `x` over the whole record = `λ(x) * years`. Solving
`1/ARI = 1 - exp(-k/years)` for `k`:

```
k = years * (-ln(1 - 1/ARI))
```

`k` is generally fractional. Rather than fit a parametric distribution (e.g. a
GPD) to get a continuous `x(k)`, this uses the **empirical order statistic**
directly: sort the candidate population (see below) descending (high tail) or
ascending (low tail), and read off the value at rank `k`, linearly
interpolating between the two neighboring integer ranks when `k` isn't a whole
number. This is a non-parametric estimate -- no distributional assumption
about the exceedances' magnitudes, only about their *timing* (Poisson-rate
arrivals).

**Worked example** (Superior baseline scenario, high tail, ARI=10): record is
1030 years. `k = 1030 * (-ln(1 - 1/10)) = 1030 * 0.10536 = 108.5`. Reading the
108th/109th-largest values (interpolated) of the candidate population gives
the ARI=10 level.

## Declustering

The monthly series is highly autocorrelated -- a single high-water episode can
span many consecutive months. Counting every one of those months as a separate
Poisson "event" inflates `λ` and biases the resulting ARI levels toward less
extreme values (too many "events" makes any level look more frequently
exceeded than it really is, in an independent-events sense).

**Declustered candidate population:** local turning points of the series --
peaks (points strictly higher than both neighbors) for the high tail, troughs
(strictly lower than both neighbors) for the low tail. This is a
threshold-independent way to pick "one representative value per excursion":
a turning point is a turning point regardless of what candidate level `x` is
being tested, so there's no circularity in defining "independent events" before
knowing `x`. This is the standard POT declustering idea, applied at the
coarsest level (every local extremum, no additional minimum-separation rule).

**Non-declustered ("clustered") candidate population:** every monthly value,
unchanged. This is provided alongside the declustered version for comparison;
it's expected to sit closer to the median/mean of the record for a given ARI
(more, less extreme "events" per year -> the same target AEP is reached at a
less extreme level) than the declustered result.

Superior baseline scenario: 12,360 monthly values are declustered to 807 peaks
(0.78/year) and 870 troughs (0.85/year) -- roughly one seasonal high and low
per year, as expected from the lakes' strong annual cycle.

## Why ARI < 1 is dropped, and why ARI=1 is replaced

`AEP = 1/ARI` is a probability, so it must satisfy `AEP <= 1`, which requires
`ARI >= 1`. The TWL workbooks include ARI values below 1 year (0.1, 0.2, 0.5)
because those come from a different, already-tabulated upstream method (likely
fit to sub-annual storm events directly) -- they never pass through this
Poisson-AEP inversion. For the avg-level Poisson method here, `ARI < 1` isn't
just hard to estimate, it's undefined (it would require `AEP > 1`), for
*either* population (declustered or clustered), so those values are dropped
from `AVG_ARIS` entirely: `1, 2, 5, 10, 20, 50, 100, 200, 500, 1000`.

Even `ARI = 1` sits right at the edge (`AEP = 1.0` exactly, which needs an
infinite Poisson rate -- see "The ARI=1/minimum achievable ARI edge case"
below). Rather than plot that capped, possibly-misleading value under the
label "ARI=1," this implementation instead computes the actual worst-case
minimum achievable ARI for each (lake, tail, declustered-or-clustered)
combination, and substitutes that value -- and its own correct label -- in
place of 1. It's applied uniformly across every one of the 17 scenario cells
in a given plot (using whichever scenario's population is sparsest, i.e. has
the highest floor), so the whole response surface stays a single, consistent
ARI comparison rather than secretly mixing return periods cell-to-cell. The
resulting filename and title show the real number (e.g. `superior_1.84.png`,
title `... ARI=1.84 [min] ...`), not `1`.

## The ARI=1 / minimum achievable ARI edge case

The Poisson formula requires `AEP < 1` to solve for a finite `k`; as
`AEP -> 1`, `k -> infinity`. But `k` cannot exceed the candidate population's
size `n` (you cannot have more exceedances than there are candidates), so this
implementation caps `k` at `n` whenever the target `AEP = 1/ARI` meets or
exceeds the population's own *maximum achievable* AEP, `1 - exp(-n/years)`.
When capped, the returned level is simply the population's own extreme value
(minimum, for the high tail; maximum, for the low tail) -- the closest thing to
"always exceeded/undershot" that the population can express. The population's
own maximum achievable AEP corresponds to a minimum achievable ARI,
`1 / (1 - exp(-n/years))` -- this is the "[min]"-labeled value that replaces
the dropped ARI=1 slot.

**Minimum achievable ARI is reached (i.e. the cap triggers) for every
population used here, at ARI=1:**

| population | rate (events/yr) | max achievable AEP | min ARI actually achievable |
|---|---|---|---|
| all months (12/yr, fixed) | 12.0 | 0.999994 | 1.000006 yr |
| declustered peaks | 0.783 | 0.543 | 1.84 yr |
| declustered troughs | 0.845 | 0.570 | 1.75 yr |

For the **non-declustered/clustered** populations, the max achievable AEP
(0.999994) is so close to 1 that the minimum achievable ARI (~1.000006 yr) is
indistinguishable from 1 in practice -- the plotted "min" value there barely
differs from what a literal ARI=1 would have shown.

For the **declustered** populations, the minimum achievable ARI is a real,
practically meaningful floor (~1.7-1.9 years for Superior, varying a bit by
lake and by scenario since each scenario has its own peak/trough count) --
seasonal peaks/troughs occur roughly once a year, not more often, so nothing
shorter than about that is estimable from this population at all. The plotted
`ari/declustered/<tail>/<lake>_<floor>.png` file is that lake+tail's own
worst-case (highest) floor across all 17 scenarios -- see `min_achievable_ari()`
in `great_lakes/analysis/avg/plot_levels.py`.

**Worked example** (Superior baseline, all four populations, in feet; ARI=1
column shown for reference even though it's no longer a separately plotted
file -- the plotted "min" file uses each lake/tail's own worst-case floor
across all 17 scenarios, which is at or beyond this baseline-scenario value):

| ARI (yr) | all-months, high | declustered peaks, high | all-months, low | declustered troughs, low |
|---|---|---|---|---|
| 1 (capped) | 600.000 (= record min) | 601.214 | 603.871 (= record max) | 603.314 |
| 2   | 602.789 | 601.804 | 600.722 | 601.608 |
| 5   | 603.117 | 602.625 | 600.459 | 600.820 |
| 10  | 603.281 | 602.854 | 600.361 | 600.558 |
| 50  | 603.642 | 603.346 | 600.131 | 600.197 |
| 100 | 603.707 | 603.596 | 600.077 | 600.098 |

(record min = 600.000 ft, max = 603.871 ft, mean = 601.744 ft over the full
1030-year baseline series.) Note the ARI=1/capped values sit at or near the
record extremes rather than following the otherwise-smooth ARI=2..100
progression -- exactly the artifact described above, which is why it's now
replaced by the honestly-labeled minimum achievable ARI instead.

## Summary of what's plotted

- `mean/<lake>.png` (under `<data_dir>/img/avg/`, default `data/clean/img/avg/`):
  plain mean of each scenario's full monthly series -- no Poisson method involved.
- `ari/clustered/high/<lake>_<ari>.png`, `ari/clustered/low/<lake>_<ari>.png`:
  non-declustered Poisson ARI levels (population = every monthly value), for ARI in
  `{min achievable (~1), 2, 5, 10, 20, 50, 100, 200, 500, 1000}`.
- `ari/declustered/high/<lake>_<ari>.png`, `ari/declustered/low/<lake>_<ari>.png`:
  declustered Poisson ARI levels (population = local peaks/troughs only), same
  ARI set, but with a lake/tail-specific "min achievable" floor (typically
  ~1.5-2 years, not ~1).

Every one of the above also has an `interpolated/<name>.png` companion in a
sibling `interpolated/` subfolder (climate_canvas `interpolate=True,
fillin=True`, resampled to a finer grid -- since the avg data already has
every one of the 17 scenarios, no Delaunay fillin fallback is ever actually
needed here, this only smooths/resamples).

All values are in feet (converted from the source data's meters); the
colormap threshold and title's "baseline avg=" figure is that lake's baseline
(`_0_0`) scenario mean, matching the convention used for the twl scripts (see
`docs/filled_vs_climate_canvas_comparison.md`).
