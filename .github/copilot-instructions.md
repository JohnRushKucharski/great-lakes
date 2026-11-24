# Copilot instructions: great-lakes

This repo is **not a software project**. It documents and makes reproducible a set of USACE
analyses (Great Lakes Framework Study, incl. Long Tail Point; Great Lakes Coastal Resiliency
Study) as clearly named **workflows**, built on the `hydropattern` package. The code in
`src/great_lakes/` only supports the workflows. The owner is the sole primary user;
colleagues at USACE also read the user docs.

Read first: `GLOSSARY.md` (domain glossary; use its terms exactly), `README.md` (index and
Mermaid graph), `docs/data_pipelines.md` (run order), `docs/methods-index.md`, `docs/adr/`
(decisions already made; don't relitigate), `docs/plans/` (plans; `reorg_plan.md` records the
reorganization decisions).

## Layout

```
README.md, GLOSSARY.md
data/                    raw/ (read-only), avg/, swl/{clean,complete}/ (+ figures/), README.md
workflows/evaluation/    applying resource rules to data:
                         {avg,swl}/batch-resources (implemented),
                         {avg,swl}/single-resource, resources-report (stub README only)
workflows/analysis/      producing/describing data products:
                         data-products/{avg,swl}, data-analysis/avg-statistics (implemented)
                         (each workflow: README, inputs/, scripts/, methods/, outputs/)
case-studies/long-tail-point/{overtopping,habitat}/
                         README, inputs/, scripts/, methods/, outputs/, deliverables/
docs/                    adr/, plans/, methods-index.md, data_pipelines.md (repo-wide only)
src/great_lakes/         shared library, import-only (no `__main__`, no `python -m` docs)
tests/                   all pytest
```

Folder names are kebab-case, with no numeric or letter prefixes, named for what they work on
or produce. Write "Long Tail
Point (LTP)" in prose; no `ltp_` prefix inside `case-studies/long-tail-point/`, only on files
that leave it (`docs/plans/ltp_*.md`).

## Data concepts

- **avg**: average (monthly) lake water levels. Processed through `hydropattern`.
- **swl** ("storm water level" in this repo, formerly "total water level"/`twl`): water
  levels incl. storm surge and wave set-up, as ARI frequency curves. NOT managed by
  `hydropattern`, though the analysis steps are similar. It excludes near-shore processes
  (run-up, overtopping). USACE often calls this "still water level" (also "SWL"), which is
  confusing because "still" can read as "average". Use "storm water level" / `swl`
  everywhere; mention the USACE term only once where a reader needs the mapping (see
  `GLOSSARY.md`). Never conflate avg and swl.
- Docs must state plainly what each dataset does and does not include.

## Units and datums

- Source data: meters, IGLD85. Only meters/feet and IGLD85/NAVD88 are in scope.
- Unit conversion (m <-> ft) and datum conversion (IGLD85 <-> NAVD88) are separate steps
  (`great_lakes.units`: `convert_units`, `convert_datum`). Do only what was asked: units
  only, datum only, or both. Name helpers and labels so it is obvious which was applied
  (e.g. `m_igld85_to_ft_NAVD88`); labels state both ("Water level (ft, NAVD88)").
- Scripts that plot take `--units {m,ft}` and `--datum {IGLD85,NAVD88}`, default ft, NAVD88.
  Tracked summary figures use the defaults only. Data files stay in meters, IGLD85.

## hydropattern relationship

- Rely on `hydropattern` where possible. Prefer `.toml` configs (reproducible); use its
  Python API only when `.toml` can't do the job.
