# Workflow restructure plan (`workflows/`)

Status: **implemented** on branch `restructure` (2026-11-24); see the commit history for the
move and the docs update.
Owner: John Kucharski (JK). Branch: `restructure`, created from `reorg` (already pushed).
Read first: `.github/copilot-instructions.md`, `GLOSSARY.md`, `README.md`,
`docs/data_pipelines.md`, `docs/methods-index.md`, `docs/plans/reorg_plan.md` (the previous
reorganization; its decisions still stand, this plan only moves and renames folders).

## 1. Goal and non-goals

Group the workflow folders into a `workflows/` tree with two families, **evaluation** and
**analysis**, and split the resources assessments into **single-resource** and
**batch-resources**. This is a **pure move**:

- No analytical result may change. No script behavior changes. Same CLI options, same
  output file names, same README.txt run records.
- Python identifiers keep their names (decided). `Layout.assess_product(kind)`,
  `Layout.avg_product`, `Layout.swl_product`, `Layout.avg_statistics_outputs`,
  `Layout.assess_template/assess_outputs/assess_data_dir` stay; only the paths they return
  change. Do not rename modules in `src/great_lakes/`.
- `data/` stays top-level and unchanged (never edit `data/raw/`).
- `case-studies/` stays top-level and unchanged, including its inside layout.
- Old ADRs (`docs/adr/`) and completed plans (`docs/plans/`) keep their old folder names as
  dated records. Do not rewrite them. Add a one-line pointer note to this plan (see 6).
- Do not delete the singular stub folders; they become the `single-resource/` folders.

## 2. Target layout and mapping

```
workflows/
  evaluation/                       applying resource rules to data
    resources-report/               stub (README only)
    avg/
      single-resource/              stub (README only)
      batch-resources/              implemented
    swl/
      single-resource/              stub (README + inputs/single_resource_swl.xlsx)
      batch-resources/              implemented
  analysis/                         producing / describing data products
    data-products/
      avg/                          implemented
      swl/                          implemented
    data-analysis/
      avg-statistics/               implemented
case-studies/long-tail-point/{overtopping,habitat}/   (unchanged, top-level)
data/                                                 (unchanged, top-level)
```

| Old path                         | New path                                         |
|----------------------------------|--------------------------------------------------|
| `analyses/assess-avg-resources/` | `workflows/evaluation/avg/batch-resources/`      |
| `analyses/assess-swl-resources/` | `workflows/evaluation/swl/batch-resources/`      |
| `analyses/assess-avg-resource/`  | `workflows/evaluation/avg/single-resource/`      |
| `analyses/assess-swl-resource/`  | `workflows/evaluation/swl/single-resource/`      |
| `analyses/report-resources/`     | `workflows/evaluation/resources-report/`         |
| `analyses/avg-statistics/`       | `workflows/analysis/data-analysis/avg-statistics/` |
| `data-products/avg/`             | `workflows/analysis/data-products/avg/`          |
| `data-products/swl/`             | `workflows/analysis/data-products/swl/`          |

The `analyses/` and `data-products/` top-level folders disappear. Use `git mv` so history
follows. Tracked file counts: `analyses/` 23, `data-products/` 16.

## 3. Vocabulary (add to GLOSSARY.md, use exactly)

- **Evaluation**: workflows that apply resource rules (hydropattern components, ARI
  thresholds) to data.
- **Analysis**: workflows that produce or describe the data products themselves (cleaning,
  completing, gates, statistics).
- **Single-resource** / **batch-resources**: evaluating one resource (stub, not built) vs
  many rows of a resources workbook (implemented as the old `assess-*-resources`).
- The existing term "workflow" is unchanged. Remove or reword any GLOSSARY text that calls
  the old folders `analyses/` or `data-products/` ("analyses" as a folder name; the word is
  still fine in prose).

