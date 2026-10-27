# Copilot instructions: great-lakes

Case-study repo (USACE) built on the `hydropattern` package. Supports the Great Lakes
Framework Study (incl. longtailpoint) and the Great Lakes Coastal Resiliency Study.
Owner is the sole primary user; colleagues at USACE also read the user docs.

Read first: `CONTEXT.md` (domain glossary, use its terms exactly), `README.md`,
`docs/data_pipelines.md`, `docs/adr/` (decisions already made; don't relitigate).

## Data concepts

- **avg**: average (monthly) lake water levels. Processed through `hydropattern`.
- **swl** ("storm water level" in this repo, formerly "total water level"/`twl`):
  water levels incl. storm surge and wave
  set-up, as ARI frequency curves. NOT managed by `hydropattern`, though the analysis
  steps are similar. It excludes near-shore processes (run-up, overtopping).
  USACE often calls this "still water level" (also "SWL") -- confusing because "still"
  can read as "average". Use "storm water level" / `swl` everywhere; mention the USACE
  term only once where a reader needs the mapping (see `CONTEXT.md`). Never conflate
  avg and swl.
- Docs must state plainly what each dataset does and does not include.

## Units and datums

- Source data: meters, IGLD85. Only meters/feet and IGLD85/NAVD88 are in scope.
- Unit conversion (m <-> ft) and datum conversion (IGLD85 <-> NAVD88) are separate steps.
  Do only what was asked: units only, datum only, or both. Name helpers and labels so it
  is obvious which was applied (e.g. `m_igld85_to_ft_NAVD88`).

## hydropattern relationship

- Rely on `hydropattern` where possible. Prefer `.toml` configs (reproducible); use its
  Python API only when `.toml` can't do the job.
- For every bug fix or feature, ask: is it generally useful? If yes, it belongs upstream
  in `hydropattern` (propose it, don't copy it here). Only case-study-specific logic
  lives in this repo. Same idea for `climate-canvas` (plotting dependency).

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

## Workflow

- TDD always: failing test first, then code. Add tests only for new/changed behavior.
- **Ask before every commit and every push.**
- Branch for big plans, new features, new workflows. Small changes and bug fixes may go
  on `main`.
- Update affected docs (`README.md`, `CONTEXT.md`, `docs/`) in the same change.

## Inputs, outputs, scripts

- `data/raw/` is read-only. Never edit it.
- Inputs needed to reproduce outputs are committed and tracked. When an input set is
  replaced by a near-identical update, replace/remove the stale one.
- Keep the scripts that produce outputs in the repo and keep them current. User docs
  must say how to run them to regenerate untracked outputs.
- Avoid clutter: update or replace old inputs/scripts rather than keeping parallel
  versions. If unsure whether something is stale, ASK the user.
- Don't commit generated artifacts or zips without asking (e.g. `longtailpoint.zip`).

## Code style

- Comments and docstrings: clear and CONCISE. Public functions get fuller docstrings;
  private/internal ones get one short line on what/why. No boilerplate parameter
  sections for self-explanatory args. Don't narrate obvious code.
- Ruff: line length 100, rules E/F/W/I. `build_dashboard.py` is exempt from E501.

## Open items

- None.