- For every bug fix or feature, ask: is it generally useful? If yes, it belongs upstream in
  `hydropattern` (propose it, don't copy it here). Only case-study-specific logic lives in
  this repo. Same idea for `climate-canvas` (plotting dependency).
- Bumping the pinned `hydropattern` version is an owner decision, done one workflow at a time
  against saved baselines so existing results stay reproducible. The pin (`v0.3.3`) satisfies
  the habitat run scripts and notebooks, which need 0.3 or later.

## Commands (Python 3.12, uv)

```powershell
uv sync --group test --group dev
uv run ruff check .
uv run mypy -p great_lakes
uv run pytest
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest, mypy. All three must pass.
Sandbox note: if `uv run` fails ("Failed to canonicalize script path"), use
`.venv\Scripts\python.exe -m pytest` (likewise `-m ruff`, `-m mypy`).

**Run a workflow** by path from the repository root; its README lists the scripts and
options, for example:

```powershell
uv run python workflows/analysis/data-products/swl/scripts/complete.py
uv run python workflows/evaluation/swl/batch-resources/scripts/assess.py --resources my_run.xlsx
uv run python case-studies/long-tail-point/overtopping/scripts/make_figures.py
```

## Workflow rules

- **Anatomy.** Each workflow folder has `README.md` (headings in order: Purpose, Status,
  Inputs, Run, Outputs, Methods, Assumptions & limitations, Deliverables for case studies),
  `inputs/`, `scripts/`, `methods/`, `outputs/` (+ `deliverables/` for case studies).
- **Scripts** (`scripts/`) are thin typer apps; logic lives in `src/great_lakes/` (DRY). No
  required arguments, run by path, and every script takes `--root` (used by tests to run on a
  fixture tree). A script that writes to an `outputs/` folder also writes a `README.txt` run
  record there (timestamp, inputs, files written, stale files). One subprocess smoke test per
  workflow runs its scripts on small fixtures.
- **Gates vs method notes.** A pass/fail check is a **gate**: a script that exits 1 on failure.
  Fit quality or descriptive material is a **method note** in `methods/`.
- **Methods index.** `docs/methods-index.md` lists every file in a `methods/` folder, with
  type and status (`final` or `draft, incomplete`). A pytest fails on an unlisted file or a
  dead link, so add a row whenever you add a methods file. Plans live in `docs/plans/` and
  are not indexed.
- **Deliverables.** `deliverables/` holds final memos only. The hand-edited `.docx` is the
  master memo text; scripts never write to `deliverables/` or overwrite hand-edited files
  (memos, worksheets). Drafts and sync products go to `outputs/`.
- **Case-study separation.** Overtopping and habitat never share drafts, memos or scripts;
  only the library (e.g. `memo/to_docx.py`) is shared.
- **Resources worksheets** (`inputs/templates/`): v1 must keep working. Copy a template;
  never edit it in place.

## Tracking policy

- Tracked: `data/` (raw, products, summary figures), every `inputs/`, `deliverables/`,
  figures embedded in docs or memos, the overtopping `dashboard.html` and `manifest.js`, the
  habitat reliability tables.
- Gitignored: other `outputs/`, `__pycache__`, the dashboard zip (published as a GitHub Release
  asset, tag `v1`), `skills/` (local AI tooling only).
- Inputs needed to reproduce outputs are committed. When an input set is replaced by a
  near-identical update, replace/remove the stale one.
- `data/raw/` is read-only. Never edit it.
- Keep the scripts that produce outputs in the repo and keep them current; READMEs say how to
  run them to regenerate untracked outputs.
- Avoid clutter: update or replace old inputs/scripts rather than keeping parallel versions.
  If unsure whether something is stale, ASK the user.
- Don't commit generated artifacts or zips without asking.

## Development workflow

- TDD always: failing test first, then code. Add tests only for new/changed behavior.
- **Ask before every commit and every push.**
- Branch for big plans, new features, new workflows. Small changes and bug fixes may go on
  `main`.
- Update affected docs (`README.md`, workflow READMEs, `GLOSSARY.md`, `docs/`,
  `docs/methods-index.md`) in the same change.

## Code style

- Comments and docstrings: clear and CONCISE. Public functions get fuller docstrings;
  private/internal ones get one short line on what/why. No boilerplate parameter sections for
  self-explanatory args. Don't narrate obvious code.
- Ruff: line length 100, rules E/F/W/I (also covers workflow `scripts/`; notebooks are
  excluded). `build_dashboard.py` is exempt from E501.
