# Long Tail Point: overtopping

## Purpose

Assess how robust candidate top-of-dune elevations at Long Tail Point (LTP; 584 and 586 ft
NAVD88) are to the 17 future lake-level scenarios, benchmarked against the 15-year ARI
storm water level (swl) plus a runup allowance. Part of the Great Lakes Coastal Resiliency
Study. The deliverable is a memo and a results dashboard.

This workflow uses **swl** (storm surge and wave set-up, as ARI frequency curves; USACE
often calls it "still water level") and **avg** (average monthly lake level) side by side,
never mixed: swl gives the elevations, avg describes the scenarios. Neither includes
near-shore run-up or overtopping; the runup allowance is an assumed, added number.
Habitat is a separate analysis: see [`../habitat/`](../habitat/).

## Status

Implemented. The memo `deliverables/longtailpoint_memo_261030.docx` is the "final-final",
edited by hand in Word. `inputs/memo_draft.md` is the repo's Markdown draft; sync it from the
docx with `scripts/sync_draft_from_docx.py`.

## Inputs

Data products (committed under `data/`): `data/avg/michiganhuron_avg.csv` and
`data/swl/complete/michigan_swl.xlsx` (meters, IGLD85; converted to ft NAVD88 for results).

Tracked in `inputs/` (hand-edited files; scripts never overwrite them):

| File | What it is |
| --- | --- |
| `batch_swl-longtail.xlsx` | resources+config worksheet: swl rows (save points 1968, 4997, 4999; top-of-dune 582-587 ft; runup 0, 2, 2.5, 3 ft) |
| `batch_avg.xlsx` | resources+config worksheet: avg rows |
| `longtail_waterlevel.xlsx` | LTP water-level inputs |
| `memo_draft.md` | Markdown memo draft; figures are `../outputs/figures/...` |
| `figures/F1_savepoints.png` | Figure 1 (locator map), made outside the repo |

Fig A-1 (annotated dashboard screenshot) is made outside the repo and added to the Word
memo by hand.

The worksheets' `output_directory` is relative to the repository root. Note
`batch_avg.xlsx` has `overwrite = False`: delete `outputs/batch_avg_output/` before
re-running it.

## Run

From the repository root; no argument is required:

```powershell
uv run python case-studies/long-tail-point/overtopping/scripts/make_figures.py
uv run python case-studies/long-tail-point/overtopping/scripts/run_assessments.py
uv run python case-studies/long-tail-point/overtopping/scripts/build_dashboard.py
uv run python case-studies/long-tail-point/overtopping/scripts/package_dashboard.py
uv run python case-studies/long-tail-point/overtopping/scripts/build_memo_docx.py
uv run python case-studies/long-tail-point/overtopping/scripts/sync_draft_from_docx.py [--promote]
```

| Script | Does |
| --- | --- |
| `make_figures.py` | memo figures and tables (F2, F3, F4, B1, T1, T2, LOO) to `outputs/figures/` |
| `run_assessments.py` | runs both worksheets (batch-resources engine); exit 1 if any row fails |
| `build_dashboard.py` | `outputs/dashboard.html` + `manifest.js` from the swl worksheet's outputs (`--include-avg` adds avg) |
| `package_dashboard.py` | `outputs/long-tail-point-dashboard.zip` (fails if a linked file is missing) |
| `build_memo_docx.py` | `outputs/longtailpoint_memo_draft.docx` from `inputs/memo_draft.md` |
| `sync_draft_from_docx.py` | recovers the draft from the final docx, shows the diff and structure differences; `--promote` replaces `inputs/memo_draft.md` after backing it up |

All take `--root` (used by tests). `make_figures.py` takes `--save-point-id` (4999) and
`--ari` (15). Run `run_assessments.py` before `build_dashboard.py`.

## Outputs

`outputs/` is regenerable and gitignored, except what the memo embeds and the dashboard
viewer files:

| Path | Tracked | Contents |
| --- | --- | --- |
| `outputs/figures/` | yes | memo figures (png) and the tables behind them (csv), `README.txt` |
| `outputs/dashboard.html`, `manifest.js` | yes | static results dashboard (double-click to open) |
| `outputs/batch_swl_output/`, `batch_avg_output/` | no | per-row grids and plots |
| `outputs/long-tail-point-dashboard.zip` | no | shareable dashboard |
| `outputs/longtailpoint_memo_draft.docx` and the sync files | no | build and sync products |

Scripts never write to `deliverables/`. Result file names carry the elevation in ft
NAVD88 and match the results of the earlier (pre-reorganization) runs exactly (e.g. `582d00`).

### Sharing the dashboard

The zip is published as a GitHub Release asset (tag `v1`), not committed:

```powershell
gh release create v1 case-studies/long-tail-point/overtopping/outputs/long-tail-point-dashboard.zip --title "Long Tail Point dashboard" --notes "Unzip and open dashboard.html."
```

## Methods

- swl method quality (B1, LOO):
  [`workflows/analysis/data-products/swl/methods/method_quality.md`](../../../workflows/analysis/data-products/swl/methods/method_quality.md).
- avg scenario statistics (F2, F3, T2):
  [`workflows/analysis/data-analysis/avg-statistics/`](../../../workflows/analysis/data-analysis/avg-statistics/README.md).
- T1 (design coverage) and F4 (swl elevation surface with the design and runup lines) are
  specific to this memo and live in `great_lakes.overtopping`.
- Scenario completion and the swl/avg assessments:
  [`workflows/analysis/data-products/swl`](../../../workflows/analysis/data-products/swl/README.md),
  [the swl batch-resources workflow](../../../workflows/evaluation/swl/batch-resources/README.md).

## Assumptions & limitations

- 12 of 17 swl scenarios are interpolated or extrapolated from 5 modeled ones; figures mark
  modeled, interpolated and extrapolated cells. The dashboard does not.
- Runup allowances are assumed (0, 2, 2.5, 3 ft), not computed. Overtopping itself is not modeled.
- Results are indicative ranges, not guarantees.
- Known issue: avg row 1 (`longtail_17877/mo_avg`) fails with "vmin, vcenter, and vmax must
  be in ascending order"; the other avg rows succeed.

## Deliverables

`deliverables/longtailpoint_memo_261030.docx`: the final memo. Retired and left untracked:
the older `MEMORANDUM.docx` and `longtailpoint_memo.docx`.
