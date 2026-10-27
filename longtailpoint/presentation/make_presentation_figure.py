"""Regenerate a presentation-friendly copy of one save-point threshold-ARI elevation
figure from its existing grid csv (see batch_twl_output/baseline/savepoint<id>_ari<ari>
_elevation_grid.csv), with changes suited to slides:

- colorbar ticks and grid-pixel value labels rounded to 1 decimal (vs. the batch
  output's 2 decimals).
- grid-pixel value labels drawn larger (14pt vs. climate_canvas's hardcoded 7pt).
- plot title drawn larger (18pt vs. matplotlib's default axes.titlesize).

Doesn't touch climate_canvas or the original baseline outputs -- reads the existing
grid csv, re-renders through climate_canvas's own _render_surface (identical
pcolormesh/contour/labeling logic as batch_run_twl.py's original call), then
overrides just the label/title font sizes and colorbar tick formatting before saving
to a new path.

Usage: python make_presentation_figure.py <save_point_id> <ari> <out_stem>
Example: python make_presentation_figure.py 4999 15 4999_ari15_elevation
    reads  ../batch_twl_output/baseline/savepoint4999_ari15_elevation_grid.csv
    writes ./4999_ari15_elevation.png (grid csv is copied separately, see README)
"""
import shutil
import sys
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt
from climate_canvas.plots_utilities import _render_surface  # type: ignore[import-untyped]
from hydropattern.cli import write_grid_csv  # type: ignore[import-untyped]

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from great_lakes import common_twl  # noqa: E402

LABEL_FONTSIZE = 16
TITLE_FONTSIZE = 18
TICK_DECIMALS = 1

BASELINE_DIR = Path(__file__).resolve().parent.parent / "batch_twl_output" / "baseline"


def read_grid_csv(path: Path):
    """Read a write_grid_csv-format grid (rows=temp deltas, columns=precip deltas)
    back into (xs, ys, zs) as plot_response_surface/_render_surface expect."""
    df = pd.read_csv(path, index_col=0)
    xs = df.columns.astype(float).to_numpy()
    ys = df.index.astype(float).to_numpy()
    zs = df.to_numpy()
    return xs, ys, zs


def build_presentation_figure(
    save_point_id: str, ari: float, out_stem: str, out_dir: Path,
    elevation_offset_ft: float = 0.0,
) -> Path:
    """elevation_offset_ft: added to every (non-NaN) grid cell before plotting/saving
    -- e.g. a runup allowance on top of the raw threshold-ARI elevation grid. The
    written csv reflects the offset elevations, not the original baseline grid."""
    grid_path = BASELINE_DIR / f"savepoint{save_point_id}_ari{ari:g}_elevation_grid.csv"
    xs, ys, zs = read_grid_csv(grid_path)
    if elevation_offset_ft:
        zs = zs + elevation_offset_ft

    baseline_ft = float(zs[list(ys).index(0.0), list(xs).index(0.0)])
    z_range = (float(zs[~pd.isna(zs)].min()), float(zs[~pd.isna(zs)].max()))
    # one_sided_color_style returns None for the normal two-sided case (baseline_ft
    # strictly inside z_range) -- then leave norm/levels/widths unset so
    # _render_surface computes its own RdBu/TwoSlopeNorm defaults, matching the
    # original batch plot's color scheme exactly; only override them (Reds_r/Blues)
    # when every cell falls on one side of baseline_ft, same as the original call.
    style = common_twl.one_sided_color_style(z_range, baseline_ft)
    color_map = style[0] if style is not None else "RdBu"
    norm = style[1] if style is not None else None
    levels = style[2] if style is not None else None
    widths = style[3] if style is not None else None
    title = common_twl.build_threshold_ari_title(ari, save_point_id)
    if elevation_offset_ft:
        # Append the runup allowance to the title's 2nd line ("ARI: <n> yr"), so a
        # runup variant is visually distinguishable from the plain elevation plot.
        lines = title.split("\n")
        lines[1] += f", +{elevation_offset_ft:g}ft runup"
        title = "\n".join(lines)

    fig, ax = plt.subplots(figsize=(10, 10))
    im, _, levels, threshold_given = _render_surface(
        ax, xs, ys, zs,
        labels=("Precipitation Delta (%)", "Temperature Delta (C)", "Elevation (ft, NAVD88)"),
        title=title, threshold=baseline_ft, color_map=color_map,
        norm=norm, levels=levels, widths=widths,
        show_values=True, value_decimals=TICK_DECIMALS,
    )
    # Round whichever levels _render_surface ended up using (its own computed
    # defaults, or style's one-sided ones) to TICK_DECIMALS for the colorbar ticks.
    levels = tuple(round(level, TICK_DECIMALS) for level in levels)
    # climate_canvas hardcodes cell-label fontsize=7; bump for slide legibility.
    for text in ax.texts:
        text.set_fontsize(LABEL_FONTSIZE)
    ax.title.set_fontsize(TITLE_FONTSIZE)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Elevation (ft, NAVD88)")
    cbar.set_ticks(levels)  # levels already rounded to TICK_DECIMALS

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{out_stem}.png"
    fig.savefig(out_path)
    plt.close(fig)

    csv_path = out_dir / f"{out_stem}.csv"
    if elevation_offset_ft:
        write_grid_csv(xs, ys, zs, csv_path)
    else:
        shutil.copy(grid_path, csv_path)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        raise SystemExit(
            f"Usage: {sys.argv[0]} <save_point_id> <ari> <out_stem> [elevation_offset_ft]"
        )
    save_point_id, ari, out_stem = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    offset = float(sys.argv[4]) if len(sys.argv) == 5 else 0.0
    result = build_presentation_figure(
        save_point_id, ari, out_stem, Path(__file__).resolve().parent,
        elevation_offset_ft=offset,
    )
    print(f"Wrote {result} and {result.with_suffix('.csv')}")
