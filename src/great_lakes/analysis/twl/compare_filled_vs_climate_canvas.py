"""Compare hydropattern's fillin_twl.py in-hull fill against climate_canvas's own
interpolate+fillin, at the same (precip_delta, temp_delta) coordinates.

Both fill the 7 in-hull scenarios from the same 5 known scenarios using
Delaunay-linear (barycentric) interpolation:

- fillin_twl.py (data/filled/*.xlsx): builds one Delaunay triangulation over the
  5 known (precip, temp) points and evaluates it directly at each of the 7 in-hull
  target coordinates (see docs/adr/0001).
- climate_canvas.data_utilities.interpolator(..., fillin=True): bilinear on the
  known grid's cells, falling back to its own delaunay_fill() (also a Delaunay-
  linear fit over the same known points) for any cell with a missing corner --
  which is every in-hull scenario here, since none sit on the sparse known grid's
  own row/column lines.

For each lake's centroid save point (common_twl.center_save_point_id) and every ARI
in ARIS, this evaluates both methods at each in-hull scenario coordinate present in
filled_data_dir's workbook and writes a comparison CSV + README.txt to output_dir
(default: `<filled_data_dir>/img/comparison` -- see resolve_default_output_dir).

See docs/filled_vs_climate_canvas_comparison.md for the original write-up:
differences are all <= ~0.02 ft, consistent with float/rounding noise rather
than a methodological difference -- both are the same Delaunay-linear fit
over the same known points.

## Usage

    uv run python -m great_lakes.analysis.twl.compare_filled_vs_climate_canvas \\
        <clean_data_dir> <filled_data_dir> [output_dir]
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import typer
from climate_canvas.data_utilities import interpolator  # type: ignore[import-untyped]
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]

from great_lakes import ari_constants, common_twl, run_readme
from great_lakes.fillin_twl import known_scenario_coords

LAKES = tuple(common_twl.LAKE_TWL_FILENAMES)
ARIS = (1.0, 10.0, 50.0, 100.0)

_COMPARISON_CSV_NAME = "filled_vs_climate_canvas_comparison.csv"


def resolve_default_output_dir(filled_data_dir: Path) -> Path:
    """Default output_dir when the CLI's output_dir argument is omitted: an
    `img/comparison` subfolder of filled_data_dir (normally data/filled) -- this
    script specifically validates data/filled's fill, so its output lives
    alongside it. See docs/data_pipelines.md.
    """
    return filled_data_dir / "img" / "comparison"


def run(clean_data_dir: Path, filled_data_dir: Path) -> pd.DataFrame:
    """Compare fillin_twl.py's filled values against climate_canvas's own
    interpolate+fillin, for every lake in LAKES / ARI in ARIS, at each in-hull
    target scenario coordinate present in filled_data_dir's workbook.

    Returns one row per (lake, ari, scenario): lake, save_point_id, ari, scenario,
    precip_delta, temp_delta, fillin_twl_ft, climate_canvas_ft, diff_ft.
    """
    rows = []
    for lake in LAKES:
        clean_path = common_twl.resolve_lake_twl_path(lake, clean_data_dir)
        known_sheets = pd.read_excel(clean_path, sheet_name=None)
        save_point_id = common_twl.center_save_point_id(known_sheets)

        filled_path = common_twl.resolve_lake_twl_path(lake, filled_data_dir)
        filled_sheets = pd.read_excel(filled_path, sheet_name=None)

        coords = known_scenario_coords(list(known_sheets.keys()))
        precips = sorted({p for p, _ in coords.values()})
        temps = sorted({t for _, t in coords.values()})

        for ari in ARIS:
            z = np.full((len(temps), len(precips)), np.nan)
            for name, df in known_sheets.items():
                suffix = common_twl.parse_scenario_sheet_name(name)
                if suffix not in coords:
                    continue
                p, t = parse_scenario_name(suffix)
                row = df.loc[df["ID"] == save_point_id, ari]
                if row.empty:
                    continue
                z[temps.index(t), precips.index(p)] = row.iloc[0] * common_twl.METERS_TO_FEET
            xs = np.array(precips, dtype=float)
            ys = np.array(temps, dtype=float)
            cc_interp = interpolator(xs, ys, z, fillin=True)

            for name, df in filled_sheets.items():
                suffix = common_twl.parse_scenario_sheet_name(name)
                if suffix is None or suffix in coords or not suffix.startswith("_"):
                    continue  # skip known scenarios; only compare in-hull fills
                p, t = parse_scenario_name(suffix)
                row = df.loc[df["ID"] == save_point_id, ari]
                if row.empty:
                    continue
                filled_ft = row.iloc[0] * common_twl.METERS_TO_FEET
                cc_ft = cc_interp((p, t))
                rows.append({
                    "lake": lake,
                    "save_point_id": save_point_id,
                    "ari": ari,
                    "scenario": suffix,
                    "precip_delta": p,
                    "temp_delta": t,
                    "fillin_twl_ft": round(filled_ft, 4),
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
    "fillin_twl_ft (hydropattern's own Delaunay fill), climate_canvas_ft (climate_"
    "canvas's own interpolate+fillin over the same known points), and diff_ft "
    "(fillin_twl_ft - climate_canvas_ft). ARI values: "
    f"{', '.join(ari_constants.format_ari(a) for a in ARIS)}. See "
    "docs/filled_vs_climate_canvas_comparison.md for the write-up."
)

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def main(
    clean_data_dir: Path = typer.Argument(
        ..., help="Directory holding the known-scenario <lake>_twl.xlsx workbooks "
                   "(data/clean)."),
    filled_data_dir: Path = typer.Argument(
        ..., help="Directory holding the filled <lake>_twl.xlsx workbooks to "
                   "validate (data/filled)."),
    output_dir: Optional[Path] = typer.Argument(
        None, help="Directory to write the comparison CSV + README.txt to. "
                    "Defaults to <filled_data_dir>/img/comparison."),
) -> None:
    """Compare fillin_twl.py's in-hull fill against climate_canvas's own
    interpolate+fillin, and write a README.txt documenting the run (see
    run_readme.write_readme).
    """
    if output_dir is None:
        output_dir = resolve_default_output_dir(filled_data_dir)

    comparison = run(clean_data_dir, filled_data_dir)
    csv_path = write_comparison_csv(comparison, output_dir)

    inputs = [
        (f"{lake} known twl workbook", common_twl.resolve_lake_twl_path(lake, clean_data_dir))
        for lake in LAKES
    ] + [
        (f"{lake} filled twl workbook", common_twl.resolve_lake_twl_path(lake, filled_data_dir))
        for lake in LAKES
    ]
    if len(comparison):
        results_text = (
            f"n={len(comparison)}  max|diff|={comparison['diff_ft'].abs().max():.4f} ft  "
            f"mean|diff|={comparison['diff_ft'].abs().mean():.4f} ft"
        )
    else:
        results_text = "n=0 (no in-hull target scenarios found to compare)."

    workspace_root = Path(__file__).resolve().parents[4]
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


if __name__ == "__main__":
    app()
