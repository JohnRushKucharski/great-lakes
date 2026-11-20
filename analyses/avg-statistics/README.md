# avg-statistics

## Purpose

Plot ARI (average recurrence interval) response surfaces of the avg (average monthly) lake
levels for the high and low tails, using the Poisson / peaks-over-threshold method. It
answers: what average lake level is associated with a given ARI under each scenario?

avg only: no storm surge or wave set-up (that is swl). See
[`GLOSSARY.md`](../../GLOSSARY.md) for "ARI".

## Status

Implemented.

## Inputs

`data/avg/<lake>_avg.csv` (avg data product; meters, IGLD85). See
[`inputs/README.md`](inputs/README.md).

## Run

No argument is required. From the repository root:

```powershell
uv run python analyses/avg-statistics/scripts/plot_ari_surfaces.py
uv run python analyses/avg-statistics/scripts/plot_ari_surfaces.py --lake superior --ari 100
```

| Option | Default |
| --- | --- |
| `--lake` (repeatable) | all avg lakes |
| `--ari` (repeatable, years, > 1) | all |
| `--root` | the repository root (used by tests) |

## Outputs

`outputs/ari/<clustered|declustered>/<high|low>/` plots (gitignored, regenerable), the
numeric levels in `outputs/ari/<lake>_ari_levels.csv`, and a `README.txt` run record
(inputs, timestamp, files written).

The CSV has one row per tail, population (`clustered`/`declustered`), ARI and scenario
(`lake, tail, population, ari, ari_is_min_floor, scenario, precip_delta, temp_delta,
level_ft`); levels are feet. `ari_is_min_floor` marks the replacement for ARI 1.
`tests/test_avg_ari.py` pins the Superior baseline values to the worked example in the
method note.

## Methods

[`methods/avg_ari_poisson_method.md`](methods/avg_ari_poisson_method.md). Code:
`great_lakes.avg_ari`.

## Assumptions & limitations

- Poisson assumption: exceedances are independent with a constant rate.
- Needs enough declustered events per scenario; a flat series (no events) fails.
- avg only; do not compare directly with swl ARI curves.
