# Plan: Long Tail Point (LTP) storm water level memo

Status: phases 1-6 complete (numbers frozen; main memo and Appendices A-B drafted in
`docs/longtailpoint_memo_draft.md`, concision pass and captions applied with user direction).
Next: phase 7 (assembly). This file is the source
of truth for the report. Terms follow `CONTEXT.md` exactly. Prose may rest only on facts
recorded here or in the approved draft.

## 1. Deliverable

- Memo-style report on the LTP storm water level (SWL) analysis, for the project/design team
  (non-programmers). Technical reviewers are secondary. Do not describe software, only how to
  use outputs (dashboard steps go in Appendix A).
- Format: Word `.docx` plus PDF. Memo header (TO/FROM/DATE/SUBJECT) and author are placeholders.
- Length: 2 pp main text + 1 pp Appendix A (dashboard) + 1 pp Appendix B (caveats). Figures do
  not count toward the limit. Hard max 3 pp main text; total text under 5 pp.
- Units: ft NAVD88 (source data are m, IGLD85; IGLD85_ft = NAVD88_ft - 0.44). Say "storm water
  level (SWL)"; mention the USACE term "still water level" once. Never conflate avg and SWL.

## 2. Approved facts

### Project context
- LTP is a sand spit on the Lake Michigan shoreline near Green Bay. It is itself habitat and
  protects degraded Dead Horse Bay habitat. Overtopping creates breaches.
- The team is evaluating nourishment designs (elevations and geometries). Material comes from
  local, occasionally dredged sites. The case study evaluates resilience under future
  lake-level scenarios driven by temperature and precipitation change.
- Eliminating breaches is neither possible nor natural. Target: overtopped once or less per ~15
  years (less preferable). 15 yr roughly aligns with dredging cycles, typical nourishment design
  life, and natural storm/high-water cycles; it is a general benchmark, not exact.
- Overtopping is assumed to lead to breach; erosion/breach is not modeled (out of scope). SWL
  excludes runup/overtopping, so assumed runup allowances are added.
- A 15-yr ARI threshold is about a 1/15 annual exceedance probability. It is NOT a guaranteed
  interval and NOT a breach rate.

### Design alternatives
- Top-of-dune elevations 584 ft and 586 ft NAVD88, mainly over a ~2,000-ft non-exclusive focus
  reach (project length extends beyond it).
- The 140,000 yd3 dredged-material constraint is approximate and not binding at these elevations
  given very rough conceptual geometries. Do not show geometries or volumes.
- Conditional guidance only; no single preferred elevation (cost, habitat, and engineering
  tradeoffs lie outside this analysis). Describe which elevation is most robust across scenario
  ranges, focusing on the 1.5 C and 3 C scenarios.
- Robustness rule: compare 584/586 against the 15-yr threshold across 1.5 C and 3 C scenarios;
  report scenario coverage and worst case by runup allowance. No probability weights.
- Runup: +2 ft central illustration; sensitivity at 0, +2, +2.5, +3 ft (assumed allowances).

### Scenarios
- Main report: baseline, 1.5 C, 3 C. 5 C / 7 C only as longer-term context or dashboard detail
  (nearer-term nourishment cycles are 10-20 yr).
- Naming `_precip%_tempC`. Known (modeled SWL): `_0_0`, `_5_1.5`, `_10_5`, `_20_5`
  (extreme_high), `_0_7` (extreme_low). Scenario IDs `extreme_low-_0_7`, `extreme_high-_20_5`.
- 1.5 C row: `_5_1.5` known, `_0_1.5` interpolated. 3 C row: none known; `_0_3`, `_5_3`, `_10_3`
  interpolated; `_15_3` extrapolated.
- Interpolated: `_0_1.5`, `_0_3`, `_0_5`, `_5_3`, `_5_5`, `_10_3`, `_15_5`. Extrapolated: `_15_3`,
  `_5_7`, `_10_7`, `_15_7`, `_20_7`. `_15_3` anchors to `_10_3`, itself interpolated (error
  compounds).
- `_15_3` (+3 C / +15% precip) = "upper-end stress case within the project scenario set (at the
  more extreme end of the range for that warming level, but still inside the range of
  projections)", with lower confidence because it is extrapolated. Do not claim it exceeds all
  published projections. Show visually flagged; stress case, not sole basis for advice.
- Marking in figures: thin black outline = modeled; `*` = interpolated; `**` = extrapolated;
  small, unobtrusive, explained in caption.

### Climate context
- Observed: recent decades warmer/wetter. Cite GLISA, *Summary of Climate Change in the Great
  Lakes Region* (Oct 2024): 1951-2023 regional avg annual air temperature +2.6 F (1.4 C), annual
  precipitation +14%; NOAA NCEI GHCN-D; regional, not local. Primary studies preferred but not
  verified beyond GLISA. Yang et al. 2023 (GRL 50, 10.1029/2022GL100682) is about moisture
  sources, not direct proof of a precipitation increase; do not cite it for that.
