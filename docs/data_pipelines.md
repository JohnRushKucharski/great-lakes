# Great Lakes data pipeline audit

Audit date: 2026-07-31

This note audits the Great Lakes example workflow end to end:

```text
raw xlsx/xlsm
  -> clean lake-average csv / clean TWL xlsx
  -> filled TWL xlsx (7 in-hull scenarios)
  -> extrapolated TWL xlsx (5 out-of-hull scenarios)
  -> batch analysis outputs (AVG + TWL grids/plots)
  -> longtailpoint outputs
  -> manifest.js + dashboard.html
```

## Executive summary

**Overall:** the main numeric pipeline is internally consistent where I could verify it. The raw-to-clean transforms preserve sampled values, the TWL fill/extrapolation code matches ADR 0001, the 17-scenario coverage claim is true in the generated workbooks, ARI interpolation is linear in ARI-space with clamping, and the dashboard manifest matches underlying grid CSVs.

**Update (post-audit fixes applied):** the string-boolean parsing defect below has been fixed in code, and the test-coverage gaps for raw cleaning, template builders, and the known-scenario analysis script have been closed with new unit tests. See "12. Post-audit fixes" for details. The stale `longtailpoint\batch_twl.xlsx` workbook (Issue 2) was intentionally left as-is, per operator instruction.

**Originally flagged issue (now fixed):** the `batch_run_twl.py` config parser mis-parsed string booleans such as `"false"` as `True` (`batch_run_twl.py:63-67`, `616-629`), because `bool("false")` is `True` in Python. The shipped longtailpoint TWL workbooks use string booleans, so:

- `overwrite = "false"` was parsed as `True`;
- `batch_twl-nointerpolation.xlsx` would actually have run with `plot_interpolate=True`.

That was a real reproducibility / operator-expectation defect. The identical bug also existed in `batch_run_avg.py`'s copy of `_to_bool` and has been fixed there too. See section 12.

---

## 1. Pipeline map

| Stage | Inputs | Script(s) | Outputs |
|---|---|---|---|
| Raw AVG cleaning | `data\raw\lake_levels_all_scenarios_9jul2026.xlsx` | `data\raw\clean_lake_levels_all_scenarios.py` | `data\clean\{superior,michiganhuron,stclair,erie,ontario}_avg.csv` |
| Raw TWL cleaning | `data\raw\still_water_summary__22may2026.xlsm` | `data\raw\clean_still_water_summary.py` | `data\clean\{superior,michigan,huron,ontario}_twl.xlsx` |
| Fill / extrapolate TWL scenarios | clean TWL xlsx + clean AVG csv | `fillin_twl.py`, `common_twl.py` | `data\filled\*_twl.xlsx`, `data\extrapolated\*_twl.xlsx` |
| AVG batch analysis | clean AVG csv + workbook templates | `batch_run_avg.py`, `templates\build_avg_template.py` | hydropattern `.toml`, output folders, grid CSVs, PNGs, Excel outputs |
| TWL batch analysis | clean / extrapolated TWL xlsx + workbook templates | `batch_run_twl.py`, `templates\build_twl_template.py` | TWL grid CSVs + PNGs; equivalent-elevation and elevation-delta grids/plots when requested |
| Known-scenario side analysis | extrapolated TWL xlsx | `analyze_known_scenarios.py` | `data\analysis\known_scenario_directionality.csv` + summary xlsx |
| Dashboard build | completed TWL/AVG batch outputs | `build_dashboard.py` | `longtailpoint\manifest.js`, `dashboard.html` |

---

## 2. Raw -> clean stage

### 2.1 Lake-average time series (`*_avg.csv`)

**Code path**

- `clean_lake_levels_all_scenarios.py` reads only the five lake sheets in `LAKES` (`Superior`, `MichiganHuron`, `StClair`, `Erie`, `Ontario`) (`clean_lake_levels_all_scenarios.py:30-36`, `56-60`).
- It drops `month`, renames `Unnamed: 0` to `time`, and writes CSV (`:63-69`).
- Dates are string-formatted because the synthetic record extends beyond pandas' normal datetime64 range (`:64-67`).

