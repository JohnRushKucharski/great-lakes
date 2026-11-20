# Repository reorganization plan

Status: **approved, not started** (decided with the owner in a design interview, 2026-11-20).
Owner: John Kucharski (JK). Read `GLOSSARY.md` first and use its terms exactly.

## 1. Goal

This repo is **not a software project**. It documents and makes reproducible a set of
analyses for the Great Lakes Framework Study and the Great Lakes Coastal Resiliency Study,
as clearly named, easy-to-find **workflows**. Software (`src/great_lakes/`, built on
`hydropattern`) only supports the workflows. The repo has grown messy; this plan
reorganizes folders, names, tracking, and documentation. Analytical results must not change
(exception: the lake-centroid save point, section 5).

Workflows identified:

1. Data products: clean / complete (fill + extrapolate) / validate **avg** and **swl** data.
2. Case studies at Long Tail Point (LTP): (a) overtopping for a beach nourishment project,
   (b) habitat for a Dead Horse Bay restoration project.
3. Further analysis of cleaned avg data (ARI, Poisson counts, persistence; ANOVA and
   autocorrelation to come; historical levels later).
4. Generic resource assessment from a worksheet against avg or swl.

## 2. Target layout

```
README.md                  index: purpose, workflow table, Mermaid dependency graph,
                           `uv sync` setup, conventions
GLOSSARY.md                domain glossary (formerly CONTEXT.md)
data/                      raw/ (read-only, never edit), avg/, swl/clean/, swl/complete/
                           (each with tracked figures/), plus data/README.md
data-products/{avg,swl}/   workflow: README, inputs/, scripts/, methods/, outputs/
analyses/
  avg-statistics/          implemented
  assess-avg-resources/    implemented (batch, v1 worksheets)
  assess-swl-resources/    implemented (batch, v1 worksheets)
  report-resources/        PLANNED: combined avg+swl report, joins on Resource label
  assess-avg-resource/     PLANNED: single resource, simplified worksheet
  assess-swl-resource/     PLANNED: single resource, from single_resource_swl.xlsx
case-studies/long-tail-point/{overtopping,habitat}/
                           README, inputs/, scripts/, methods/, outputs/, deliverables/
docs/                      adr/, plans/, methods-index.md  (repo-wide only)
src/great_lakes/           shared library, import-only (no __main__, no `python -m` docs)
tests/                     all pytest
```

Rules: grouped by role; folder names verb-noun, kebab-case; **no numeric or letter
prefixes**; use `avg` (never "avg-level"). Planned workflows get a stub README only.
Overtopping and habitat are **separate case studies**: never share drafts, memos, or
scripts between them (the only shared code is the library, e.g. `memo/to_docx.py`).

### Workflow anatomy

| Folder | Holds |
|---|---|
| `README.md` | headings in order: Purpose, Status, Inputs, Run, Outputs, Methods, Assumptions & limitations, Deliverables (case studies only) |
| `inputs/` | tracked; everything needed to reproduce outputs; hand-edited files are called out |
| `scripts/` | thin entry points, **no required args**, run by path from repo root, e.g. `uv run python data-products/swl/scripts/complete.py`; include pass/fail **gates** |
| `methods/` | method notes, fit-quality validation, descriptive figures/notebooks |
| `outputs/` | regenerable; gitignored except what is embedded in docs or listed as tracked |
| `deliverables/` | final memos only; scripts never write here |

Validation rule: a pass/fail check is a **gate** (`scripts/`). Fit quality or descriptive
material is a **method note** (`methods/`). `docs/methods-index.md` is a hand-maintained
table (method note, workflow, type = method/validation/figure set/notebook, status =
final / "draft, incomplete"). A pytest fails on any file in a `methods/` folder missing
from the index, and on dead links. Non-methodological plans live in `docs/plans/` and are
not indexed.

### Entry points and tests

- Scripts call shared library code (DRY). No console command is installed.
- Library logic tests import `great_lakes`. One subprocess smoke test per workflow runs its
  scripts by path on small fixtures. CI = ruff (also covers workflow `scripts/`), mypy,
  pytest. All three must pass at the end of every phase.

## 3. Data layout

- `data/README.md` documents each dataset and figure (what it includes and does NOT).
- avg: `data/avg/` plus `figures/` (keep all 4 lake figures).
- swl: `data/swl/clean/` (5 known scenarios) and `data/swl/complete/` (all 17 scenarios),
  each with `figures/<lake>.png`: a 2x2 of ARI 1/10/100/1000, one colorbar **per panel**,
  save point nearest the LAKE centroid; in `complete/`, estimated cells are visibly marked.
