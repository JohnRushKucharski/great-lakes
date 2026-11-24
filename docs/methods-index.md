# Methods index

Every file in a workflow's `methods/` folder is listed here (a test fails if one is missing
or a link is dead). A **method note** explains how a result was derived or how well it
fits; a pass/fail check is a **gate** and lives in `scripts/` (see [`GLOSSARY.md`](../GLOSSARY.md)).

Type: method, validation, figure set, notebook. Status: `final` means no changes are
planned (it can still be improved); `draft, incomplete` means unfinished or has open next
steps.

## Data products

| Method note | Workflow | Type | Status |
| --- | --- | --- | --- |
| [`scenario_completion.md`](../workflows/analysis/data-products/swl/methods/scenario_completion.md): Delaunay fill and row-shift extrapolation of the 12 missing swl scenarios | [swl](../workflows/analysis/data-products/swl/README.md) | method | final |
| [`compare_fill_to_climate_canvas.md`](../workflows/analysis/data-products/swl/methods/compare_fill_to_climate_canvas.md): fill agrees with climate_canvas within 0.05 ft (the gate's write-up) | [swl](../workflows/analysis/data-products/swl/README.md) | validation | final |
| [`method_quality.md`](../workflows/analysis/data-products/swl/methods/method_quality.md): swl-on-avg regression (B1) and leave-one-out checks | [swl](../workflows/analysis/data-products/swl/README.md) | validation | final |
| [`summarize_precip_temp_effects.py`](../workflows/analysis/data-products/swl/methods/summarize_precip_temp_effects.py): % change in swl for the known precip and temperature pairs | [swl](../workflows/analysis/data-products/swl/README.md) | method | final |

## Data analysis and evaluation

| Method note | Workflow | Type | Status |
| --- | --- | --- | --- |
| [`avg_ari_poisson_method.md`](../workflows/analysis/data-analysis/avg-statistics/methods/avg_ari_poisson_method.md): Poisson / peaks-over-threshold ARI of avg levels | [avg-statistics](../workflows/analysis/data-analysis/avg-statistics/README.md) | method | final |
| [`aep_method.md`](../workflows/evaluation/swl/batch-resources/methods/aep_method.md): why swl ARI is converted to annual exceedance probability and not `1 / ARI` | [swl batch-resources](../workflows/evaluation/swl/batch-resources/README.md) | method | final |
| [`annual_probability_method.md`](../workflows/evaluation/avg/batch-resources/methods/annual_probability_method.md): avg `annual_probability` = portion of water years with at least 1 occurrence (not a return period) | [avg batch-resources](../workflows/evaluation/avg/batch-resources/README.md) | method | final |
| [`equivalent_elevation_method.md`](../workflows/evaluation/swl/batch-resources/methods/equivalent_elevation_method.md): equivalent elevation and elevation delta | [swl batch-resources](../workflows/evaluation/swl/batch-resources/README.md) | method | final |
| [`template_swl_reference.md`](../workflows/evaluation/swl/batch-resources/methods/template_swl_reference.md): every resources and config column of the swl worksheet | [swl batch-resources](../workflows/evaluation/swl/batch-resources/README.md) | method | final |

## Case studies

Long Tail Point overtopping has no `methods/` notes of its own: it points to the swl and
avg-statistics notes above (see its [README](../case-studies/long-tail-point/overtopping/README.md)).

| Method note | Workflow | Type | Status |
| --- | --- | --- | --- |
| [`musky_habitat.ipynb`](../case-studies/long-tail-point/habitat/methods/musky_habitat.ipynb): musky criteria at one floor (`BOTTOM_FT`) | [habitat](../case-studies/long-tail-point/habitat/README.md) | notebook | final |
| [`pondweed_habitat.ipynb`](../case-studies/long-tail-point/habitat/methods/pondweed_habitat.ipynb): pondweed criteria at one floor (`BOTTOM_FT`) | [habitat](../case-studies/long-tail-point/habitat/README.md) | notebook | final |
| [`musky_matrix.ipynb`](../case-studies/long-tail-point/habitat/methods/musky_matrix.ipynb): musky response surfaces for all floors | [habitat](../case-studies/long-tail-point/habitat/README.md) | figure set | final |
| [`low_water_cycles.ipynb`](../case-studies/long-tail-point/habitat/methods/low_water_cycles.ipynb): low-water cycle definition behind F8 | [habitat](../case-studies/long-tail-point/habitat/README.md) | notebook | final |
| [`high_water_cycles.ipynb`](../case-studies/long-tail-point/habitat/methods/high_water_cycles.ipynb): high-water cycle definition behind F8 | [habitat](../case-studies/long-tail-point/habitat/README.md) | notebook | final |
