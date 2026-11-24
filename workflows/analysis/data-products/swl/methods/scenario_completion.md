# Scenario completion: `swl/complete.py`

Run by `data-products/swl/scripts/complete.py` (see [`../README.md`](../README.md)).

Each `data/swl/clean/<lake>_swl.xlsx` workbook only has **5 of 17** possible climate
scenarios (the **known scenarios**). `great_lakes.swl.complete` estimates the other 12 (**target
scenarios**), per save point and per ARI column, and writes
`data/swl/complete/<lake>_swl.xlsx` with all 17 scenario sheets (the 12-sheet
intermediate goes to `data-products/swl/outputs/filled/`). `assess-swl-resources` can read
either directory.

Every one of the 17 scenarios is a point on a fixed (`precip_delta`, `temp_delta`) grid.
Plotting the 5 known scenarios' coordinates, the 12 targets split into two groups that
need two different methods:

- **7 in-hull targets** sit inside the convex hull of the 5 known points — a proper
  interpolation (Delaunay-linear) applies.
- **5 out-of-hull targets** sit outside that hull — no interpolation method can honestly
  produce them; extrapolation is required, and extrapolation always trades away some
  confidence in exchange for coverage.

## Stage 1 — Delaunay-linear interpolation (7 in-hull scenarios)

**Theory.** The 5 known (precip_delta, temp_delta) points are triangulated once (scipy's
`Delaunay`). Each in-hull target point falls inside exactly one triangle. Its
**barycentric weights** relative to that triangle's 3 vertices are 3 non-negative numbers
that sum to 1.0 and reconstruct the point's coordinates as a weighted sum of the vertices'
coordinates. Because the same 3 points and weights also work directly on the *known SWL
values* (not just the coordinates), the target scenario's SWL at any save point/ARI cell
is just that same weighted sum of the 3 known scenarios' values at that cell. This is
mathematically equivalent to fitting one flat plane through the 3 known z-values above
that triangle and reading the target point's height off that plane.

**Math.** For target point `T` inside triangle `(A, B, C)` with barycentric weights
`(wA, wB, wC)` (`wA + wB + wC = 1`, all `>= 0`):

```
SWL(l, T, p, r) = wA * SWL(l, A, p, r) + wB * SWL(l, B, p, r) + wC * SWL(l, C, p, r)
```

**Worked example** (a simple hand-computable triangle, not real lake data — see
`SIMPLE_TRIANGLE_*` fixtures in `tests/test_swl_complete.py`): vertices `A=(0,0)->100`,
`B=(10,0)->110`, `C=(0,10)->130` describe the plane `z = 100 + x + 3y`. Target point
`(2, 2)` gets barycentric weights `(wA, wB, wC) = (0.6, 0.2, 0.2)`:

```
z(2,2) = 0.6*100 + 0.2*110 + 0.2*130 = 108.0
```

...which matches the plane formula directly (`100 + 2 + 3*2 = 108`).

**Assumptions/limitations.** Delaunay-linear only assumes the SWL response surface is
*locally* flat within each individual triangle — it makes no claim about linearity
anywhere else on the grid, and different triangles can (and do) have different slopes.
Its one hard limitation is exactly the reason this tool needs a Stage 2 at all: it
**cannot extrapolate** beyond the convex hull of the known points, by construction.

## Stage 2 — Row-shift extrapolation (5 out-of-hull scenarios)

**Theory.** See
[`docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md`](../../../docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md)
for the full rationale. In short: a save point's SWL is treated as `AVG(l, s)` (the mean
lake level under scenario `s`, from `data/avg/<avg-lake>_avg.csv`) plus a "waves" term
that captures storm-driven water level above/below the mean. The assumption is that the
waves term stays constant across scenarios on the same **warming row** (same
`temp_delta`) — i.e. a given amount of warming doesn't change storminess, only the mean
lake level does. Under that assumption, an out-of-hull target scenario's SWL equals a
resolved **anchor scenario**'s SWL (nearest known-or-already-filled scenario on the same
warming row, by `|precip_delta|` distance) plus the difference in average lake level
between the two.

**Math.** For target `s` with anchor `a` (`a` and `s` share `temp_delta`):

```
~SWL(l, s, p, r) = SWL(l, a, p, r) + [AVG(l, s) - AVG(l, a)]
```

Because `AVG(l, s) - AVG(l, a)` doesn't depend on save point `p` or return interval `r`,
this collapses to one additive scalar shift applied uniformly to every cell of the
anchor's sheet — no per-cell computation is needed at runtime.

**Worked example** (see `test_extrapolate_scenarios_shifts_anchor_values_by_avg_delta` in
`tests/test_swl_complete.py`): anchor `_0_7` has SWL values `100.0`/`200.0` at two save
points for one ARI column. `AVG(l, "_0_7") = 180.0` and `AVG(l, "_10_7") = 185.0`, a
`+5.0` delta:

```
~SWL(l, "_10_7", p, r) = 100.0 + (185.0 - 180.0) = 105.0
~SWL(l, "_10_7", p2, r) = 200.0 + (185.0 - 180.0) = 205.0
```

**Anchor selection.** `select_anchor_scenario()` looks for the nearest *resolved*
scenario (known, or already Delaunay-filled) on the same warming row. This matters
because the dT=3 row's out-of-hull point (`_15_3`) anchors to `_10_3`, which is itself a
Stage-1 **filled** scenario, not a known one — so Stage 2 must always run *after* Stage 1.
If no resolved scenario shares the target's warming row, `extrapolate_scenarios()` raises
a `ValueError` rather than silently guessing.

**Assumptions/limitations.** This method is a genuine extrapolation, not an
interpolation — the constant-waves-along-a-row assumption is physically reasonable but
unverified against any additional dT=7/dT=3-row known scenario, since only one point on
each affected row is known. To flag this lower confidence to downstream consumers,
extrapolated sheets get a **distinct** `extrapolated-_<precip_delta>_<temp_delta>` name
prefix, instead of Stage 1's `filled-` prefix.

## CLI usage

```powershell
uv run python data-products/swl/scripts/complete.py [--overwrite]
```

Reads `data/swl/clean/<lake>_swl.xlsx` and `data/avg/<avg-lake>_avg.csv`. Writes the
12-sheet filled workbooks to `data-products/swl/outputs/filled/` (gitignored) and the
17-sheet workbooks (5 known + 7 filled + 5 extrapolated) to `data/swl/complete/`. Without
`--overwrite` the script refuses to replace existing files. Pass `--root` to run against
another repository root.

## Running the tests

```powershell
uv run pytest tests/test_swl_complete.py tests/test_units.py tests/test_lakes.py
```