Replace the folder naming rule in `.github/copilot-instructions.md` ("Folder names are
verb-noun, kebab-case, with no numeric or letter prefixes") with: kebab-case, no numeric or
letter prefixes, folders named for what they work on or produce. Update the Layout block and
the "Run a workflow" examples there too. Keep the avg vs swl separation rules untouched.

## 4. Inventory of things that must change

**Code (paths only), `src/great_lakes/paths.py`:**
`avg_product`, `swl_product`, `avg_statistics_outputs`, `assess_product(kind)` (becomes
`root/"workflows"/"evaluation"/kind/"batch-resources"`). Everything else derives from these
or from `data/`. No workflow script uses `parents[n]` or `__file__` to find the repo root
(verified), so deeper nesting does not break them; scripts get `--root` and use `Layout`.

**Docstrings/comments naming old paths (text only):** `avg_ari.py`, `batch/avg.py`,
`batch/run_readme.py`, `batch/runner.py`, `batch/template_avg.py`, `batch/template_swl.py`,
`cleaning/avg.py`, `cleaning/swl.py`, `swl/complete.py`, `swl/gates.py`.

**Tests (hardcoded roots):** `tests/test_paths.py`, `tests/test_analysis_scripts.py`
(`ANALYSES`, `assess-{kind}-resources`), `tests/test_case_study_scripts.py`,
`tests/test_data_product_scripts.py` (`PRODUCTS`), `tests/test_methods_index.py`
(`ROOTS = ("data-products", "analyses", "case-studies")` becomes
`("workflows", "case-studies")`), and a skip-reason string in `tests/test_batch_avg.py`.

**`.gitignore`** (ignores outputs by glob; deeper nesting needs new globs):
- `data-products/*/outputs/` -> `workflows/analysis/data-products/*/outputs/`
- `analyses/*/outputs/` -> `workflows/analysis/data-analysis/*/outputs/`,
  `workflows/evaluation/*/outputs/` (resources-report) and
  `workflows/evaluation/*/*/outputs/` (avg/swl single and batch).
- Verify with `git check-ignore -v` on one output path per workflow, and that tracked inputs
  stay tracked. Case-study globs do not change.

**Docs:** `README.md` (index and Mermaid graph), `.github/copilot-instructions.md`,
`GLOSSARY.md`, `docs/data_pipelines.md` (every run command), `docs/methods-index.md` (every
path in the table), `data/README.md`, `case-studies/long-tail-point/overtopping/README.md`,
and every workflow README and methods note (13 files inside the moved folders mention old
paths). Markdown relative links (`../`) inside moved files gain one or two levels;
26 links elsewhere point into the moved folders. `tests/test_methods_index.py` fails on dead
links, so it will catch misses.

**Not changed:** `docs/adr/*`, completed `docs/plans/*` (dated records),
`case-studies/*` internals, `CI` (`.github/workflows/ci.yml` has no folder references).

## 5. Gotchas

1. **Ignored local outputs do not move with `git mv`.** The owner has local, gitignored
   `outputs/` trees under `analyses/*/outputs/` and `data-products/*/outputs/`. After
   `git mv`, move them to the matching new folders (or ask the owner whether to regenerate).
   Never delete them without asking. Empty old folders may remain: ask before deleting.
2. `data-products/swl/outputs/` holds large gate and filled products used by tests and
   dashboards; confirm the new location is where `Layout` expects them.
3. Scratch `manual_tests/` (gitignored) must not exist when running the full suite; pytest
   collects its copies of the tests and fails with "import file mismatch". Run
   `pytest tests`.
4. The singular stubs and `report-resources/` have only READMEs (and one template xlsx);
   the README anatomy (Purpose, Status, Inputs, Run, Outputs, Methods, Assumptions &
   limitations) still applies, with paths fixed.
5. Windows paths: use backslashes in tool calls; docs keep forward slashes.

## 6. Implementation order (TDD)

1. Create branch: `git checkout -b restructure` from `reorg`.
2. Update the tests first (new expected paths in `test_paths.py`, `ROOTS`, the three
   script-smoke test files). Run them; they must fail for the right reason.
3. `git mv` per the mapping table; update `paths.py`; tests turn green.
4. Fix `.gitignore` globs and verify with `git check-ignore -v`.
5. Update docstrings, all docs, GLOSSARY (vocabulary in 3), copilot-instructions, README
   Mermaid graph, `docs/data_pipelines.md`, `docs/methods-index.md`.
6. Add a pointer line at the top of `docs/plans/reorg_plan.md` and under the existing "Path
   note" in each `docs/adr/*.md`: "Folders were later regrouped under `workflows/`, see
   `docs/plans/restructure_plan.md`." Do not rewrite the old paths.
7. Move the local ignored outputs (gotcha 1).
8. Sweep for leftovers (must return nothing outside the dated records):
   `git grep -n -E "data-products/|analyses/|assess-(avg|swl)-resource|report-resources"`
   excluding `docs/adr`, `docs/plans`, and this plan.
9. Run every moved script with `--help` by its new path (smoke tests cover the rest).
10. Gates: `.venv\Scripts\python.exe -m ruff check .`, `-m mypy -p great_lakes`,
    `-m pytest tests -n 8` (xdist is now a test dependency; about 5 min).
11. Optional equivalence check: run the avg and swl batch smoke workflows from the new
    paths and confirm outputs are unchanged versus `main`/`reorg`.
12. Ask the owner before every commit and push. Suggested commits: (1) tests + moves +
    `paths.py` + `.gitignore`; (2) docs, GLOSSARY, instructions.

## 7. Working rules for the implementing agent

- Ask (ask_user) before **every** commit and push. No Co-authored-by trailer. Commit with
  `git -c user.name=JohnRushKucharski -c user.email=johnkucharski@gmail.com commit -m "..."`.
- Push without an upstream: `git -c "credential.helper=!gh auth git-credential" push origin HEAD`.
- Sandbox: use `.venv\Scripts\python.exe -m ...` (not `uv run`; `uv sync` fails there, the
  owner runs it locally). Write file contents only with the edit/create tools, not
  `Set-Content` and friends (git mv and other programs are fine in PowerShell).
- Use GLOSSARY terms exactly; never conflate avg and swl; do only what is asked.
- If unsure whether something is stale or should be deleted: ASK.
- Report progress concisely; stop and show the owner anything that changes a result.

## 8. Resolved / open

Decided with the owner: `workflows/` wrapper (case-studies and data excluded); evaluation
vs analysis split as in 2; stubs become `single-resource/`; Python names unchanged; old ADRs
and plans keep old paths with a pointer note; new naming rule in 3; push `reorg` first and
implement in a new session on `restructure`. `docs/plans/` stays under `docs/` (repo-wide).
Future historical-level analyses will be created by the owner later under
`workflows/analysis/`.

Optional follow-up unrelated to this move: switch generated hydropattern `.toml` to the
ordered `[[components.X.characteristics]]` form to remove the 0.3.x compact-form warning.
