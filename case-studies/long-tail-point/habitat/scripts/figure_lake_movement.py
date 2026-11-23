"""F1: how the lake moves. Change in mean Michigan-Huron level vs baseline (ft) for each
precipitation x warming scenario; the six robust-set scenarios are outlined, 5C/7C are
stress-test context. Levels convert m -> ft only; no datum change. (Warming plausibility
over time is covered in prose, not a figure.)

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_lake_movement.py
"""

import sys
from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_elevation_ladder import M_TO_FT  # type: ignore[import-not-found]  # noqa: E402

PRECIP_PCT = (0.0, 5.0, 10.0, 15.0, 20.0)
WARMING_C = (0.0, 1.5, 3.0, 5.0, 7.0)
ROBUST_SET = ("_0_1.5", "_5_1.5", "_0_3", "_5_3", "_10_3", "_15_3")
BASELINE = "_0_0"

def parse_scenario(code: str) -> tuple[float, float]:
    """'_P_T' -> (precipitation change %, warming C)."""
    _, precip, warming = code.split("_")
    return float(precip), float(warming)


def change_grid(levels_ft: Mapping[str, float]) -> pd.DataFrame:
    """Level change vs baseline (ft); rows = warming C, columns = precip %, NaN if no scenario."""
    grid = pd.DataFrame(np.nan, index=list(WARMING_C), columns=list(PRECIP_PCT))
    base = levels_ft[BASELINE]
    for code, level in levels_ft.items():
        precip, warming = parse_scenario(code)
        grid.loc[warming, precip] = level - base
    return grid


def build_figure(levels_m: pd.DataFrame) -> plt.Figure:
    levels = {s: float(levels_m[s].mean() * M_TO_FT) for s in levels_m.columns}
    grid = change_grid(levels)
    fig, ax = plt.subplots(figsize=(7, 4.8))

    arr = grid.to_numpy(dtype=float)
    limit = float(np.nanmax(np.abs(arr)))
    image = ax.imshow(arr, cmap="RdBu", vmin=-limit, vmax=limit, origin="lower", aspect="auto")
    for i, warming in enumerate(WARMING_C):
        for j, precip in enumerate(PRECIP_PCT):
            value = arr[i, j]
            if np.isnan(value):
                continue
            ax.text(j, i, f"{value:+.1f}" if value else "0", ha="center", va="center",
                    fontsize=9, fontweight="bold" if _is_robust(precip, warming) else None,
                    color="white" if abs(value) > 5 else "black")
            if _is_robust(precip, warming):
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="black", lw=2))
    ax.set_xticks(range(len(PRECIP_PCT)), [f"+{p:g}%" for p in PRECIP_PCT])
    ax.set_yticks(range(len(WARMING_C)), [f"+{w:g} C" for w in WARMING_C])
    ax.set_xlabel("Precipitation change")
    ax.set_ylabel("Warming")
    ax.set_title(f"Mean lake-level change vs baseline ({levels[BASELINE]:.2f} ft IGLD85)",
                 fontsize=10)
    fig.colorbar(image, ax=ax, label="Change in mean level (ft)", fraction=0.046, pad=0.03)
    ax.text(0.0, -0.2, "Outlined = robust set (the six scenarios judged for robustness); "
            "5C and 7C = stress-test context.", transform=ax.transAxes, fontsize=7)

    fig.tight_layout()
    return fig


def _is_robust(precip: float, warming: float) -> bool:
    return f"_{precip:g}_{warming:g}" in ROBUST_SET


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    fig = build_figure(pd.read_csv(habitat.levels_csv(layout), index_col="time"))
    typer.echo(f"Wrote {habitat.save_figure(fig, layout, 'F1')}")


if __name__ == "__main__":
    typer.run(main)
