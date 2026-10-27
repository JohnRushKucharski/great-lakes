"""Plot SWL response surfaces (like plot_known_scenarios.py) for a data_dir holding
already-filled/extrapolated `<lake>_swl.xlsx` workbooks (data/filled or
data/extrapolated), using their own actual values (no climate_canvas
interpolation/fillin -- these directories already hold hydropattern's own
fillin_swl.py fill/extrapolation for every scenario cell they have).

Same centroid save point per lake (common_swl.center_save_point_id), same 13 ARI
columns present in every SWL workbook (ari_constants.SWL_ARIS), same threshold
(baseline `_0_0` average lake level from a `clean`-sibling data dir, in feet) as
plot_known_scenarios.py.

- data/filled/: 12 of 17 scenarios present (5 known + 7 in-hull filled); the 5
  out-of-hull cells are left blank (NaN).
- data/extrapolated/: all 17 scenarios present (also includes the 5 out-of-hull
  row-shift extrapolated cells) -- full grid, no blanks.

Writes `<lake>_<ari>.png` (raw actual values, interpolate=False) and
`interpolated/<lake>_<ari>.png` (climate_canvas's own interpolate=True,
fillin=True over the same actual cell values -- resampled to a finer grid,
Delaunay-fillin for any remaining NaN, e.g. data/filled/'s 5 missing
out-of-hull cells), plus a README.txt (see run_readme.write_readme), to
output_dir (default: `<data_dir>/img` -- see resolve_default_output_dir).

## Usage

    uv run python -m great_lakes.analysis.swl.plot_filled_and_extrapolated \\
        <data_dir> [output_dir] [--avg-data-dir DIR]

Run once per data_dir (data/filled, then data/extrapolated) -- see
docs/data_pipelines.md for the combined regeneration script.
"""

from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from climate_canvas.plots_utilities import plot_response_surface  # type: ignore[import-untyped]
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]

from great_lakes import ari_constants, common_swl, run_readme
from great_lakes.fillin_swl import ALL_SCENARIO_SUFFIXES

LAKES = tuple(common_swl.LAKE_SWL_FILENAMES)
ARIS = ari_constants.SWL_ARIS

# All 17 scenarios' (precip, temp) coords, keyed by bare suffix, e.g. "_0_0" -> (0., 0.)
ALL_COORDS = {suffix: parse_scenario_name(suffix) for suffix in ALL_SCENARIO_SUFFIXES}


def resolve_default_output_dir(data_dir: Path) -> Path:
    """Default output_dir when the CLI's output_dir argument is omitted: an `img`
    subfolder of data_dir itself (data/filled/img or data/extrapolated/img) -- see
    docs/data_pipelines.md.
    """
    return data_dir / "img"


def resolve_default_avg_data_dir(data_dir: Path) -> Path:
    """Default avg_data_dir when the CLI's --avg-data-dir option is omitted: the
    `clean` sibling of data_dir (data/filled and data/extrapolated are both
    siblings of data/clean, which alone holds the `<avg-lake>_avg.csv` baseline
    files).
    """
    return data_dir.parent / "clean"


def _write_pair(xs, ys, zs, title: str, directory: Path, filename: str,
                threshold: float) -> tuple[Path, Path]:
    """Write both the raw (interpolate=False) plot and its interpolated
    (interpolate=True, fillin=True) companion into `directory` and
    `directory/interpolated`, both named `<filename>.png`.
    """
    labels = ("precip_delta", "temp_delta", "SWL (ft)")
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"{filename}.png"
    plot_response_surface(
        xs, ys, zs, interpolate=False, labels=labels, title=title,
        save_path=raw_path, show=False, threshold=threshold,
    )

    interpolated_dir = directory / "interpolated"
    interpolated_dir.mkdir(parents=True, exist_ok=True)
    interpolated_path = interpolated_dir / f"{filename}.png"
    plot_response_surface(
        xs, ys, zs, interpolate=True, fillin=True, labels=labels, title=title,
        save_path=interpolated_path, show=False, threshold=threshold,
    )
    return raw_path, interpolated_path


def run(data_dir: Path, output_dir: Path, avg_data_dir: Path) -> tuple[Path, ...]:
    """Generate every filled/extrapolated SWL response-surface plot for every lake
    in LAKES/ARI in ARIS, under output_dir (with a sibling interpolated/ subfolder).
    Returns every file written.
    """
    written: list[Path] = []
    for lake in LAKES:
        path = common_swl.resolve_lake_swl_path(lake, data_dir)
        sheets = pd.read_excel(path, sheet_name=None)
        save_point_id = common_swl.center_save_point_id(sheets)

        avg_means = common_swl.read_avg_scenario_means(lake, avg_data_dir)
        baseline_avg_ft = avg_means["_0_0"] * common_swl.METERS_TO_FEET

        for ari in ARIS:
            ari_label = ari_constants.format_ari(ari)
            xs, ys, zs = common_swl.build_scenario_ari_grid(ALL_COORDS, sheets, save_point_id, ari)
            title = (f"{lake.capitalize()} save point {save_point_id} -- ARI={ari_label} "
                      f"(baseline average lake level={baseline_avg_ft:.2f} ft)")
            written.extend(_write_pair(
                xs, ys, zs, title, output_dir, f"{lake}_{ari_label}", baseline_avg_ft,
            ))
    return tuple(written)


_NAMING_SCHEME_TEXT = (
    "<lake>_<ari>.png - raw actual-value SWL response surface (interpolate=False; "
    "NaN wherever data_dir's workbook has no sheet for that scenario, e.g. "
    "data/filled/'s 5 out-of-hull gaps).\n"
    "interpolated/<lake>_<ari>.png - same, climate_canvas interpolate+fillin "
    "resampled (Delaunay-linear fillin for any remaining NaN cell).\n"
    "ARI values follow ari_constants.SWL_ARIS (all 13 workbook columns)."
)

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def main(
    data_dir: Path = typer.Argument(
        ..., help="Directory holding the <lake>_swl.xlsx workbooks to plot "
                   "(data/filled or data/extrapolated)."),
    output_dir: Optional[Path] = typer.Argument(
        None, help="Directory to write plots + README.txt to. Defaults to "
                    "<data_dir>/img."),
    avg_data_dir: Optional[Path] = typer.Option(
        None, "--avg-data-dir",
        help="Directory holding <avg-lake>_avg.csv files for the baseline "
             "threshold. Defaults to a 'clean' sibling of data_dir."),
) -> None:
    """Plot filled/extrapolated SWL response surfaces for every lake's centroid
    save point, and write a README.txt documenting the run (see
    run_readme.write_readme).
    """
    if output_dir is None:
        output_dir = resolve_default_output_dir(data_dir)
    if avg_data_dir is None:
        avg_data_dir = resolve_default_avg_data_dir(data_dir)

    written = run(data_dir, output_dir, avg_data_dir)

    inputs = [
        (f"{lake} swl workbook", common_swl.resolve_lake_swl_path(lake, data_dir))
        for lake in LAKES
    ]
    inputs.append(("avg data directory", avg_data_dir))
    workspace_root = Path(__file__).resolve().parents[4]
    run_readme.write_readme(
        output_directory=output_dir,
        title="Filled/extrapolated SWL analysis report",
        inputs=inputs,
        results_text=f"Wrote {len(written)} plot file(s) across {len(LAKES)} lake(s).",
        naming_scheme_text=_NAMING_SCHEME_TEXT,
        written_paths=written,
        workspace_root=workspace_root,
    )
    for path in written:
        print(f"Wrote {path}")


if __name__ == "__main__":
    app()
