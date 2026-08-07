---
status: accepted
---

# Row-shift extrapolation for out-of-hull TWL scenarios

## Context

Each `<lake>_twl.xlsx` workbook has 5 **known scenarios** (of 17 total precip/temp
scenarios represented in the `<avg-lake>_avg.csv` average-lake-level data) per save
point. Of the 12 **target scenarios**, 7 fall inside the known scenarios' convex hull
in (precip_delta, temp_delta) space and are estimated via Delaunay-linear
(barycentric) interpolation (see `fillin_twl.py`). The remaining 5 fall *outside* the
hull. Delaunay-linear interpolation cannot extrapolate — `scipy.spatial.Delaunay`
raises (`find_simplex` returns `-1`) for any point outside the triangulation. Those 5
scenarios need a different estimation method, or they stay unfilled indefinitely.

Considered options:

1. **Leave them unfilled.** Rejected — the goal is full 17-scenario coverage per save
   point per lake.
2. **A single global regression/plane fit across all known points**, extrapolated
   linearly beyond the hull. Rejected — a single global linear relationship across the
   whole (precip_delta, temp_delta) domain has no reason to hold physically (the
   known scenarios were chosen unevenly, not to support one global linear model), and
   was already discussed and set aside earlier in this project in favor of the
   piecewise Delaunay approach for the in-hull case.
3. **Row-shift extrapolation** (chosen): for each out-of-hull target scenario, shift a
   same-warming-row known-or-filled scenario's full TWL sheet by the difference in
   average lake level between the two scenarios.

## Decision

For an out-of-hull target scenario `s`, pick its **anchor scenario** `a`: the
known-or-already-filled scenario sharing `s`'s temp_delta (same **warming row**),
nearest to `s` by precip_delta distance. (This requires the Delaunay-linear
interpolation stage to run first, since some anchors — e.g. `_10_3` anchoring `_15_3`
— are themselves filled scenarios, not known ones.) Estimate `s`'s entire
water-level-vs-ARI sheet as anchor `a`'s sheet shifted by a single additive constant:
the difference in **average lake level (AVG)** between `s` and `a`.

### Underlying physical assumption

TWL at a save point and return interval decomposes into a mean-lake-level term and a
"waves" term (storm surge / wind setup / wave runup above the mean level):

```
waves(l, x, p, r) = TWL(l, x, p, r) - AVG(l, x)
```

The assumption: **for two scenarios sharing the same temp_delta (warming amount),
the waves term is approximately unchanged by precip_delta** — the storm/wind/ice
climate driving wave setup is governed primarily by *warming*, not by precipitation
inputs to the lake's water balance. Precipitation instead governs `AVG(l, x)` (the
lake's mean water balance / mean level) directly. So moving along a fixed-dT row
(varying only precip_delta) changes TWL almost entirely through the shift in AVG, not
through a change in storm/wave climate:

```
waves(l, s, p, r) ≈ waves(l, a, p, r)   for all save points p, all return intervals r,
                                          whenever temp_delta(s) == temp_delta(a)
```

### The math

Starting from the assumption above:

```
~TWL(l, s, p, r) = waves(l, a, p, r) + AVG(l, s)
                 = [TWL(l, a, p, r) - AVG(l, a)] + AVG(l, s)
                 = TWL(l, a, p, r) + [AVG(l, s) - AVG(l, a)]
```

`AVG(l, s)` and `AVG(l, a)` are both single scalars (independent of save point `p` and
return interval `r`), so `[AVG(l, s) - AVG(l, a)]` is a single additive constant —
call it `Δ(l, a, s)`. The estimate for the *entire* target sheet is therefore anchor
`a`'s full sheet plus one scalar, applied uniformly to every save point row and every
ARI column:

```
~TWL(l, s, p, r) = TWL(l, a, p, r) + Δ(l, a, s),  for every (p, r)
```

`AVG(l, x)` itself is the mean of the *entire* synthetic scenario record (~12,360
monthly rows spanning 1970-2999) in `data/clean/<avg-lake>_avg.csv` for scenario `x`'s
column. `michigan` and `huron` (separate `<lake>_twl.xlsx` workbooks) both read
`michiganhuron_avg.csv`, since Michigan-Huron is one hydraulically-connected lake with
one water level.

### Anchor examples in today's data

- **dT=7 row**: only `_0_7` is known; `_5_7`, `_10_7`, `_15_7`, `_20_7` are all
  out-of-hull and all anchor to `_0_7` (the only resolved point on that row).
- **dT=3 row**: `_0_3`, `_5_3`, `_10_3` are in-hull (Delaunay-filled); `_15_3` is
  out-of-hull and anchors to `_10_3` (nearest resolved point on that row, itself a
  filled — not known — scenario).

## Consequences

- Row-shift extrapolation is a genuinely lower-confidence estimate than Delaunay
  interpolation: it extrapolates in the real sense (beyond the known data's convex
  hull) and rests on the waves-invariance assumption above, which is not directly
  tested by the data. This is flagged to downstream consumers via a distinct sheet
  name prefix, `extrapolated-_<precip>_<temp>` (vs. `filled-_<precip>_<temp>` for
  Delaunay-interpolated sheets) rather than reusing the same prefix.
- Anchor selection is "nearest already-resolved scenario on the same row by
  precip_delta distance," not a hardcoded scenario pair — this generalizes correctly
  even though every warming row in today's data happens to have exactly one resolved
  anchor.
- The interpolation stage must run before the extrapolation stage, since some anchors
  are Delaunay-filled scenarios rather than known ones.