- The `filled` data (in-hull only) is an intermediate in
  `data-products/swl/outputs/filled/`, used for validation.
- Bulk figures go to workflow `outputs/figures/` (untracked). A single `plot_figures.py`
  writes both bulk and tracked summaries in one run (`--summary-only` for summaries) so the
  two stay in sync.
- Units and datum are independent options `--units {m,ft}` and `--datum {IGLD85,NAVD88}`,
  default **ft, NAVD88**. Labels always state both ("Water level (ft, NAVD88)"). Tracked
  summary figures use defaults only. Split helpers into `convert_units` and `convert_datum`
  (merge the duplicate `m_igld85_delta_to_ft_NAVD88` in `longtailpoint_report.py`).
- Size reference: `data/clean/img` 33 MB, `data/extrapolated/img` 12.6 MB,
  `data/filled/img` 10 MB (these old image folders are replaced by the new figures).

## 4. Rename and move map

Scripts:

| Old | New |
|---|---|
| `clean_lake_levels_all_scenarios.py` | `data-products/avg/scripts/clean.py` |
| `clean_swl_summary.py` | `data-products/swl/scripts/clean.py` |
| `fillin_swl.py` | `data-products/swl/scripts/complete.py` (does BOTH in-hull interpolation and row-shift extrapolation; writes `outputs/filled/` and `data/swl/complete/`) |
| `analysis/swl/plot_*.py` | `data-products/swl/scripts/plot_figures.py` (+ new 2x2 `<lake>.png`) |
| `compare_filled_vs_climate_canvas.py` | `data-products/swl/scripts/compare_fill_to_climate_canvas.py` (now a **gate**: fail if any difference > **0.05 ft**) |
| `docs/filled_vs_climate_canvas_comparison.md` | `data-products/swl/methods/compare_fill_to_climate_canvas.md` |
| `analyze_known_scenarios.py` | `data-products/swl/methods/summarize_precip_temp_effects.py` (% change in SWL for precip pair `_10_5`->`_20_5` and temp pair `_0_0`->`_0_7`, all save points and ARIs) |
| `analysis/avg/plot_levels.py` | `analyses/avg-statistics/scripts/plot_ari_surfaces.py` |
| `docs/avg_level_ari_poisson_method.md` | `analyses/avg-statistics/methods/avg_ari_poisson_method.md` |
| `batch_run_avg.py` / `batch_run_swl.py` | `analyses/assess-{avg,swl}-resources/scripts/assess.py` |
| `build_avg_template.py` / `build_swl_template.py` | `analyses/assess-{avg,swl}-resources/scripts/build_template.py` |
| `build_dashboard.py` | overtopping `scripts/build_dashboard.py` |
| (new) | overtopping `scripts/package_dashboard.py` (section 6) |
| habitat `report/build_report.py` | habitat `scripts/build_memo_draft.py` |
| `memo_docx_to_md.py` (CLI) | `sync_draft_from_docx.py` in each case study `scripts/` |
| habitat `figure_f*.py` | `scripts/figure_<content>.py` (named by content; derive from the habitat plan/draft) |
| habitat `musky_runs.py`, `pondweed_runs.py` | `scripts/`; their CSVs -> `outputs/` (tracked: memo tables depend on them) |

Library (`src/great_lakes/`):

| Old | New |
|---|---|
| `common_swl.py` | split: `units.py` (convert_units, convert_datum, labels), `lakes.py` (lake names, avg filenames, centroids, save-point selection), `swl/sheets.py` |
| `ari_constants.py` | `ari.py` |
| `batch_runner.py`, `run_readme.py` | `batch/runner.py`, `batch/run_readme.py` |
| `build_memo_docx.py`, `memo_docx_to_md.py` | `memo/to_docx.py`, `memo/from_docx.py` |
| `longtailpoint_report.py` | split three ways: generic avg stats (annual_maxima, high_year_flags, rolling window shares, Poisson counts T2, persistence F2/F3) -> `avg-statistics`; swl method quality (B1 regression, LOO_*, T1) -> `data-products/swl/methods/`; overtopping-specific (F4, presentation figure/note, runup) -> overtopping |

`build_memo_docx` is shared: remove its overtopping defaults (`docs/longtailpoint_memo_draft.md`,
`longtailpoint/longtailpoint_memo.docx`). Remove old import paths when moving (no shims).

Docs and templates:

