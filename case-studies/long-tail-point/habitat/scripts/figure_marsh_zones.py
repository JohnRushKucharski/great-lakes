"""F4 marsh-zone share by scenario (heatmap) + Jenny's own 3C dry / 3C wet depth maps.

Share of the 288 survey points inside each Jenny marsh-zone depth range, per scenario
(baseline + robust set, ordered dry -> wet by mean lake level). Zones overlap, so columns do
not sum to 100%. Unrooted floating (any depth) is omitted, as in F3. The two depth maps
(F4B 3C/0, F4C 3C/15) are copied unchanged from Jenny's memo, not redrawn.

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_marsh_zones.py
"""

import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_elevation_ladder import (  # type: ignore[import-not-found]  # noqa: E402
    M_TO_FT,
    SURVEY_XLSX,
    ZONE_DEPTHS_FT,
)

LEVELS_CSV = habitat.levels_csv(Layout())
ZONES = tuple(ZONE_DEPTHS_FT)

HEATMAP_SCENARIOS = {
    "_0_0": "Baseline",
    "_0_1.5": "1.5C/0",
    "_5_1.5": "1.5C/5",
    "_0_3": "3C/0",
    "_5_3": "3C/5",
    "_10_3": "3C/10",
    "_15_3": "3C/15",
}
JENNY_MAPS_DIR = habitat.jenny_maps_dir(Layout())
# Jenny's own survey-point depth maps (her memo Figs 7 and 8), tracked as inputs.
JENNY_MAPS = ("F4B", "F4C")


def zone_shares(bottoms_ft: np.ndarray, level_ft: float) -> pd.Series:
    """Fraction of survey points in each marsh-zone depth range (inclusive) at level_ft."""
    depths = level_ft - np.asarray(bottoms_ft, dtype=float)
    eps = 1e-6  # floating-point noise only; boundary points count as inside
    return pd.Series(
        {z: float(((depths >= lo - eps) & (depths <= hi + eps)).mean()) for z, (lo, hi) in
         ZONE_DEPTHS_FT.items()}
    )


def order_by_level(levels_ft: Mapping[str, float]) -> list[str]:
    """Scenario codes sorted from lowest to highest mean level (dry -> wet)."""
    return sorted(levels_ft, key=lambda s: levels_ft[s])


def mean_levels_ft(levels_m: pd.DataFrame) -> dict[str, float]:
    """Mean monthly level (ft) per scenario column; input in m, no datum change."""
    return {s: float(levels_m[s].mean() * M_TO_FT) for s in levels_m.columns}


def save_point_elevations(path: Path = SURVEY_XLSX) -> np.ndarray:
    """Bottom elevations (ft IGLD85) of the Dead Horse Bay survey points, from depth_analysis."""
    sheet = pd.read_excel(path, sheet_name="depth_analysis")
    return sheet["Estimated Bottom elevation (ft)"].dropna().to_numpy(dtype=float)


def copy_jenny_maps(out_dir: Path, src_dir: Path = JENNY_MAPS_DIR) -> list[Path]:
    """Copy Jenny's depth-map images unchanged from the tracked inputs to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fig_id in JENNY_MAPS:
        target = out_dir / f"{fig_id}.png"
        shutil.copyfile(src_dir / f"{fig_id}.png", target)
        written.append(target)
    return written


def build_figure(levels_m: pd.DataFrame, bottoms_ft: np.ndarray) -> plt.Figure:
    levels = mean_levels_ft(levels_m)
    scenarios = order_by_level({s: levels[s] for s in HEATMAP_SCENARIOS})
    shares = pd.DataFrame({s: zone_shares(bottoms_ft, levels[s]) for s in scenarios})
    fig, ax = plt.subplots(figsize=(8, 4.2))
    values = shares.to_numpy(dtype=float) * 100
    ax.imshow(values, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=8,
                    color="white" if values[i, j] > 60 else "black")
    ax.set_xticks(range(len(scenarios)), [
        f"{HEATMAP_SCENARIOS[s]}\n{levels[s]:.1f} ft" for s in scenarios], fontsize=8)
    ax.set_yticks(range(len(ZONES)), [
        f"{z} ({lo:g}-{hi:g} ft)" for z, (lo, hi) in ZONE_DEPTHS_FT.items()], fontsize=8)
    ax.set_title("Survey points in each marsh zone (% of 288), by scenario", fontsize=10)
    return fig


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    levels = pd.read_csv(habitat.levels_csv(layout), index_col="time")
    fig = build_figure(levels, save_point_elevations(habitat.survey_xlsx(layout)))
    typer.echo(f"Wrote {habitat.save_figure(fig, layout, 'F4')}")
    copy_jenny_maps(habitat.figures_dir(layout), habitat.jenny_maps_dir(layout))
    habitat.refresh_figures_readme(layout)


if __name__ == "__main__":
    typer.run(main)