- More precipitation can yield higher, lower, or similar lake levels depending on the balance
  with evaporation.

### Data provenance
- Both datasets made under the EPA-funded Great Lakes Framework Study (citation placeholder).
- AVG: synthetic temperature/precipitation records (1,030 yr per scenario, 1970-2999) run through
  the Great Lakes Net Basin Supply model, the Large Lake Thermodynamic Model, and operations
  models -> synthetic monthly lake levels for 31 scenarios; 17 carried forward.
- SWL: surge and wave setup evaluated under 5 of the 17 scenarios (baseline, nearer-term
  moderate, moderate-low, extreme high and low lake level); produced by USACE ERDC Coastal and
  Hydraulics Laboratory (citation placeholder).
- Source files: `data/raw/lake_levels_all_scenarios_9jul2026.xlsx`,
  `data/raw/still_water_summary__22may2026.xlsm` (both present; `data/raw/` remains read-only).
- Phase 2 inventory: relevant cleaned inputs already exist; no regeneration needed.
  `data/clean/michiganhuron_avg.csv` has 12,360 monthly rows (1970-2999) and 17 scenario
  columns. `data/clean/michigan_swl.xlsx` has 5 known-scenario sheets, each with 19,517
  save points.
- Save points: IDs 1968, 4997, and 4999 confirmed in all five Michigan SWL sheets in the raw
  source workbook. Focus on 4999 (nearest the focus area); the three give very similar results,
  so say so. The `lat`/`lon` metadata in `longtailpoint/batch_swl-longtail.xlsx` for 1968 and
  4997 do not match those IDs' Michigan SWL coordinates; explicit `save_point_id` takes
  precedence over coordinates, so current lookup resolves by ID. Locator map is a placeholder
  supplied by the user.

### Count examples (Poisson, approved)
- Over 15 yr, label "threshold-exceedance / overtopping-proxy years", never breaches.
  Poisson lambda=1: P(N>0)=63.2%, P(N>2)=8.0%, P(N>3)=1.9%. Matches
  `batch_run_swl.exceedance_probability` (p = 1 - exp(-1/ARI)). Binomial p=1/15 (64.47 / 7.38 /
  1.49%) is superseded. Both assume independence and constant rate.
- State that AVG data show year-to-year persistence, so exceedances cluster.
- Note: `CONTEXT.md` defines ARI as 1/p; code uses the Poisson form (6.45% vs 6.67% at ARI 15).

### Reference values (SP 4999, 15-yr ARI, baseline runup, ft NAVD88)
`_0_0` 583.7; `_5_1.5` 583.8; `_0_1.5` 582.2; `_0_3` 580.8; `_5_3` 582.4; `_10_3` 584.2;
`_15_3` 586.0; `_15_5` 584.0; `_20_5` 585.9; `_0_7` 576.9; `_20_7` 584.4. The +2 ft runup version
adds 2 ft to every cell. Generator: `longtailpoint/presentation/make_presentation_figure.py`
(args: save_point_id ari out_stem [offset_ft]). Existing figures:
`longtailpoint/presentation/4999_ari15_elevation.png/.csv`, `4999_ari15_p2d00runup.png/.csv`.

## 3. Main memo outline

1. Purpose and bottom line (~4 sentences).
2. Project context. F1 locator map (placeholder).
3. Why this analysis and the 15-yr benchmark.
4. Inputs: AVG (17 scenarios), SWL (5 modeled), units, assumed runup allowances. F2.
5. Results: F4, T1, F3. Poisson examples stay in prose (no Table 2).
6. Options for design decisions:
   - Conditional guidance on 584 vs 586 ft robustness across 1.5 C and 3 C scenarios.
   - Adaptive options, flagged as suggestions for team review: build robustness in near-term
     increments so more extreme, less near-term scenarios can be accommodated later if
     monitoring suggests they are becoming more likely on the near-term horizon (relative to
     monitoring/decision time). Include monitoring triggers and decision timing.
7. Caveats summary: all six, one line each.

Figure-reading guidance (axes, colors, markings, ft NAVD88, indicative values) lives in the F2
and F4 captions, not a separate section. Prose names scenarios as warming/precipitation change
(e.g. "3 C/+15%"); `_precip_temp` codes stay in code, data, and figures only.

## 4. Figures and tables