**What enters / exits**

| Input sheet shape | Transform | Output shape / convention |
|---|---|---|
| Monthly synthetic scenario record with columns `Unnamed: 0`, 17 scenario columns `_0_0 ... _20_7`, and `month` | drop `month`; rename date column to `time`; preserve all 17 scenario columns unchanged | CSV with `time` + 17 scenario columns |

**Integrity evidence**

- Raw workbook sheet names include the expected five lake sheets plus non-pipeline sheets like `summary`, `stats_*`, `year_count`; the cleaner explicitly selects only the five lake sheets.
- Spot-checks against the cleaned CSVs matched exactly for all five lakes:

| Lake | Raw first `time` | Raw first `_0_0` | Clean first `_0_0` | `month` dropped? |
|---|---:|---:|---:|---|
| Superior | `1970-01-01` | `183.43` | `183.43` | yes |
| MichiganHuron | `1970-01-01` | `176.63` | `176.63` | yes |
| StClair | `1970-01-01` | `175.25` | `175.25` | yes |
| Erie | `1970-01-01` | `174.32` | `174.32` | yes |
| Ontario | `1970-01-01` | `74.59` | `74.59` | yes |

- Sampled clean CSV structure:
  - `superior_avg.csv`: 12,360 rows × 18 columns (`time` + 17 scenarios), `time_min=1970-01-01`, `time_max=2999-12-01`, `duplicate_times=0`, no NaNs in sampled columns.
  - `michiganhuron_avg.csv`: same row/column count and date span.
- 12,360 monthly rows matches a 1030-year synthetic record (`1970-2999`, inclusive).

**Judgment**

- **Correct sheet/column selection:** yes.
- **Scenario names preserved:** yes; the 17 `_precip_temp` columns are copied through unchanged.
- **Date range preservation:** yes.
- **Units:** preserved, but not re-labeled in the cleaner itself. The pipeline treats these values as meter-scale lake levels consistent with later IGLD85→NAVG88 conversion logic.

### 2.2 Still-water/TWL workbooks (`*_twl.xlsx`)

**Code path**

- `clean_still_water_summary.py` maps lake tags `sup`, `mich`, `hur`, `ont` to four output workbooks (`clean_still_water_summary.py:30-36`).
- Scenario mapping is explicit in `SCENARIOS` (`:48-54`):
  - `baseline -> baseline-_0_0`
  - `modnear -> nearterm-_5_1.5`
  - `modfuture_low -> moderate_low-_10_5`
  - `lowLL -> extreme_low-_0_7`
  - `highLL -> extreme_high-_20_5`
- The script skips the first two header rows and assigns a single standardized header `ID, lat, lon, 0.1 ... 1000` (`:82-90`), then drops rows with blank `ID` (`:96-99`).

**Integrity evidence**

- The raw workbook `summary` sheet reports the authoritative scenario deltas; sampled rows show:

| Raw scenario tag | dP | dT | Clean sheet name |
|---|---:|---:|---|
| `baseline` | 0 | 0 | `baseline-_0_0` |
| `modnear` | 5 | 1.5 | `nearterm-_5_1.5` |
| `modfuture_low` | 10 | 5 | `moderate_low-_10_5` |
| `highLL` | 20 | 5 | `extreme_high-_20_5` |
| `lowLL` | 0 | 7 | `extreme_low-_0_7` |

- Each clean TWL workbook has exactly those five sheets for all four lakes.
- Raw-vs-clean baseline spot-checks matched exactly:

| Lake | First ID | Raw first ARI 0.1 | Clean first ARI 0.1 | Row count match |
|---|---:|---:|---:|---|
| Superior | 1 | 182.55 | 182.55 | yes |
| Michigan | 27 | 175.18 | 175.18 | yes |
| Huron | 1 | 175.14 | 175.14 | yes |
| Ontario | 1 | 73.92 | 73.92 | yes |

**Judgment**

- **Correct raw sheets/columns selected:** yes, based on code and sampled value preservation.
- **Known-scenario relabeling:** yes, and it matches the raw workbook's own `summary` dP/dT definitions.
- **TWL lake coverage:** four lakes only (`superior`, `michigan`, `huron`, `ontario`); `stclair`/`erie` absence is intentional, not a silent drop.

