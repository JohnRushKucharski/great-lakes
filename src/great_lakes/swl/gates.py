"""swl gates: checks that fail loudly when a data product is wrong.

1. **Fill vs climate_canvas** (`run_gate`): compares `swl.complete`'s in-hull fill against
   climate_canvas's own interpolate+fillin at the same (precip_delta, temp_delta)
   coordinates. Both fill the 7 in-hull scenarios from the same 5 known scenarios using
   Delaunay-linear (barycentric) interpolation:

   - `swl.complete` builds one Delaunay triangulation over the 5 known (precip, temp)
     points and evaluates it directly at each in-hull target (see docs/adr/0001).
   - `climate_canvas.data_utilities.interpolator(..., fillin=True)` is bilinear on the
     known grid's cells, falling back to its own delaunay_fill() (also Delaunay-linear
     over the same known points) for any cell with a missing corner -- which is every
     in-hull scenario here.

   For each lake's centroid save point (`lakes.lake_centroid_save_point_id`) and every ARI
   in ARIS, the gate fails if any |difference| exceeds `TOLERANCE_FT`. The comparison csv
   and README.txt are written first, so a failure can be inspected.
   See data-products/swl/methods/compare_fill_to_climate_canvas.md.

2. **ARI curves** (`run_ari_gate`): every save point's water level must be present and
   non-decreasing as the ARI grows, in every sheet of every lake's workbook.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from climate_canvas.data_utilities import interpolator  # type: ignore[import-untyped]
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]

from great_lakes import ari, lakes, units
from great_lakes.batch import run_readme
from great_lakes.swl import sheets as swl_sheets
from great_lakes.swl.complete import known_scenario_coords

LAKES = tuple(lakes.LAKE_SWL_FILENAMES)
ARIS = (1.0, 10.0, 50.0, 100.0)
TOLERANCE_FT = 0.05

_COMPARISON_CSV_NAME = "filled_vs_climate_canvas_comparison.csv"
_VIOLATIONS_CSV_NAME = "ari_curve_violations.csv"


class GateFailure(Exception):
    """A gate's check failed; the data product should not be trusted."""


def run(clean_data_dir: Path, filled_data_dir: Path) -> pd.DataFrame:
    """Compare the Delaunay-filled values (swl/complete.py) against climate_canvas's own
    interpolate+fillin, for every lake in LAKES / ARI in ARIS, at each in-hull
    target scenario coordinate present in filled_data_dir's workbook.

    Returns one row per (lake, ari, scenario): lake, save_point_id, ari, scenario,
    precip_delta, temp_delta, fillin_swl_ft, climate_canvas_ft, diff_ft.
    """
    rows = []
    for lake in LAKES:
        clean_path = lakes.resolve_lake_swl_path(lake, clean_data_dir)
        known_sheets = pd.read_excel(clean_path, sheet_name=None)
        save_point_id = lakes.lake_centroid_save_point_id(lake, known_sheets)

        filled_path = lakes.resolve_lake_swl_path(lake, filled_data_dir)
        filled_sheets = pd.read_excel(filled_path, sheet_name=None)

        coords = known_scenario_coords(list(known_sheets.keys()))
        precips = sorted({p for p, _ in coords.values()})
        temps = sorted({t for _, t in coords.values()})

        for aril in ARIS:
            z = np.full((len(temps), len(precips)), np.nan)
            for name, df in known_sheets.items():
                suffix = swl_sheets.parse_scenario_sheet_name(name)
                if suffix not in coords:
                    continue
                p, t = parse_scenario_name(suffix)
                row = df.loc[df["ID"] == save_point_id, aril]
                if row.empty:
                    continue
                z[temps.index(t), precips.index(p)] = units.convert_units(
                    row.iloc[0], "m", "ft"
                )
            xs = np.array(precips, dtype=float)
            ys = np.array(temps, dtype=float)
            cc_interp = interpolator(xs, ys, z, fillin=True)

            for name, df in filled_sheets.items():
                suffix = swl_sheets.parse_scenario_sheet_name(name)
                if suffix is None or suffix in coords or not suffix.startswith("_"):
                    continue  # skip known scenarios; only compare in-hull fills
                p, t = parse_scenario_name(suffix)
                row = df.loc[df["ID"] == save_point_id, aril]
                if row.empty:
                    continue
                filled_ft = units.convert_units(row.iloc[0], "m", "ft")
                cc_ft = cc_interp((p, t))
                rows.append({
                    "lake": lake,
                    "save_point_id": save_point_id,
                    "ari": aril,
                    "scenario": suffix,
                    "precip_delta": p,
                    "temp_delta": t,
                    "fillin_swl_ft": round(filled_ft, 4),
                    "climate_canvas_ft": round(cc_ft, 4),
                    "diff_ft": round(filled_ft - cc_ft, 4),
                })
    return pd.DataFrame(rows)