| ID | Content | Source / status |
|----|---------|-----------------|
| F1 | Locator map | User supplies later (placeholder) |
| F2 | 17-scenario grid, AVG change vs baseline, modeled/interpolated/extrapolated marks, highlight baseline/1.5 C/3 C | New |
| F3 | Panel A: ~100-yr timeline strip; dots = "high years" (top 1-in-15 of that scenario's record); row 1 actual (clustered), row 2 shuffled/independent. Panel B: share of 15-yr windows with 0/1/2/3+ high years, actual vs independent (Poisson). Caption gives lag-1 correlation r. Statistic = annual maximum monthly AVG level. Scenarios: baseline + lowest/highest-AVG (relative to baseline whole-record mean) within the 1.5 C and 3 C sets; if persistence differs between high/low show both, else show higher-AVG case per warming level. Caption: AVG proxy, not SWL. | New; inputs `data/clean/michiganhuron_avg.csv` (gitignored, regenerable) |
| F4 | Main result: 15-yr ARI elevation surface, SP 4999, +2 ft runup, 584/586 overlay, marks | Revise `make_presentation_figure.py` output |
| T1 | 584 vs 586 x runup 0/2/2.5/3 x 1.5 C/3 C scenarios (coverage + worst case) | New |
| T2 | Poisson examples | Dropped from memo; numbers in §4 prose (CSV still generated) |
| A-A | Annotated dashboard screenshot(s) | User supplies / later |
| B-1 | SWL~AVG regression with prediction intervals | New (analysis E) |

## 5. Appendices

**Appendix A (dashboard, 1 pp).** Plain-language steps: open `longtailpoint/dashboard.html`
(zero install, double-click; manifest in `manifest.js`), find SP 4999, plot vs grid, A/B
compare, reset filters. Controls: Analysis (Return Interval / Equivalent Elevation / Elevation
Delta / Threshold ARI Elevation), Form (Plot/Grid), Save point, Elevation (NAVD88 ft), Runup
(ft), Compare toggle, initial Filter by (Elevation / Baseline ARI). No software internals.
Verified dashboard facts (phase 6): manifest has SWL only (Water Level Type picker hidden);
SPs 1968/4997/4999; elevations 582-587 ft by 0.5; runup 0/2/2.5/3. Threshold ARI Elevation
hides the Runup and Elevation pickers (no runup; user adds it), so the +2 ft runup check uses
Return Interval (ARI at which SWL + runup reaches the crest). SP 4999 Return Interval grids
match T1 (586 ft/+2: 1.5 C ~50 and ~20 yr, 3 C 2 of 4; 584 ft/+2: 0 of 2, 1 of 4).
Equivalent Elevation/Elevation Delta are SWL relative to (elevation - runup). ARI capped
0.1 to ~1,000 yr. Dashboard plots do not mark modeled/interpolated/extrapolated cells.

**Appendix B (caveats, 1 pp).** Each item: (a) slight expansion, (b) why defensible/decision-
useful, (c) how it could affect a decision. All six are also flagged in the main memo.
1. Runup excluded from SWL.
2. Overtopping process not modeled.
3. Overtopping is not breach.
4. Poisson counts ignore the persistence seen in AVG.
5. Extrapolation assumptions (row-shift, same-dT waves constant; ADR 0001).
6. Interpolation across the sparse SWL matrix (5 of 17 modeled; none at 3 C).
Optional additions: scenarios are not probability-weighted; 15-yr ARI is a benchmark.

## 6. Statistical evaluation (new analysis script)

Appendix quantitative, main memo qualitative. Indicative ranges, no guarantees.
- **E:** per ARI (primary 15, SP 4999), regress SWL on AVG over the 5 known scenarios. Report
  slope (~1 expected under row-shift), residual SD, and 95% prediction intervals at each
  interpolated/extrapolated scenario's AVG. n=5 -> 3 df, t~3.18, so intervals are wide. Check
  whether target AVG is inside or outside the known AVG range (leverage). Check residuals vs dT.
  Express error in ft against the 2-ft gap between 584 and 586 designs (<= ~0.5 ft = robust).
- **C:** leave-one-out row-shift: predict `_20_5` from `_10_5` + dAVG and vice versa. Only true
  out-of-sample test; `_0_0` and `_0_7` have no same-row anchor.
- **B:** leave-one-out interpolation: only `_5_1.5` and `_10_5` are interior to the hull of the
  other four, so only 2 valid tests.
- Dropped: method disagreement (D); A folded into E.
- Weaknesses to state: n=5; known scenarios are not random; the 3 save points are ~one sample;
  ARIs are correlated; SWL-AVG is not pure waves (includes the lake-level variability tail,
  which varies by scenario; ADR 0001 ignores this); interpolated values are convex combinations
  of known values so their variance cannot validate accuracy; extrapolated cells have no
  bounded comparison (error compounds for `_15_3`). Report residual SD in ft and slope;
  correlation alone misleads.

## 7. Phases

1. Persist plan (this file) — complete.
2. Data inventory — complete; cleaned inputs already present, no regeneration needed.
3. Analyses, test-first — generated; review and freeze numbers before prose.
4. Numbers freeze — complete (approved). Frozen: F3 lag-1 r 0.84-0.86 (baseline 0.848);
   Poisson 63.21 / 8.03 / 1.90%; T1 as in `T1_design_coverage.csv`; B1 slope 0.95, residual SD
   0.12 ft, 95% intervals ~0.86-0.96 ft wide, `_15_3` regression 585.6 ft vs 585.95 ft figure;
   LOO row-shift error 0.001 ft (circular, same assumption as ADR 0001); LOO interpolation errors
   0.11 / 0.21 ft (n=2). State circularity and n=2 in caveats; runup 2/2.5/3 ft are assumptions.
5. Draft main memo from frozen numbers — complete (user-approved). Figure numbering: F1 locator,
   F2 AVG-change grid, F3 persistence, F4 15-yr ARI surface; Table 1 (coverage).
   Newly approved facts in the draft: Poisson P(0/1/2/3+) = 36.8/36.8/18.4/8.0%; AVG windows with
   no high year 63-65% and 3+ high years 18-20% (vs 36.8% / 8.0% independent); high year = top
   1-in-15 of a scenario's annual-max monthly record; `_15_3` has the highest 3 C ARI elevation
   (but `_20_5` has the largest AVG rise, +2.1 vs +1.9 ft); user confirmed as acceptable:
   breaches degrade Dead Horse Bay habitat, dredged material reduces breach frequency,
   evaporation rises with warming, daily synthetic inputs, NOAA Net Basin Supply, SPs 1968/4997
   near LTP. Caveat 4 defines Poisson counts; caveats 5-6 cite LOO circularity (0.001 ft) and
   n=2 interpolation tests (0.11/0.21 ft).
6. Draft Appendices A and B — complete. User relaxed limits: aim toward
   ~5 pp total without hurting content or readability. Concision pass applied (user-approved
   edits): word counts now main ~1,540 (+~130 caption words), A ~420, B ~710; total ~2,670
   (~5.3 pp at ~500 words/page). B adds one derived fact (user-approved): borderline cells within
   ~0.5 ft of a design (e.g. 3 C/+10% at 584.2 ft vs 584 ft at 0 runup; 586.2 vs 586 ft at
   +2 ft runup). Also checked, not in prose: all regression target AVGs lie inside the known
   AVG range (no leverage concern).
7. Assemble .docx + PDF; check length and consistency; fill placeholders. Fix F4 in-image note
   "SWL excludes runup" (misleading on the +2 ft runup version; e.g. "SWL plus 2 ft runup").
8. Update README / `docs/`; tidy repo.

Phase 3 outputs are in `longtailpoint/presentation/`: `F2_scenario_avg_change`,
`F3_avg_persistence`, and revised `4999_ari15_p2d00runup` figures with CSV data;
`F3_persistence_summary.csv` and `F3_annual_high_years.csv`; `T1_design_coverage.csv`,
`T2_poisson_examples.csv`; `B1_swl_avg_regression.png`, `B1_regression_predictions.csv`,
`B1_known_residuals.csv`; and `LOO_row_shift.csv` / `LOO_interpolation.csv`. F3 includes
both low- and high-AVG scenarios for 1.5 C and 3 C (user-selected), shows 1970-2069 in its
timeline, and uses a fixed-seed shuffle. Regression includes the 13 workbook ARIs plus
primary ARI 15. Values were frozen in phase 4 (see above).
Figure style (after review): F2 and the 4999 ARI figures are flat 17-cell grids
(no interpolation), RdBu scale centered on the baseline (`_0_0`) value, climate_canvas
colorbar ticks, white alpha-0.88 label boxes, and black outlines with a white halo on
modeled cells (F2 has no teal highlight); F3 timeline x-axis is synthetic year
1-100, not calendar years.

## 8. Open placeholders

- Memo header and author.
- Two dataset citations (Framework Study AVG; ERDC SWL).
- Locator map (F1).
- Dashboard screenshots (A-A).
- Primary-literature citations for warmer/wetter trend (GLISA only so far).

## 9. Repo rules to honor

Ask before every commit and push. TDD (failing test first). `data/raw/` is read-only. Keep
scripts that produce outputs in the repo; update docs in the same change. Don't commit
generated artifacts or zips without asking. Ruff line length 100. If `uv run` fails, use
`.venv\Scripts\python.exe -m pytest` (likewise `-m ruff`, `-m mypy`).

## 10. Housekeeping

`CONTEXT.md` "Known scenario" fix (extreme_low/extreme_high swap) committed on branch
`ltp-swl-memo` with phases 1-6. `longtailpoint.zip` remains untracked (do not commit without
asking). Merge `ltp-swl-memo` to `main` via PR when the report is done.