---

## 3. Fill / extrapolate stage

### 3.1 In-hull fill

`fillin_twl.py` defines the full 17-scenario set in `ALL_SCENARIO_SUFFIXES` (`fillin_twl.py:49-55`) and classifies missing scenarios by Delaunay hull membership (`:90-111`).

The actual classification implied by the clean workbooks is:

- **Known (5):** `_0_0`, `_5_1.5`, `_10_5`, `_20_5`, `_0_7`
- **Filled / in-hull (7):** `_0_1.5`, `_0_3`, `_0_5`, `_5_3`, `_5_5`, `_10_3`, `_15_5`
- **Extrapolated / out-of-hull (5):** `_5_7`, `_10_7`, `_15_3`, `_15_7`, `_20_7`

### 3.2 Out-of-hull extrapolation

ADR 0001 says: choose the nearest resolved scenario on the same `temp_delta` row, then add `AVG(target) - AVG(anchor)` to every save-point/ARI cell.

The implementation matches that:

- same-row / nearest-precip anchor selection: `fillin_twl.py:191-213`
- additive `delta = avg_means[target] - avg_means[anchor]`: `:238-247`
- stage ordering guarantees filled scenarios can serve as anchors for extrapolation: `:347-369`
- Michigan and Huron both resolve to `michiganhuron_avg.csv` through `common_twl.TWL_LAKE_TO_AVG_LAKE` (`common_twl.py:36-41`, `88-96`)

**Integrity evidence**

#### Scenario coverage

I listed actual sheet names in all generated workbooks:

- every file in `data\filled\*_twl.xlsx` has **12** sheets:
  - 5 known + 7 `filled-*`
- every file in `data\extrapolated\*_twl.xlsx` has **17** sheets:
  - 5 known + 7 `filled-*` + 5 `extrapolated-*`

This is true for all four TWL lakes (`superior`, `michigan`, `huron`, `ontario`).

#### Manual recomputation of extrapolated cells

I manually recomputed two real output cells from the current data:

| Lake | Target scenario | Anchor | `AVG(target)` | `AVG(anchor)` | Delta | Anchor cell (first save point, ARI=0.1) | Expected | Actual |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Superior | `_15_3` | `_10_3` | 183.6187063 | 183.4021343 | +0.2165720 | 182.56 | 182.78 | 182.78 |
| Michigan | `_20_7` | `_0_7` | 176.5980761 | 174.3119312 | +2.2861448 | 172.70 | 174.99 | 174.99 |

The Superior case is especially important because `_10_3` is itself a **filled** anchor, exactly as ADR 0001 describes.

**Judgment**

- **ADR 0001 math implemented correctly:** yes.
- **Same-row anchor selection implemented correctly:** yes.
- **`filled-` vs `extrapolated-` prefixes:** yes.
- **Michigan-Huron shared AVG data used correctly:** yes; I found no code path attempting `michigan_avg.csv` or `huron_avg.csv`.

---

## 4. Batch analysis stages

### 4.1 Average-lake-level batch runs

`batch_run_avg.py` maps resource-sheet lake codes directly to clean CSVs (`batch_run_avg.py:31-39`, `100-102`). Michigan-Huron is explicitly one lake here (`michiganhuron_avg.csv`), which is consistent with the cleaned data and with longtailpoint's AVG workbook.

`run_batch()` generates one TOML + one hydropattern run per row (`batch_run_avg.py:671-724`).

**Integrity evidence**

- `longtailpoint\batch_avg.xlsx` uses `lake=michiganhuron` for its sampled rows, not `michigan` or `huron`.
- `data\analysis\avg\high\superior_10.png` and `...superior_10_interpolated.png` both showed sane titles/axes:
  - title: `Superior high-water ARI=10 (baseline avg=601.74 ft)`
  - x-axis: `precip_delta`
  - y-axis: `temp_delta`
  - colorbar: `lake level (ft)`

### 4.2 TWL batch runs and longtailpoint outputs

**Code path**

