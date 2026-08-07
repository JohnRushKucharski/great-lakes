# Sidecar `.js` manifest for the longtailpoint results dashboard, not live JSON/CSV fetch

The longtailpoint results dashboard (`longtailpoint/dashboard.html`) must let a user
filter/compare `batch_run_twl.py` outputs with zero install and zero local server —
just double-clicking the html file, opened via a `file://` URL. Browsers block
`fetch()`/`XMLHttpRequest` reads of local files under `file://` (a same-origin/CORS
restriction), so the dashboard cannot load a real `.json` or `.csv` manifest at
runtime the normal way. `<script src="...">` is not subject to this restriction, so a
generated `manifest.js` (a plain `window.MANIFEST = {...}` JS literal, not JSON) is
loaded via a `<script>` tag instead. The dashboard reads grid/plot data from this
generated sidecar file; the original `_grid.csv` files it's built from stay untouched
and directly usable elsewhere (e.g. opened in Excel). If dashboard requirements
outgrow this (much larger datasets, need for live/incremental updates, multi-user
access), revisit — a small local server would remove the `file://` restriction
entirely but reintroduces an install/run step this decision was made to avoid.