| Old | New |
|---|---|
| `docs/report_plan.md` | `docs/plans/ltp_overtopping_report_plan.md` (strip approvals and `[Review: ...]` notes, keep figure/table plan, mark unfinished "draft, incomplete") |
| `longtailpoint/habitat/report/PLAN.md` | `docs/plans/ltp_habitat_report_plan.md` (habitat only) |
| `templates/template_report.md` | `docs/plans/resource_report_plan.md` (UNIMPLEMENTED spec; unfinished at "6. Assign high+"; blank "Sensitivity to Lake Level Change"; mark "draft, incomplete") |
| `templates/template_{avg,swl}.xlsx`, `new_template_batch_run_*.xlsx` | each workflow's `inputs/templates/` (v1 must keep working; v2 will eventually replace it) |
| `templates/single_resource_swl.xlsx` | `analyses/assess-swl-resource/inputs/` (planned workflow) |
| `docs/data_pipelines.md` | sections 1-8 distributed into workflow READMEs and `methods/`; the audit-log appendix (9-16) DELETED after moving any still-true notes into "Assumptions & limitations" |
| `README.md` "Batch tool 1/2/3" | become the workflow READMEs; root README becomes the index |

Naming: write "Long Tail Point (LTP)" in prose; folder `long-tail-point/`; no `ltp_`
prefix inside that folder, only on files that leave it (e.g. `docs/plans/ltp_*.md`).

## 5. Save point (centroid) change

New `lake_centroid_save_point_id(lake, sheets)` in `lakes.py`: nearest save point to the
lake centroid, longitude scaled by cos(lat). Centroids (lat, lon): superior 47.72, -86.94;
michigan 44.01, -86.76; huron 44.94, -82.22; erie 42.25, -81.15; ontario 43.63, -77.62.
Only superior, michigan, huron, ontario have swl workbooks. It replaces
`common_swl.center_save_point_id` (mean lat/lon; wrong, e.g. superior 15559 vs 5400)
**only** in data-product cleaning and figure code (`compare_*`, `plot_*`, `plot_levels`),
**not** in resource analyses. Test-first.

## 6. Case studies

### Overtopping (`case-studies/long-tail-point/overtopping/`)

- Hand-edited inputs: `batch_avg.xlsx`, `batch_swl-longtail.xlsx`, and the memo.
- Master memo: `longtailpoint_memo_261030.docx` (hand-edited outside the repo, "final-final").
  `MEMORANDUM.docx` is a superseded agent draft: retire. `longtailpoint_memo.docx`: older, retire.
- Fig 1 (`presentation/F1_savepoints.png`) and Fig A-1 (dashboard screenshot) were made
  outside the repo: tracked inputs. Other figures come from `longtailpoint_report.py`
  (F2/F3/B1/T1/T2/LOO) and `presentation/make_presentation_figure.py` (4999 ARI-15
  elevation); see the old `docs/report_plan.md`.
- `longtailpoint/presentation/` is split per the library split above (generic avg stats ->
  `avg-statistics`; swl method quality -> `data-products/swl/methods/`; overtopping items stay).
- Sync the repo draft from the final docx (phase 5): back up the old draft, run
  `memo_docx_to_md` with `--out` into `outputs/`, check structure and slots, review the diff
  with the owner, promote only after approval. Flag structure differences, do not force.
- **Dashboard is a deliverable** (sent to people as a zip, no install). Add
  `scripts/package_dashboard.py`: builds `outputs/long-tail-point-dashboard.zip` containing
  `dashboard.html`, `manifest.js`, the batch output PNGs/CSVs, `START_HERE.txt`; **no input
  workbooks**; fail if the dashboard links a missing file. Zip is gitignored (current
  hand-made zip is 54 MB and has stale `batch_twl_output/` names: use `swl`). Publish it as
  a GitHub Release asset, **tag `v1`**:
  `gh release create v1 outputs/long-tail-point-dashboard.zip ...`; document the command in
  the workflow README. `dashboard.html` and `manifest.js` stay tracked.

### Habitat (`case-studies/long-tail-point/habitat/`)

- Dissolve the person folders `JK` (John Kucharski) and `JO` (Jennifer Olszewski).
- Memo master is the hand-edited docx (`LTP_habitat_resilience_memo-261112.docx`); build
  scripts never overwrite `deliverables/` (drafts go to `outputs/`). `report_draft.md` was
  synced to that docx on 2026-11-20.
- Tracked inputs: `Compiled PI Survey Data_jo.xlsx` (26 MB, owner OK), the plan PDF
  `WI-516-101 LTP 35% PRELIMINARY PLAN 8-20-26.pdf`, `regimes.xlsx` (check use).