- ARI lookup is linear in ARI-space via `np.interp` (`batch_run_twl.py:78-110`).
- Reverse lookup for equivalent elevation is also linear in ARI-space (`:113-143`).
- Out-of-range thresholds clamp to the nearest endpoint with a warning (`:98-109`, `136-143`).
- Primary metric evaluation is scenario-sheet-by-scenario-sheet (`:637-660`).
- Equivalent elevation is computed in meters/IGLD85 internally, then converted to feet/NAVG88 only when writing elevation outputs (`:810-849`).

**Unit conversion evidence**

`common_twl.py:55-69` documents and implements a flat +0.44 ft offset after converting meters to feet. I checked the cited workbook directly:

| `longtail_waterlevel.xlsx` `Sheet2` | Value |
|---|---:|
| NAVG88 high | 587.00 ft |
| IGLD85 high | 586.56 ft |
| NAVG88 low | 582.00 ft |
| IGLD85 low | 581.56 ft |

That is exactly the +0.44 ft relationship the code uses. The conversion tests in `tests\test_common_twl.py` also assert those exact pairs.

**Integrity evidence**

- `batch_run_twl.py` converts only the **equivalent-elevation** and **elevation-delta** outputs to ft/NAVG88 (`:810-849`); the primary TWL metric remains in `metric_mode` units.
- Spot-checked plots looked label-consistent:
  - `data\analysis\twl\ontario_0.5.png`
  - `data\analysis\twl\ontario_0.5_interpolated.png`
  - `data\filled\img\michigan_20.png`
  - `data\extrapolated\img\michigan_20_interpolated.png`
- Example observed labels/titles:
  - `Ontario save point 6695 -- ARI=0.5 (baseline average lake level=245.64 ft)`
  - colorbar `TWL (ft)`
  - interpolated/non-interpolated variants differ visually in the expected way (sparse blocks vs filled surface).

**Judgment**

- **ARI interpolation is genuinely linear-in-ARI-space:** yes.
- **Clamping at 0.1 / 1000 instead of extrapolating:** yes.
- **Meters IGLD85 -> feet NAVG88 conversion applied exactly once, at final elevation outputs only:** yes, in code and in sampled outputs.

---

## 5. Dashboard stage

`build_dashboard.py` expects six file kinds (`build_dashboard.py:43-50`) and uses `None` vs fail-loud vs soft-missing semantics intentionally (`:184-205`). Magnitudes and equivalent-elevation-basis labels are converted for display in ft/NAVG88 (`:74-93`).

**Integrity evidence**

- `longtailpoint\manifest.js` contains both TWL and AVG entries:
  - `twl`: 264 entries
  - `avg`: 11 entries
- First manifest entry:
  - `qualified_name = longtail_17877_base_1968`
  - grid path `batch_twl_output/baseline/longtail_17877_base_1968_grid.csv`
  - manifest grid value at `(temp=0.0, precip=0.0)` = `1.0010005001667084`
  - CSV value at the same cell = `1.0010005001667084`
- `dashboard.html` uses the expected user-facing labels:
  - `Analysis type`
  - `Magnitude (ft, NAVG88)`
  - `Runup allowance`
  - `Equivalent-elevation basis`

**Judgment**

- **Dashboard reads the same grid CSVs that the batch runs produced:** yes, based on direct manifest-to-CSV spot check.
- **Dashboard labels/units:** consistent with `CONTEXT.md` and the plot-generation code.

---

## 6. Critical questions: direct answers

