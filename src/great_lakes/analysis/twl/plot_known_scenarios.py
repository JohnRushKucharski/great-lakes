"""Plot TWL response surfaces for a center save point on each lake, in feet.

For each of the 4 Great Lakes twl workbooks in data_dir (5 **known** scenarios
only -- no filled/interpolated/extrapolated sheets), picks the save point nearest the
lake's centroid (mean lat/lon over all its save points -- see
common_twl.center_save_point_id) and plots climate_canvas's response surface --
precip_delta (x) vs temp_delta (y), colored by TWL in **feet** -- for every ARI column
in ari_constants.TWL_ARIS. Two plots per lake/ARI:

- `<lake>_<ari>.png`: interpolation OFF -- only the 5 known precip/temp cells are
  colored, everything else left blank.
- `interpolated/<lake>_<ari>.png`: climate_canvas's own `--interp`/`--fillin`
  features on -- the known cells are linearly resampled to a finer grid, and the
  cells outside the known scenarios' convex hull (which linear resampling alone
  leaves blank) are estimated via climate_canvas's own Delaunay-linear fillin. This
  is independent of (and does not use) hydropattern's own fillin_twl.py row-shift
  extrapolation in data/filled or data/extrapolated -- it is climate_canvas
  resampling the same 5 known-scenario points shown in the first plot.

The colormap threshold (its centered/diverging color) is that lake's baseline
scenario (`_0_0`) average lake level -- i.e. today's average water level under that
same scenario -- read from `<avg-lake>_avg.csv` in data_dir, converted to feet, same
threshold for both plots and all ARIs of a given lake. The threshold value is also
shown in the plot title.

Writes all PNGs, plus a README.txt (see run_readme.write_readme), to output_dir
(default: `<data_dir>/img/twl/known` -- see resolve_default_output_dir).

## Usage

    uv run python -m great_lakes.analysis.twl.plot_known_scenarios <data_dir> [output_dir]
"""

from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from climate_canvas.plots_utilities import plot_response_surface  # type: ignore[import-untyped]

from great_lakes import ari_constants, common_twl, run_readme
from great_lakes.fillin_twl import known_scenario_coords

LAKES = tuple(common_twl.LAKE_TWL_FILENAMES)
ARIS = ari_constants.TWL_ARIS


def resolve_default_output_dir(data_dir: Path) -> Path:
    """Default output_dir when the CLI's output_dir argument is omitted: a
    `img/twl/known` subfolder of data_dir (normally data/clean) -- see
    docs/data_pipelines.md.
    """
    return data_dir / "img" / "twl" / "known"


def _write_pair(xs, ys, zs, title: str, directory: Path, filename: str,
                threshold: float) -> tuple[Path, Path]:
    """Write both the raw (interpolate=False) plot and its interpolated
    (interpolate=True, fillin=True) companion into `directory` and
    `directory/interpolated`, both named `<filename>.png`.
    """
    labels = ("precip_delta", "temp_delta", "TWL (ft)")
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


def run(data_dir: Path, output_dir: Path) -> tuple[Path, ...]:
    """Generate every known-scenario TWL response-surface plot for every lake in
    LAKES/ARI in ARIS, under output_dir (with a sibling interpolated/ subfolder).
    Returns every file written.
    """
    written: list[Path] = []
    for lake in LAKES:
        path = common_twl.resolve_lake_twl_path(lake, data_dir)
        sheets = pd.read_excel(path, sheet_name=None)
        save_point_id = common_twl.center_save_point_id(sheets)

        avg_means = common_twl.read_avg_scenario_means(lake, data_dir)
        baseline_avg_ft = avg_means["_0_0"] * common_twl.METERS_TO_FEET

        coords = known_scenario_coords(list(sheets.keys()))

        for ari in ARIS:
            ari_label = ari_constants.format_ari(ari)
            xs, ys, zs = common_twl.build_scenario_ari_grid(coords, sheets, save_point_id, ari)
            title = (f"{lake.capitalize()} save point {save_point_id} -- ARI={ari_label} "
                      f"(baseline average lake level={baseline_avg_ft:.2f} ft)")
            written.extend(_write_pair(
                xs, ys, zs, title, output_dir, f"{lake}_{ari_label}", baseline_avg_ft,
            ))
    return tuple(written)


_NAMING_SCHEME_TEXT = (
    "<lake>_<ari>.png - known-scenario TWL response surface (only the 5 known "
    "precip/temp cells colored, interpolate=False).\n"
    "interpolated/<lake>_<ari>.png - same, climate_canvas interpolate+fillin "
    "resampled (Delaunay-linear fillin outside the known scenarios' convex hull).\n"
    "ARI values follow ari_constants.TWL_ARIS (all 13 workbook columns)."
)

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def main(
    data_dir: Path = typer.Argument(
        ..., help="Directory holding the clean <lake>_twl.xlsx workbooks and "
                   "<avg-lake>_avg.csv files (data/clean)."),
    output_dir: Optional[Path] = typer.Argument(
        None, help="Directory to write plots + README.txt to. Defaults to "
                    "<data_dir>/img/twl/known."),
) -> None:
    """Plot known-scenario TWL response surfaces for every lake's centroid save
    point, and write a README.txt documenting the run (see run_readme.write_readme).
    """
    if output_dir is None:
        output_dir = resolve_default_output_dir(data_dir)

    written = run(data_dir, output_dir)

    inputs = [
        (f"{lake} twl workbook", common_twl.resolve_lake_twl_path(lake, data_dir))
        for lake in LAKES
    ]
    workspace_root = Path(__file__).resolve().parents[4]
    run_readme.write_readme(
        output_directory=output_dir,
        title="Known-scenario TWL analysis report",
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