- Notebooks are separate explorations from `*_runs.py` and are **kept**. Merge
  `musky_573..579.ipynb` into one `musky_habitat.ipynb` and `pondweed_574..576.ipynb` into
  one `pondweed_habitat.ipynb`: `BOTTOM_FT` set in a top cell with a comment giving the
  expected range (musky 573-579 ft, pondweed 574-576 ft); tracked **with outputs** for a
  mid-range default (musky 576, pondweed 575); import helper functions from the matching
  script (verify the logic is identical first); replace the hydropattern `ROOT` path hack
  (it fails inside this repo) with a normal import. `musky_matrix.ipynb`,
  `high_water_cycles.ipynb`, `low_water_cycles.ipynb` go to `methods/`.
- Retire: pptx files, `JK/high-water-handoff.md` (stale `examples\longtailpoint` path),
  stale memo versions (`LTP_habitat_resilience_memo.docx`, `_v2.docx`), the older
  `longtail_habitat_summary_28oct2026.docx` (confirm with owner), `__pycache__`.
  `michiganhuron_avg.csv` (1.5 MB) and its PNG: untracked unless used as inputs (confirm).

## 7. Tracking policy and `.gitignore` flip

Tracked: final `data/` datasets and figures, `inputs/`, figures embedded in docs,
`deliverables/` (final memo only), `dashboard.html`, `manifest.js`. Gitignored: other
`outputs/`, `__pycache__`, the dashboard zip, `skills/` (`.github/skills` is local-only AI
tooling). The `.gitignore` flip is approved: currently ignored but to be tracked are
`longtailpoint/habitat/{JK,JO,report}/` content (per section 6), `longtailpoint_report.py`
and its tests, `docs/longtailpoint_memo_draft.md`, `docs/report_plan.md` (triage first),
final memos, and `data/{clean,filled,extrapolated}` (replaced by the new layout).
(`build_memo_docx.py` and its test were already flipped in the prep commit.)
Many of these exist **only locally**: they are untracked, so use plain moves, then flip
`.gitignore`, then `git add` (not `git mv`). Do not commit generated artifacts or zips
without asking.

## 8. Phases

One branch `reorg` off `main`, one PR, one commit per phase, ruff + mypy + pytest green at
the end of each phase. Ask the owner before every commit and push.

1. **Prep.** Triage stale drafts and `[Review: ...]` notes; flip the rest of `.gitignore`;
   track the files listed in section 7. (GLOSSARY rename, `memo_docx_to_md`,
   `build_memo_docx` and this plan are already on `main`.)
2. **Library split** (test-first): `units.py`, `lakes.py` (centroid fix), `ari.py`,
   `swl/sheets.py`, `batch/`, `memo/`; split `longtailpoint_report.py`; remove old import paths.
3. **`data-products/`**: move scripts, data, figures, methods; add `plot_figures.py`,
   `compare_fill_to_climate_canvas.py` gate (0.05 ft), `--units/--datum`.
4. **`analyses/`**: avg-statistics, assess-avg-resources, assess-swl-resources; templates to
   `inputs/templates/`; stubs for planned workflows.
5. **`case-studies/`**: overtopping and habitat; dissolve JK/JO; notebook merge;
   `package_dashboard.py`; draft sync from final docx.
6. **Docs**: root README index with Mermaid graph; workflow READMEs; `data/README.md`;
   `docs/methods-index.md` + its test; `docs/plans/`; rewrite `.github/copilot-instructions.md`
   (repo-is-workflows opening; read-first list; Layout; rules on scripts, gates, methods
   index, deliverables, case-study separation; tracking policy; units/datum options;
   commands including running a workflow; drop stale paths and "Open items"); delete the
   audit appendix.
7. **Merge and release**: merge the PR, build the zip, `gh release create v1 ...`.

## 9. Working rules

- Strict TDD for new or changed behavior; use existing linters; Python 3.12 with `uv`
  (`uv run ruff check .`, `uv run mypy -p great_lakes`, `uv run pytest`; if `uv run` fails
  with "Failed to canonicalize script path", use `.venv\Scripts\python.exe -m ...`).
- `data/raw/` is read-only. Hand-edited files (batch worksheets, memos) are never overwritten
  by scripts. Do not relitigate decisions here or in `docs/adr/`; ask the owner if something
  is unclear or stale.
- Rely on `hydropattern`; generally useful fixes belong upstream, not here.
- Update docs in the same change as the code they describe.

## 10. Unresolved (ask the owner when reached)

- Where historical-level analyses live (`avg-statistics` or a separate folder): deferred.
- Whether to keep the older habitat summary docx and the `michiganhuron_avg.*` files.
- Whether a pass/fail gate for ARI curve invariants (monotonic, no NaN) is wanted.
- The "Green Bay, WI" location in the GLOSSARY came from the plan PDF file name.
- Local-only untracked tests (`tests/test_f*_*.py`, `test_musky_runs.py`,
  `test_pondweed_runs.py`) depend on the untracked habitat code; track them together with it.