| Question | Answer |
|---|---|
| Raw->clean: correct raw sheet/column selected, no silent mislabeling? | **Yes, with one caveat.** The cleaners select the intended sheets/columns and preserve sampled numeric values exactly. Scenario relabeling in TWL cleaning matches the raw workbook `summary` dP/dT definitions. Caveat: the AVG cleaner itself does not add an explicit units label; units are inferred from surrounding docs/value ranges. |
| Is Michigan-Huron treated as one connected lake everywhere it should be? | **Yes in the audited code paths.** AVG cleaning emits `michiganhuron_avg.csv`; `batch_run_avg.py` uses `michiganhuron`; `common_twl.py` maps both `michigan` and `huron` TWL workbooks to the shared AVG CSV for extrapolation. |
| Does fill/extrapolation match ADR 0001 exactly? | **Yes.** Same-row nearest-precip anchor selection and additive `AVG(target)-AVG(anchor)` shifting are implemented as described, and real output cells matched manual recomputation. |
| Is `17 = 5 known + 7 filled + 5 extrapolated` true in actual files? | **Yes for all 4 TWL lakes.** |
| Are unit conversions applied exactly once, in the correct direction, only at final output? | **Yes for equivalent-elevation / elevation-delta outputs.** Primary TWL metrics are not elevation units and are not converted. |
| Do plot/dashboard labels match documented conventions? | **Mostly yes; I found no mislabeled sampled PNGs or dashboard controls.** |
| Is ARI interpolation truly linear-in-ARI-space with clamping? | **Yes.** Code uses `np.interp` directly on ARI values and clamps to endpoint ARIs/levels with warnings. |
| Which stages lack test coverage? | **Raw cleaning scripts, `analyze_known_scenarios.py`, template builders, and image-regression checks have no direct tests.** `batch_run_twl.py` also lacks a real-workbook config regression for string booleans, which allowed a real bug to slip through. |

---

## 7. Flagged issues

### Issue 1 — real config boolean parsing defect in `batch_run_twl.py` — **FIXED**

**Evidence (original bug)**

- `_to_bool()` returned `bool(value)` for any nonblank value (`batch_run_twl.py:63-67`, pre-fix).
- `read_config_sheet()` routes `overwrite`, `plot_interpolate`, and `fillin` through `_to_bool()` (`batch_run_twl.py:616-629`).
- The identical `_to_bool()` body was duplicated in `batch_run_avg.py:105-118` (pre-fix), routing `excel`, `overwrite`, `plot_enabled`, `plot_interpolate` through the same defect.
- The shipped longtailpoint TWL workbooks store booleans as strings:
  - `batch_twl-interpolation_baseline.xlsx`: `overwrite='false'`, `plot_interpolate='true'`, `fillin='true'`
  - `batch_twl-interpolation_586ft.xlsx`: same pattern
  - `batch_twl-nointerpolation.xlsx`: `overwrite='false'`, `plot_interpolate='false'`
- Pre-fix parser result: `batch_twl-interpolation_baseline.xlsx` parsed `overwrite=True`; `batch_twl-nointerpolation.xlsx` parsed `plot_interpolate=True`.

**Fix applied**

`_to_bool()` in both `batch_run_twl.py` and `batch_run_avg.py` now special-cases `str` inputs: `"true"/"1"/"yes"` (case-insensitive, trimmed) -> `True`, `"false"/"0"/"no"` -> `False`, anything else raises `ValueError`. Non-string inputs still fall back to plain `bool(value)` (unchanged behavior for real Excel booleans / numeric 0/1). Verified against the actual shipped workbook cell values (`overwrite='false'` in `batch_twl-nointerpolation.xlsx`, confirmed via `openpyxl` read) now parses to `False` as intended.

Regression tests: `tests\test_batch_run_twl.py::test_to_bool` / `test_to_bool_rejects_unparsable_string`, `tests\test_batch_run_avg.py::test_to_bool` / `test_to_bool_rejects_unparsable_string` (new — `batch_run_avg.py` previously had no `_to_bool` test at all).

**Severity:** was high for reproducibility / operational integrity; now fixed and covered.

### Issue 2 — `longtailpoint\batch_twl.xlsx` is currently unrunnable as shipped — **left as-is**

**Evidence**

- Workbook config contains `metric_mode = "return period"` (with a space).
- `batch_run_twl.read_config_sheet()` only accepts `portion`, `percentage`, or `return_period` (`batch_run_twl.py:600-604`).
- Reading that workbook raises `SheetValidationError`.

**Impact**

- The adjacent workbook is stale or invalid and cannot be rerun without manual correction.

**Severity:** medium. I did **not** find evidence that the current dashboard manifest depends on this particular workbook. **Disposition:** left unfixed intentionally (operator instruction) — the workbook itself is data, not pipeline code, and correcting its `metric_mode` cell was explicitly out of scope for this pass.

