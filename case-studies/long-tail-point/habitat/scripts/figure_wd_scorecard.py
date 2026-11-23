"""F5 WD scorecard: May-Aug median water depth over each woody debris (WD) structure end.

Rows = Jenny T8 structure ends (floor, ft IGLD85); columns = the five F3 scenarios.
Cell = median May-Aug lake level minus floor (ft), coloured by Jenny T7 musky depth ranges.
Lake levels convert m -> ft here only; no datum change (all IGLD85).

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_wd_scorecard.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_elevation_ladder import (  # type: ignore[import-not-found]  # noqa: E402
    M_TO_FT,
    WD_FLOORS_FT,
)

MONTHS = (5, 6, 7, 8)
SPAWN_LOW_FT, RECRUIT_HIGH_FT, SPAWN_HIGH_FT = 0.98, 1.97, 4.92  # Jenny T7

SCENARIOS = {
    "3 C dry\n(3C/0)": "_0_3",
    "1.5 C dry\n(1.5C/0)": "_0_1.5",
    "Baseline": "_0_0",
    "1.5 C wet\n(1.5C/5)": "_5_1.5",
    "3 C wet\n(3C/15)": "_15_3",
}
CLASS_COLORS = {
    "too shallow": "#d95f4b",
    "spawning + recruitment": "#4c9f70",
    "spawning only": "#9ecae1",
    "too deep": "#e8c15a",
}


def median_depth_ft(levels_m: pd.DataFrame, scenario: str, floor_ft: float) -> float:
    """Median May-Aug depth (ft) over a floor; levels in m, monthly, indexed by date string."""
    # Month parsed from the ISO string: the series runs past pandas' 2262 datetime limit.
    months = levels_m.index.str[5:7].astype(int)
    level_ft = levels_m.loc[months.isin(MONTHS), scenario] * M_TO_FT
    return float(level_ft.median() - floor_ft)


def depth_class(depth_ft: float) -> str:
    """Classify a depth against Jenny T7 musky ranges."""
    if depth_ft < SPAWN_LOW_FT:
        return "too shallow"
    if depth_ft <= RECRUIT_HIGH_FT:
        return "spawning + recruitment"
    if depth_ft <= SPAWN_HIGH_FT:
        return "spawning only"
    return "too deep"


def scorecard(levels_m: pd.DataFrame) -> pd.DataFrame:
    """Median May-Aug depth (ft): rows = structure ends, columns = scenario labels."""
    return pd.DataFrame(
        {
            label: {
                end: median_depth_ft(levels_m, code, floor) for end, floor in WD_FLOORS_FT.items()
            }
            for label, code in SCENARIOS.items()
        }
    )


def build_figure(levels_m: pd.DataFrame) -> plt.Figure:
    card = scorecard(levels_m)
    fig, ax = plt.subplots(figsize=(8, 5))
    for r, end in enumerate(card.index):
        for c, label in enumerate(card.columns):
            depth = card.loc[end, label]
            ax.add_patch(
                plt.Rectangle((c, r), 1, 1, fc=CLASS_COLORS[depth_class(depth)], ec="white", lw=2)
            )
            ax.text(c + 0.5, r + 0.5, f"{depth:.2f}", ha="center", va="center", fontsize=10)
    ax.set_xlim(0, len(card.columns))
    ax.set_ylim(len(card.index), 0)
    ax.set_xticks([c + 0.5 for c in range(len(card.columns))], list(card.columns))
    ax.xaxis.tick_top()
    for tick in ax.get_xticklabels():
        tick.set_verticalalignment("bottom")
    ax.set_yticks(
        [r + 0.5 for r in range(len(card.index))],
        [f"{end}  ({WD_FLOORS_FT[end]:.2f} ft)" for end in card.index],
    )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_ylabel("WD structure end (bottom elevation, ft IGLD85)")
    fig.legend(
        handles=[Patch(fc=c, label=k) for k, c in CLASS_COLORS.items()],
        loc="lower center",
        ncol=4,
        frameon=False,
        title="Median May-Aug depth over bottom elevation (ft), by musky depth range",
    )
    fig.subplots_adjust(bottom=0.16)
    return fig


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    fig = build_figure(pd.read_csv(habitat.levels_csv(layout), index_col="time"))
    typer.echo(f"Wrote {habitat.save_figure(fig, layout, 'F5')}")


if __name__ == "__main__":
    typer.run(main)
