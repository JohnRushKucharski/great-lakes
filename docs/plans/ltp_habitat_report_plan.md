# LTP Dead Horse Bay habitat resilience memo: plan (handoff)

> Historical plan, written before the reorganization. Current locations are under
> `case-studies/long-tail-point/habitat/` (see its README): `report\build_report.py` is
> `scripts/build_memo_draft.py`; `report\figure_f*.py` are `scripts/figure_<content>.py`;
> `report\report_draft.md` is `inputs/memo_draft.md`; `report\figures\` is `outputs/figures/`;
> `JK\`/`JO\` inputs are in `inputs/`; the reliability CSVs are in `outputs/reliability/`;
> the JK notebooks are in `methods/`. Old paths below are left as written.

Output: this folder (`longtailpoint\habitat\report\`): build script + figures + .docx.
Word memo styled like `longtailpoint\MEMORANDUM.docx`, same tone, reuse text where apt. <=5 pp text (max 10), figures PNG.
TO: LTP Project Delivery Team. FROM: GLRI Framework Team. Prepared by Jenny Olszewski (USGS), John Kucharski (Deltares). Date: 9 November 2026.
Purpose: assess resilience of habitat restoration plans in Dead Horse Bay (planted submergent and emergent marsh, musky habitat incl. woody debris structures) AND demonstrate how GLRI avg lake-level scenarios serve restoration projects (simple -> complex). Jenny leads, John builds on top. Not for programmers: no software description.
Inputs: `habitat\JO\` (Jenny memo .docx, slides), `habitat\JK\` (notebooks, regimes.xlsx, first_draft.pptx, 35% plan PDF, michiganhuron_avg.csv).

## Decisions it supports (near-term, within ~1 yr; design must work ~couple decades, minimal intervention)
Planting elevations; woody debris (WD) structure depth/placement; plant palette / marsh-type transitions; robustness of depths. Structures assumed NOT moved/added (one sentence on possible adaptation only if analysis shows value). Main failure to avoid: structures perched out of water.

## Outline
1 Purpose & Bottom Line | 2 Project Context & Why This Analysis | 3 Inputs | 4 Two lenses (A depth at avg levels - Jenny; B yearly suitability + variability - John)
5 Results in 4 levels (each w/ "when to use this level"):
 - L1 Quick screen: lake movement (F1 first_draft slide 2 mean level change; F2 timeline strip, Jenny slide 24)
 - L2 Marsh zones (Jenny): F3 Elevation Ladder (hero), F4 marsh-zone % by scenario + 2 depth maps (3C dry, 3C wet)
 - L3 Specific design (WD/musky): F5 structure scorecard (6 ends), F6 reliability heatmap (musky juv/spawn/recruit by floor)
 - L4 Species & variability: F7 hydrograph (baseline vs 3C dry/wet), F8 low/high cycle surfaces, F9 robustness chart
6 Options & advice (conditional, not a recommendation) | 7 Appendix: definitions (regimes.xlsx), datum/units, full matrices, extra maps, limitations

## Figures
F1 mean level change (first_draft slide 2) | F2 timeline strip | F3 Elevation Ladder: y=floor elev 571-579 ft IGLD85; baseline + 1.5C/3C dry/3C wet level bands; Jenny zone depth bands; WD floors; save-point elevation histogram; John's yearly suitability strips
F4 marsh zone % (Jenny T3 heatmap) + 2 maps | F5 WD scorecard | F6 reliability heatmap (rows musky juv/spawn/recruit + pondweed; cols floor elev; 3-4 focus scenarios; full 3x7 matrix to appendix)
F7 hydrograph | F8 cycle surfaces | F9 robustness chart. Tables: scenario subset, habitat definitions, WD floors (Jenny T8).
Do NOT reuse DU map or 35% plan images (DU property); reference only. Redraw/own figures; Jenny's own figures reusable.

## Rules
- Datums: both analyses IGLD85 per docs (Jenny baseline 579.16 ft IGLD85; John levels m, floors ft IGLD85). Accepted; no audit. Keep unit and datum conversion separate.
- "Works": juvenile/spawning/pondweed reliable >=75% yrs, marginal 50-75, unreliable <50. Recruitment judged vs best baseline (>= half of ~8%; baseline peak ~16% at 578 ft).
- Robust set: 1.5C/0, 1.5C/5, 3C/0, 3C/5, 3C/10, 3C/15; 5C/7C context only.
- Tiers: brittle (baseline only) < lowest (both 1.5C) < robust (all 1.5C + 3C) < very robust (+ some 5C/7C). Floor reaches a tier only if reliable in every scenario of the tier. 3C/0 and 3C/15 pull opposite directions, so covering all 3C needs a broadly tolerant floor.
- Pondweed = submergent marker (mostly deep, some shallow): 1-3 m growing season (May-Aug), >=0.5 m winter, rise <=0.15 m/month; floors 571-577 ft.
- Musky floors 573-579 ft; WD structure floors = Jenny T8 (575.01-576.46 ft IGLD85) > 35% plan PDF (LWD 576.15; ~575-577).
- Cycles: rate per 100 yr vs baseline and historical; "variability lost/gained" flags; 1-in-7-13 yr is context, not target. Low: 175.90-176.30 m, 24-60 mo, trailing 12-mo mean. High: >=176.75 m (~579.9 ft), >=24 mo, no upper bound.
- Option 4: check if one structure is best under baseline, another 1.5C, another 3C (robustness-by-complement).
- Adaptive management/monitoring: next-step mention only, not a recommendation.
- Limitations: avg monthly levels only (no waves/storm/ice/turbidity, sediment/bathy change); vegetation lag; invasives not modeled.

## Options (Sec 6)
1 plant for 1.5-3C not baseline; 2 widen domain up/down slope; 3 palette spanning zones; 4 WD robustness as planned (+1 sentence adaptation); 5 treat 5C/7C as stress tests; next steps: monitoring/adaptive management.

## Draft opening prose (KEEP; Purpose and Bottom Line)

> This memo assesses how resilient the planned habitat restoration in Dead Horse Bay, the marshy area behind Longtail Point, is to plausible future lake levels. The plans include planted emergent and submergent marsh zones and woody debris structures designed as habitat for musky. We ask a simple question: if lake levels move as the GLRI scenarios suggest over the next couple of decades, do the planned elevations still provide the intended habitat?
>
> We answer in two ways. First, we map where marsh zones and structures sit relative to future water depths. Second, we count how many years each elevation would support the habitat, and whether the lake keeps its natural high- and low-water swings. The results identify which elevations are robust, meaning they work across the near- and moderate-term scenarios. They also show where the plan is brittle, for example structures left perched above the water.
>
> The memo builds from a quick screen to a species-level assessment. Other restoration projects can follow the same steps with the same lake-level data.

Background framing: GLRI (EPA) funded the avg lake-level data/scenarios; Ducks Unlimited is a partner; site info https://www.uwgb.edu/green-bay-area-of-concern/fish-wildlife-habitats/priority-areas/#dead-horse-bay

## Grill decisions (log)
- Bottom line (Sec 1): one bullet per decision (planting elevations, WD depth/placement, palette, depth robustness), each robust/brittle/conditional + tier; written LAST from results. Opening prose stays.
- Length: main text figures = F3, F4, F5, F6, F9; F1+F2 merged into one small two-panel figure; F7, F8 appendix. F2 "timeline strip" meaning unclear to John (Jenny slide 24 origin): build draft, John reacts.
- F3 core: y=elevation; level bands (baseline,1.5C,3C dry,3C wet); Jenny zone bands; WD floor markers; thin side panel elevation histogram. Yearly suitability strips move to F6. John will react after seeing figure ("yearly suitability" unclear to him: define it plainly in text).
- Blocking for first draft: pondweed runs only. Cycles (high-water rates, hist-vs-baseline, 579.9 ft reconcile) feed F8/appendix; lit grading = short appendix table for claims actually made.
- Ownership: single report_draft.md = text of record; Jenny's text enters Lens A/Level 2, John builds Lens B/Levels 3-4/Sec 6. Copilot edits ALL sections for one unified voice and fully integrated analysis (expert Great Lakes ecology/climate + science-comms role); mark items "[Review: John]" / "[Review: Jenny]" where judgment/ownership needed. Jenny reviews built .docx, John applies comments to draft.
- Glossary added to CONTEXT.md: floor, reliability class, robust set, robustness tier. Tiers renamed: brittle < minimal (was "lowest") < robust < very robust. "Robust" used as adjective only with a tier/scenario-group modifier.
- Tier wording: prose says "robust through the 1.5 C scenarios / all 3 C scenarios"; bare tier labels only in figures/tables/legends; bottom line may add "(tier: robust)".
- Option 4 rule (pre-set): if no single WD floor is reliable across the robust set, report the complementary mix of floors per scenario and add one adaptation sentence; if one floor covers it, say so and omit adaptation. Always conditional advice, not a recommendation.
- Scenario labels: code = warming C / precip %. "dry" = +0% precip at that warming; "wet" = largest precip increase at that warming (3C dry = 3C/0, 3C wet = 3C/15). Define once in Sec 3; prose dry/wet, tables/figures codes. Added to CONTEXT.md.
- Build order (review each with John before next): 1 pondweed runs -> 2 F3 -> 3 F6 -> 4 F5 -> 5 F9 -> 6 F4 + merged F1/F2 -> 7 prose Sec 2-6, bottom line last -> 8 F7/F8 + appendix.
- DONE pondweed-571-577: `report\pondweed_runs.py` -> `pondweed_reliability.csv` (floor x scenario x component, % complete years). Verified vs reviewed 574/575/576 notebooks (1030 yrs; growing 96.5/79.0/46.5% baseline). Needs hydropattern >=0.3: run with `$env:PYTHONPATH="C:\Users\kucharsk\dev\hydropattern"` (repo pin is v0.1.1, no `scenarios` module; bumping pin = separate decision). Tests: `tests\test_pondweed_runs.py` (skip if old hydropattern). Early read: no single floor is reliable (>=75%) in all 6 robust-set scenarios for growing season (3C/0 favors 571-572 ft, 3C/15 favors 574-576 ft).
## HANDOFF (read first in a new session)
State (2026-11-09): scaffold + grill + pondweed runs + F3 (reviewed OK) + F6 (reviewed) + F5 + F9 (reviewed OK) DONE. F4 + F1 drafts DONE (John to react): F1 = `figure_f1f2.py` heatmap only (timeline panel B dropped at John's request; plausibility = observed trends + plausible change by period go in Level 1 prose; no F2). F4 = heatmap (`figure_f4.py`, John: "great") + F4B/F4C = Jenny's 3C dry / 3C wet depth maps copied unchanged from her memo (media image8/image9; written to `figures\F4B.png`/`F4C.png` by `figure_f4.py`; my redrawn maps dropped). Slots `{{F4B}}`,`{{F4C}}` added; memo captions renumbered Fig 1..10. Next = prose Sec 2-6 (bottom line last) -> F7/F8 + appendix. F5 column order: 3C dry, 1.5C dry, baseline, 1.5C wet, 3C wet (dry -> wet, John).
- F6: `report\musky_runs.py` -> `musky_reliability.csv` (floors 573-579, 17 scenarios; needs hydropattern >=0.3 via PYTHONPATH, same as pondweed; tests `tests\test_musky_runs.py` match musky_matrix.ipynb baseline). `report\figure_f6.py` -> `figures\F6.png` (tests `tests\test_f6_reliability.py`). 5 panels in F3 order (baseline, 1.5C/5, 3C/15, 1.5C/0, 3C/0); rows musky juv/spawn/recruit + pondweed growing/winter; cols floors 571-579 (grey n/a outside native range: musky 573-579, pondweed 571-577). Classes: reliable >=75, marginal 50-75, unreliable <50; recruitment (% of 5-yr windows) reliable >=8, marginal 4-8 (John's choice). TODO: full 3x7 (all scenarios) matrix for appendix.
- F3: `report\figure_f3.py` -> `figures\F3.png` (`.venv\Scripts\python.exe longtailpoint\habitat\report\figure_f3.py`). Tests `tests\test_f3_elevation_ladder.py`. Inputs: `JK\michiganhuron_avg.csv` (m -> ft), `JO\Compiled PI Survey Data_jo.xlsx` sheet `depth_analysis` (288 save points, col "Estimated Bottom elevation (ft)"), Jenny T3 zone depth key, T8 WD floors. Columns: baseline, 1.5C/5, 3C/15 (wet), 1.5C/0, 3C/0 (dry) (one scenario per column, never pooled); level band p10-p90 monthly + median; zone bars = annual mean level minus zone depth range (shifted per scenario); WD floor band + 35% plan LWD line; side histogram. y axis widened to 571-583 ft (3C wet level ~581 ft would be off-chart at 579). Unrooted floating zone omitted (any depth).
- Scaffold: `report\build_report.py` (+ `report_draft.md` text of record, `{{F1}}..{{F9}}` slots -> `figures\Fn.png` else grey placeholder). Build: `.venv\Scripts\python.exe longtailpoint\habitat\report\build_report.py` -> `LTP_habitat_resilience_memo.docx` (untracked). Styling reused from `src\great_lakes\build_memo_docx.py`. Tests: `tests\test_build_habitat_report.py`.
- Pondweed: `report\pondweed_runs.py` -> `report\pondweed_reliability.csv`. Tests: `tests\test_pondweed_runs.py`. (Update: the repo pin is now hydropattern v0.3.3, which has `scenarios`; the PYTHONPATH workaround and the "needs hydropattern >=0.3" notes above no longer apply.)
- Git: branch `main` pushed. These are gitignored (local only, NOT backed up): `report\`, `habitat\JK\`, `habitat\JO\`, docs drafts, `src\great_lakes\longtailpoint_report.py`, `build_memo_docx.py`, related tests. Keep PLAN.md current here. Ask before every commit/push. `CONTEXT.md` edits (floor, reliability class, robust set, robustness tier, dry/wet scenario) are UNCOMMITTED on main.
- Sandbox: shell writes denied; create/modify files with edit/create tools. `uv run` may fail: use `.venv\Scripts\python.exe -m pytest|ruff|mypy` (ruff/mypy: add `--no-cache` / `--cache-dir=nul`). `ruff check .` has ~256 pre-existing errors in other files; check only touched files.
- Style: caveman mode was requested by John (terse replies); TDD; ruff line 100; concise comments; units and datum conversions separate; IGLD85 for both analyses.
- Source of facts for prose (John, 2026-11-09): project goal = marsh habitat restoration and conservation in Dead Horse Bay. Woody-debris (WD) site details = ONLY `habitat\JK\WI-516-101 LTP 35% PRELIMINARY PLAN 8-20-26.pdf` (read text/facts only; its images/DU map must NOT be reused: DU property). Anything else = Jenny's `habitat\JO\longtail_habitat_summary_28oct2026.docx` (read via zipfile+regex; python-pptx/docx tooling may be missing). John has nothing further to add: draft site background / WD build detail from those two sources, mark gaps "[Review: John]"/"[Review: Jenny]". "Yearly suitability" defined plainly in text.
- Scenario code `_P_T` in CSV = precip %/warming C (e.g. `_0_3` = 3C dry, `_15_3` = 3C wet; `_0_1.5`, `_5_1.5` = 1.5C). Robust set CSV names: `_0_1.5,_5_1.5,_0_3,_5_3,_10_3,_15_3`.
- F5: `report\figure_f5.py` -> `figures\F5.png` (tests `tests\test_f5_wd_scorecard.py`). Cell = median May-Aug depth (level - floor, ft) over T8 floor; classes from Jenny T7 (too shallow <0.98; spawning+recruitment 0.98-1.97; spawning only 1.97-4.92; too deep >4.92). Imports constants from `figure_f3.py`. Level CSV runs past year 2262: parse month from the ISO string, not `pd.to_datetime`.
- F9: `report\figure_f9.py` -> `figures\F9.png` (tests `tests\test_f9_robustness.py`). REDESIGNED (John): one diverging scale around baseline, 8 levels: never reliable (dark red) < lower lake only (light red) / higher lake only (same light red, hatched) < baseline only (white) < baseline + one 1.5C < 1.5C (both) < 1.5C + part of 3C < 3C (all 1.5C + all four 3C = "robust", dark green). "very robust"/5C dropped (stress-test context only). Fails-baseline direction: lower = reliable in 1.5C/0 or 3C/0; higher = 3C/15; 1.5C/5, 3C/5, 3C/10 neutral; tie -> lower. Aim tier = weakest component (musky = juvenile + spawning, recruitment separate row; pondweed = growing + winter). 3 panels: musky, pondweed, overlap bonus (not required). Cell counts (35 cells): never 1, lower 6, higher 7, baseline only 0, +one 1.5C 10, 1.5C 0, 1.5C + part 3C 7, 3C 4. John chose NOT to reorder F6. Early read: pondweed best = 1.5C + part of 3C (571-573 ft), winter survival 3C at 571-572; musky juvenile 3C at 573-574; spawning best = +one 1.5C (576-577); no floor serves both aims beyond that. Option 4 rule applies. John to react to v3.
- F3/F5 column order 3C dry, 1.5C dry, baseline, 1.5C wet, 3C wet; F6 deliberately NOT reordered (John).
- F9 tier names in the grill log (brittle/minimal/robust/very robust) are SUPERSEDED by the 8-level diverging scale above; "very robust" dropped. Update CONTEXT.md glossary to match if still old.
- Figures done and accepted: F1 (heatmap only), F3, F4 (+F4B/F4C Jenny maps), F5, F6, F9. Memo figure numbers: Fig1=F1, 2=F3, 3=F4, 4=F4B, 5=F4C, 6=F5, 7=F6, 8=F7, 9=F8, 10=F9 (check captions in draft match slot order).
- NEXT STEPS in order: (0) 2026-11-09 later: Sec 2-4 reviewed/edited by John. Level 1-3 prose, Level 4 F9 prose, Sec 6, Bottom line DRAFTED (John to review). Level 4 F7/F8 text = "[Pending]" until figures built. Option 4 result: no single WD floor covers robust set; 576 ft covers baseline/1.5C-5/3C-5/3C-10, 575 ft covers 1.5C-0/3C-5; 3C/0 + 3C/15 uncovered -> one adaptation sentence in Sec 6. Open flags: Jenny slide-24 period labels + 1.5C mid-century percentile; Jenny's "dry loses <4ft" wording vs data. Bottom line to be revisited after F7/F8.
(1) DONE except F7/F8 text and appendix. Original note: prose Sec 2-6 in `report_draft.md`: fill Level 1-4 "[Stub...]" text; Level 1 must cover observed trends + plausible change by time period (replaces dropped F1 panel B / old slide-24 percentile timeline: 1.5C ~p50 in 2030-40 falling to p1 by 2099; 3C p82.5 -> p37.5 -> p10; 5C p99 -> p62.5 -> p50; 7C p99 -> p82.5 -> p82.5, from Jenny slide 24); then Sec 6, Bottom line LAST from results. Notes: CONTEXT.md is at repo root; PDF text via pypdf; Jenny docx text via zipfile (session files\jo.txt). Open: PDF HW/AW/LWD meaning + datum (John). (2) F7 hydrograph + F8 cycle surfaces + appendix (full 3x7 F6 matrix; tables: scenario subset, habitat definitions, WD floors; short lit-grading table). Needs hist-vs-baseline cycles + high-water rates (see Tasks). (3) final: rebuild memo, ruff/mypy/pytest on touched files, update PLAN.md, ASK before commit/push (report\, JK\, JO\ are gitignored; commit candidates = tests, CONTEXT.md, src).

## Domain notes from John (use in prose, Sec 5 Level 3/4 and Sec 6)
- Recruitment zones = shoreward of the spawning zones; occasionally (some years) inundated deeper than normal to give extra spawning habitat. So recruitment being unreliable at deeper floors is expected, not a failure. Frame F6 recruitment row that way.
- Recruitment range (T7: 0.98-1.97 ft, May-Jun) is the shallow end of the spawning range (0.98-4.92 ft, May-Jun); only extra rule is >=3 of 5 yrs. So recruitment habitat ~ shallow spawning habitat (John; depth ranges nest, verified in T7).
- Restoration aims: improve submergent (pondweed) habitat AND musky spawning/rearing habitat. Floors good for both musky and pondweed are of extra interest, but each aim stands alone even where they do not coincide at the same spot. Do not require overlap when judging results.

## Tasks / open
- Build scaffold first (this folder): script that assembles figures + docx; repo rules: TDD, ask before commit/push, `uv run ruff/mypy/pytest`.
- lit-evidence-cycles: grade evidence strong (peer-reviewed Great Lakes, similar definitions) / moderate (unclear or dissimilar) / hypothesis (still cite sources)
- hist-vs-baseline-cycles: historical monthly Michigan-Huron (`data\raw`) vs baseline in 100-yr chunks
- pondweed-571-577: new runs | high-water-final: compute rates; reconcile first_draft 579.9 ft
- pdf-design-facts: bid qty 111 root wads, 54 logs, 57 log piles, 30 CY slash, 827 tn gravel/cobble, 114 boulders; LWD=576.15
- Remaining figures: F7, F8 (+ appendix 3x7 F6 matrix). All others done.