---

## 8. PNG output spot checks

I did not inspect all 558 PNGs. I sampled representative files across the four PNG-producing areas:

| Area | Sampled file(s) | Observation |
|---|---|---|
| AVG analysis | `data\analysis\avg\high\superior_10.png`, `...superior_10_interpolated.png` | Titles/axes/colorbar sane; interpolated variant visually smoother than blocky base plot. |
| TWL analysis | `data\analysis\twl\ontario_0.5.png`, `...ontario_0.5_interpolated.png` | Titles, `TWL (ft)` colorbar, and save-point naming looked coherent; interpolation visually present only in `_interpolated` variant. |
| Filled-scenario visualizations | `data\filled\img\michigan_20.png` | Lake name, save point, ARI, and TWL units consistent with filename/context. |
| Extrapolated-scenario visualizations | `data\extrapolated\img\michigan_20_interpolated.png` | Same labeling convention; no obvious empty/bugged axes. |

No sampled plot showed a lake-name swap, unit mismatch, or empty rendering.

---

## 9. Test coverage

### 9.1 Executed test suite

Command run (original audit pass):

```powershell
uv run pytest tests\test_common_twl.py tests\test_fillin_twl.py tests\test_batch_run_avg.py tests\test_batch_run_twl.py tests\test_build_dashboard.py tests\test_scenario_grid.py tests\test_twl_batch_run.py -v
```

Result (original audit pass, before fixes):

- **328 passed**
- **0 failed**
- **10 warnings**
- runtime: **24.86s**

