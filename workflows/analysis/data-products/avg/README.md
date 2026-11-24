# avg data product

## Purpose

Average (monthly) lake water levels for the five lakes (superior, michiganhuron, stclair,
erie, ontario) under 17 precip/temp climate scenarios, cleaned from the raw workbook and
shown as response-surface figures. These are **avg** levels only: they contain no storm
surge or wave set-up (see the swl product for that, and `GLOSSARY.md`).

## Status

Implemented: cleaning and figures. The ARI figures and the other avg statistics live in
[`avg-statistics`](../../data-analysis/avg-statistics/README.md).

## Inputs

`data/raw/lake_levels_all_scenarios_9jul2026.xlsx` (meters, IGLD85). See
`inputs/README.md`.

## Run

```powershell
uv run python workflows/analysis/data-products/avg/scripts/clean.py [--overwrite]
uv run python workflows/analysis/data-products/avg/scripts/plot_figures.py [--units ft] [--datum NAVD88]
```

`--units` (m or ft) and `--datum` (IGLD85 or NAVD88) are separate options; each is applied
only if it differs from the source. Defaults are ft and NAVD88. Pass `--root` to run
against another repository root.

## Outputs

| Path | Tracked | Contents |
|---|---|---|
| `data/avg/<lake>_avg.csv` | yes | cleaned monthly series, one column per scenario (5 files) |
| `data/avg/figures/<lake>.png` | yes | mean level surface, one per lake (5 figures), default ft/NAVD88 |
| `outputs/figures/<lake>.png` | no | same, raw cells |
| `outputs/figures/interpolated/<lake>.png` | no | same, interpolated for readability |
| `outputs/figures/<units>_<datum>/` | no | figures for non-default `--units`/`--datum` only |
| `outputs/figures/README.txt` | no | run record: timestamp, inputs, files written |

Figures show the discrete scenario cells. Michiganhuron stands for both Michigan and Huron
(one hydraulically connected lake).

## Methods

The mean surface is the mean of each scenario's full monthly record (1970-2999),
converted with `great_lakes.units`; the colormap is diverging around the baseline
(`_0_0`) mean. See `GLOSSARY.md` for AVG(l,s).

## Assumptions & limitations

- Dates run to 2999, beyond pandas' nanosecond range, so the clean step formats them as
  strings.
- Datum shifts are a constant offset (+0.44 ft from IGLD85 to NAVD88 in the default
  figures versus the older ft/IGLD85 figures).