def write_comparison_csv(comparison: pd.DataFrame, output_dir: Path) -> Path:
    """Write `comparison` to `<output_dir>/filled_vs_climate_canvas_comparison.csv`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _COMPARISON_CSV_NAME
    comparison.to_csv(path, index=False)
    return path


_NAMING_SCHEME_TEXT = (
    f"{_COMPARISON_CSV_NAME} - one row per (lake, ari, in-hull target scenario): "
    "fillin_swl_ft (hydropattern's own Delaunay fill), climate_canvas_ft (climate_"
    "canvas's own interpolate+fillin over the same known points), and diff_ft "
    "(fillin_swl_ft - climate_canvas_ft). ARI values: "
    f"{', '.join(ari.format_ari(a) for a in ARIS)}. See "
    "data-products/swl/methods/compare_fill_to_climate_canvas.md for the write-up."
)


def check_max_diff(comparison: pd.DataFrame, tol: float | None = None) -> float:
    """Return max |diff_ft|; raise GateFailure if it exceeds `tol` (default TOLERANCE_FT)
    or if nothing was compared.
    """
    tol = TOLERANCE_FT if tol is None else tol
    if comparison.empty:
        raise GateFailure("Compared nothing: no in-hull target scenarios were found.")
    worst = float(comparison["diff_ft"].abs().max())
    if worst > tol:
        raise GateFailure(f"max|diff| = {worst:.4f} ft exceeds the {tol} ft tolerance.")
    return worst


def run_gate(
    clean_dir: Path, filled_dir: Path, output_dir: Path, workspace_root: Path
) -> pd.DataFrame:
    """Run the fill-vs-climate_canvas comparison, write its csv + README.txt to
    `output_dir`, then enforce the tolerance (GateFailure). Returns the comparison.
    """
    comparison = run(clean_dir, filled_dir)
    csv_path = write_comparison_csv(comparison, output_dir)

    inputs = [
        (f"{lake} known swl workbook", lakes.resolve_lake_swl_path(lake, clean_dir))
        for lake in LAKES
    ] + [
        (f"{lake} filled swl workbook", lakes.resolve_lake_swl_path(lake, filled_dir))
        for lake in LAKES
    ]
    if len(comparison):
        results_text = (
            f"n={len(comparison)}  max|diff|={comparison['diff_ft'].abs().max():.4f} ft  "
            f"mean|diff|={comparison['diff_ft'].abs().mean():.4f} ft  "
            f"(tolerance {TOLERANCE_FT} ft)"
        )
    else:
        results_text = "n=0 (no in-hull target scenarios found to compare)."

    run_readme.write_readme(
        output_directory=output_dir,
        title="Filled vs climate_canvas comparison report",
        inputs=inputs,
        results_text=results_text,
        naming_scheme_text=_NAMING_SCHEME_TEXT,
        written_paths=[csv_path],
        workspace_root=workspace_root,
    )
    print(results_text)
    print(f"Wrote {csv_path}")
    check_max_diff(comparison)
    return comparison


def find_ari_curve_violations(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Rows (sheet, ID, ari, problem) where a save point's curve is missing or decreasing.

    "missing": NaN at that ARI. "decreasing": lower than the previous (smaller) ARI.
    """
    found = []
    for name, frame in sheets.items():
        ari_cols = sorted(c for c in frame.columns if c not in swl_sheets.NON_ARI_COLUMNS)
        values = frame[ari_cols].to_numpy(dtype=float)
        ids = frame["ID"].to_numpy()
        missing = np.isnan(values)
        with np.errstate(invalid="ignore"):
            decreasing = np.diff(values, axis=1) < 0
        for problem, hits, offset in (("missing", missing, 0), ("decreasing", decreasing, 1)):
            for i, j in zip(*np.nonzero(hits)):
                found.append((name, ids[i], ari_cols[j + offset], problem))
    return pd.DataFrame(found, columns=["sheet", "ID", "ari", "problem"])


def run_ari_gate(
    workbook_dir: Path, output_dir: Path, workspace_root: Path,
    lake_names: tuple[str, ...] = LAKES,
) -> None:
    """Check every sheet of each lake's workbook in `workbook_dir`; write README.txt to
    `output_dir` (plus `ari_curve_violations.csv` on any violation) and raise GateFailure
    on any violation.
    """
    parts = []
    for lake in lake_names:
        sheets = pd.read_excel(
            lakes.resolve_lake_swl_path(lake, workbook_dir), sheet_name=None, engine="calamine"
        )
        found = find_ari_curve_violations(sheets)
        if not found.empty:
            parts.append(found.assign(lake=lake))
    written: list[Path] = []
    failure = None
    if parts:
        violations = pd.concat(parts, ignore_index=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / _VIOLATIONS_CSV_NAME
        violations.to_csv(path, index=False)
        written.append(path)
        by_lake = violations.groupby("lake").size().to_dict()
        failure = f"{len(violations)} ARI-curve violations {by_lake}; see {path}."
        results_text = f"FAILED: {failure}"
    else:
        results_text = f"ARI curves OK: {len(lake_names)} lakes, no missing or decreasing values."
    run_readme.write_readme(
        output_directory=output_dir,
        title="ARI-curve gate report",
        inputs=[
            (f"{lake} swl workbook", lakes.resolve_lake_swl_path(lake, workbook_dir))
            for lake in lake_names
        ],
        results_text=results_text,
        naming_scheme_text=(
            f"{_VIOLATIONS_CSV_NAME} - written only on failure: one row per (lake, sheet, "
            "save point ID, ARI) whose value is missing or lower than at the previous ARI."
        ),
        written_paths=written,
        workspace_root=workspace_root,
    )
    if failure:
        raise GateFailure(failure)
    print(results_text)