Command run (post-fix, including new test files, full `tests\` suite):

```powershell
uv run pytest tests\ -q
```

Result: **685 passed**, plus 2 pre-existing failures in `tests\test_stable_request_shape.py` traced to an unrelated, already-in-progress working-tree change in `hydropattern/parsers.py`/`patterns.py` (a `"frequency between"` form, unrelated to Great Lakes) — confirmed via `git stash` that these 2 failures exist independently of every change in this document and were not introduced by the Great Lakes fixes.

### 9.2 Coverage map by pipeline stage (post-fix)

| Pipeline stage | Covered by | Coverage quality | Gaps / comments |
|---|---|---|---|
| Raw AVG cleaning (`clean_lake_levels_all_scenarios.py`) | `tests\test_clean_raw_scripts.py` (new) | Good | Covers the `LAKES` sheet-name mapping and the extracted `clean_lake_frame()` transform (month drop, `time` rename, string-date formatting past pandas' datetime64 range). |
| Raw TWL cleaning (`clean_still_water_summary.py`) | `tests\test_clean_raw_scripts.py` (new) | Good | Covers `source_sheet_name()`, a regression test locking the `SCENARIOS` precip/temp mapping (guards the exact historical lowLL/highLL swap bug called out in the script's own comment), `NEW_HEADER`, and the extracted `clean_scenario_frame()` blank-ID-row transform. |
| Shared unit conversion / Michigan-Huron AVG mapping (`common_twl.py`) | `tests\test_common_twl.py` | Good | Strong low-level checks, including the 0.44 ft datum offset and shared Michigan/Huron AVG file mapping. |
| Scenario-grid core | `tests\test_scenario_grid.py` | Good | Covers parsing and sparse-grid behavior. |
| Fill / extrapolate TWL (`fillin_twl.py`) | `tests\test_fillin_twl.py` | Strong | Covers hull split, barycentric weights, anchor selection, extrapolation math, workbook writing, and CLI orchestration. |
| AVG batch runner (`batch_run_avg.py`) | `tests\test_batch_run_avg.py` | Strong | Includes parser tests, an end-to-end run against real AVG CSVs, and (new) `_to_bool` regression tests for string booleans. |
| TWL batch runner (`batch_run_twl.py`) | `tests\test_batch_run_twl.py` | Strong | Good synthetic coverage of ARI interpolation, equivalent elevation, and output writing, plus (new) `_to_bool` regression tests covering `"true"`/`"false"`/`"1"`/`"0"`/`"yes"`/`"no"` strings and rejection of unparsable strings — the exact case that let Issue 1 ship. |
| Dashboard (`build_dashboard.py`) | `tests\test_build_dashboard.py` | Strong | Good synthetic manifest/html tests. No regression that the checked-in `longtailpoint\manifest.js` still matches real files (still a gap; not addressed in this pass). |
| Known-scenario side analysis (`analyze_known_scenarios.py`) | `tests\test_analyze_known_scenarios.py` (new) | Good | Covers `sheet_name_for_suffix()` (happy path + both error branches), `summarize()` (stat correctness + sign-share logic on a hand-computable synthetic input), and `analyze_lake()` end-to-end against a synthetic 4-sheet workbook with hand-checked precip/temp deltas. |
| Template builders (`templates\build_avg_template.py`, `templates\build_twl_template.py`) | `tests\test_template_builders.py` (new) | Good | Covers header/example-row contents and config-sheet option/default/comment fidelity for both templates. |
| PNG rendering correctness | **None** | **None** | Still no image-regression tests; visual issues would still be caught only manually. Not addressed in this pass (no lightweight image-regression tool was already in the project's dependency set, and adding one was judged out of scope for this fix pass). |

### 9.3 Notable meta-gap — resolved

`tests\test_twl_batch_run.py` was an empty 0-byte file contributing no coverage. It has been deleted; its intended subject (`batch_run_twl.py`) is fully covered by `tests\test_batch_run_twl.py`.

---

## 10. Bottom line

For the **current numeric data products**, I found good evidence that:

- raw values survive cleaning correctly,
- scenario naming is consistent,
- Michigan-Huron sharing is implemented correctly,
- fill/extrapolation matches the ADR and sampled outputs,
- scenario coverage is complete,
- unit conversion logic matches the cited datum table,
- and the dashboard manifest reflects the underlying grid CSVs.

The main integrity concern was **not** the interpolation math; it was the **TWL/AVG workbook config parsing bug for string booleans** — now fixed in both `batch_run_twl.py` and `batch_run_avg.py`, with regression tests. One stale invalid workbook (`longtailpoint\batch_twl.xlsx`) remains, left as-is by operator instruction. See section 12 for the full list of changes made after the initial audit.

---

## 12. Post-audit fixes (this pass)

Applied after the initial audit above, per explicit operator instruction:

1. **Fixed** the string-boolean parsing bug (Issue 1) in both `batch_run_twl.py` and `batch_run_avg.py`. `_to_bool()` now parses `"true"/"1"/"yes"` -> `True` and `"false"/"0"/"no"` -> `False` (case-insensitive, whitespace-trimmed) for string cells, and raises `ValueError` on an unrecognized string, instead of falling through to Python's `bool(str)` truthiness. Non-string values (real Excel booleans, `0`/`1`) are unaffected.
2. **Deleted** `tests\test_twl_batch_run.py` (empty, 0 bytes, no coverage contributed).
3. **Added tests** for every pipeline stage the audit flagged as having zero coverage:
   - `tests\test_clean_raw_scripts.py` — raw AVG/TWL cleaning scripts. Required a small, behavior-preserving refactor: `clean_lake_frame()` was extracted from `clean_lake_levels_all_scenarios.py`'s `main()`, and `clean_scenario_frame()` was extracted from `clean_still_water_summary.py`'s `main()`, so each transform could be unit-tested against a synthetic in-memory DataFrame without touching the real (large) source workbooks. `main()`'s file-I/O behavior is otherwise unchanged.
   - `tests\test_template_builders.py` — `templates\build_avg_template.py` / `build_twl_template.py`. No production refactor needed; both already exposed a `build_template(path)` function.
   - `tests\test_analyze_known_scenarios.py` — `analyze_known_scenarios.py`. No production refactor needed; loaded the same way the script would run standalone (its own directory temporarily added to `sys.path`, matching its existing bare `import common_twl` / `from fillin_twl import ...` style).
4. **Left unchanged** (per explicit instruction): the stale `longtailpoint\batch_twl.xlsx` workbook (Issue 2) and PNG/image-regression coverage.

Issue 2 (stale `longtailpoint\batch_twl.xlsx`) and PNG/image-regression testing remain open items for a future pass.

