# Long Tail Point: habitat

## Purpose

Assess how resilient the planned habitat restoration in Dead Horse Bay (the marsh behind
Long Tail Point, LTP) is to the 17 future lake-level scenarios: planted marsh zones,
submergent vegetation (pondweed) and woody debris structures for musky. Part of the
Framework for Resilient Great Lakes Restoration Initiative (GLRI) work with the Great Lakes
Framework Study. The deliverable is a memo ("Resilience of Dead Horse Bay habitat
restoration plans to future lake levels"), prepared with Jenny Olszewski (USGS).

This workflow uses **avg** (average monthly Michigan-Huron lake level, meters IGLD85) only.
It does not use **swl** (storm water level, which includes storm surge and wave set-up) and
does not include storm, wave or near-shore processes. The scenario runs go through
`hydropattern`.

## Status

Implemented. The memo `deliverables/LTP_habitat_resilience_memo-261112.docx` is the
hand-edited final. `inputs/memo_draft.md` is the repo's Markdown draft; sync it from the docx
with `scripts/sync_draft_from_docx.py`. The history of the memo plan is in
[`docs/plans/ltp_habitat_report_plan.md`](../../../docs/plans/ltp_habitat_report_plan.md).

## Inputs

Data product (committed): `data/avg/michiganhuron_avg.csv` (meters, IGLD85; 17 scenarios).

Tracked in `inputs/` (hand-edited or externally made; scripts never overwrite them):

| File | What it is |
| --- | --- |
| `Compiled PI Survey Data_jo.xlsx` | Dead Horse Bay survey points (`depth_analysis` sheet; bottom elevation in ft) |
| `regimes.xlsx` | pondweed and musky regime criteria (depth, timing, notes with sources) |
| `WI-516-101 LTP 35% PRELIMINARY PLAN 8-20-26.pdf` | Ducks Unlimited 35% plan (structure elevations) |
| `memo_draft.md` | Markdown memo draft; `{{F1}}`..`{{F9}}` mark the figure slots |
| `jenny_maps/F4B.png`, `F4C.png` | Jenny's 3C dry / 3C wet survey-point depth maps, extracted unchanged from her older summary memo |

## Run

From the repository root; no argument is required. `musky_runs.py` and `pondweed_runs.py`
need `hydropattern` 0.3 or later, which the pinned version satisfies. Run them
before the figures that read their tables (F6, F9).

```powershell
uv run python case-studies/long-tail-point/habitat/scripts/musky_runs.py
uv run python case-studies/long-tail-point/habitat/scripts/pondweed_runs.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_lake_movement.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_elevation_ladder.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_marsh_zones.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_wd_scorecard.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_reliability.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_hydrograph.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_cycle_surfaces.py
uv run python case-studies/long-tail-point/habitat/scripts/figure_robustness.py
uv run python case-studies/long-tail-point/habitat/scripts/build_memo_draft.py
uv run python case-studies/long-tail-point/habitat/scripts/sync_draft_from_docx.py [--promote]
```

| Script | Does |
| --- | --- |
| `musky_runs.py` | musky juvenile, spawning and recruitment reliability, floors 573-579 ft, to `outputs/reliability/musky_reliability.csv` |
| `pondweed_runs.py` | pondweed winter survival and growing season, floors 571-577 ft, to `outputs/reliability/pondweed_reliability.csv` |
| `figure_lake_movement.py` | F1: change in mean level by scenario |
| `figure_elevation_ladder.py` | F3: planting and structure elevations vs future levels |
| `figure_marsh_zones.py` | F4: marsh-zone share by scenario; also copies Jenny's F4B/F4C maps |
| `figure_wd_scorecard.py` | F5: woody debris structure scorecard |
| `figure_reliability.py` | F6: reliability by bottom elevation (needs the reliability tables) |
| `figure_hydrograph.py` | F7: baseline vs 3C dry and 3C wet hydrographs |
| `figure_cycle_surfaces.py` | F8: low- and high-water cycle surfaces |
| `figure_robustness.py` | F9: robustness tiers (needs the reliability tables) |
| `build_memo_draft.py` | `outputs/LTP_habitat_resilience_memo_draft.docx` from `inputs/memo_draft.md` |
| `sync_draft_from_docx.py` | recovers the draft from the final docx, shows the diff and structure differences; `--promote` replaces `inputs/memo_draft.md` after backing it up |

All take `--root` (used by tests). The survey workbook is large (26 MB); the figure scripts
that read it (F3, F4) take about a minute each.

## Outputs

`outputs/` is regenerable and gitignored, except the figures and reliability tables the
memo is built from:

| Path | Tracked | Contents |
| --- | --- | --- |
| `outputs/figures/` | yes | memo figures F1, F3-F9 (png), F4B/F4C, `README.txt` |
| `outputs/reliability/` | yes | `musky_reliability.csv`, `pondweed_reliability.csv`, `README.txt` |
| `outputs/LTP_habitat_resilience_memo_draft.docx` and the sync files | no | build and sync products |

Scripts never write to `deliverables/`. Figure and table units: lake levels convert m to ft
only (no datum change; everything is IGLD85); floors are ft IGLD85.

## Methods

The reviewed method notebooks are in `methods/` and are saved with their outputs. They read
`data/avg/michiganhuron_avg.csv` and need `hydropattern` 0.3 or later (the pin satisfies it):

- `musky_habitat.ipynb`: musky criteria at one floor (`BOTTOM_FT`, 573-579 ft; saved at 576).
- `pondweed_habitat.ipynb`: pondweed criteria at one floor (`BOTTOM_FT`, 574-576 ft; saved
  at 575).
- `musky_matrix.ipynb`: musky response surfaces for all floors 573-579 ft.
- `low_water_cycles.ipynb`, `high_water_cycles.ipynb`: the low-water (175.90-176.30 m,
  24-60 months) and high-water (>= 176.75 m, >= 24 months) cycle definitions behind F8.

`musky_runs.py` and `pondweed_runs.py` apply the same criteria headless across all floors.

## Assumptions & limitations

- Monthly average levels only: passing every monthly average does not mean a threshold held
  every day. Storm surge, waves and near-shore processes are not included.
- Reliability targets and depth ranges come from Jenny Olszewski's habitat criteria; they
  are conditional guidance, not a recommendation.
- The musky and pondweed floors are only run over each species' native range (musky 573-579,
  pondweed 571-577 ft); other cells are n/a.

## Deliverables

`deliverables/LTP_habitat_resilience_memo-261112.docx`: the final memo. Retired and left
untracked: earlier memo drafts (`LTP_habitat_resilience_memo.docx`, `_v2.docx`), Jenny's older
summary docx and the first-draft slides.
