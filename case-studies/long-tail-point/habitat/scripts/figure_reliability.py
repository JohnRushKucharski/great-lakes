"""F6 reliability heatmap: habitat reliability by floor elevation for focus scenarios.

Rows: musky juvenile / spawning / recruitment and pondweed growing season / winter survival.
Columns: floor elevation (ft IGLD85). One panel per focus scenario; cell color = reliability
class, printed value = % of years (recruitment: % of rolling 5-year windows). Inputs are the
CSVs written by `musky_runs.py` and `pondweed_runs.py`. Floors are only run over each
species' native range (musky 573-579, pondweed 571-577); other cells are grey n/a.

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_reliability.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

FLOORS_FT = tuple(float(f) for f in range(571, 580))
ROWS = [
    ("juvenile_habitat", "Musky\njuvenile"),
    ("spawning_zones", "Musky\nspawning"),
    ("recruitment_zones", "Musky\nrecruitment"),
    ("growing_season_habitat", "Pondweed\ngrowing season"),
    ("winter_survival", "Pondweed\nwinter survival"),
]
# Same order as F3: baseline, wet scenarios, dry scenarios.
PANELS = {
    "_0_0": "Baseline",
    "_5_1.5": "1.5 C wet (1.5C/5)",
    "_15_3": "3 C wet (3C/15)",
    "_0_1.5": "1.5 C dry (1.5C/0)",
    "_0_3": "3 C dry (3C/0)",
}
CLASS_CODES = {"unreliable": 1, "marginal": 2, "reliable": 3}
CLASS_COLORS = {"unreliable": "#d6604d", "marginal": "#f4d35e", "reliable": "#5fa86b"}


def reliability_class(component: str, pct: float) -> str | None:
    """Reliable >= 75%, marginal 50-75%, unreliable < 50%; recruitment cuts are 8% and 4%."""
    if np.isnan(pct):
        return None
    reliable, marginal = (8.0, 4.0) if component == "recruitment_zones" else (75.0, 50.0)
    return "reliable" if pct >= reliable else "marginal" if pct >= marginal else "unreliable"


def scenario_matrix(results: pd.DataFrame, scenario: str) -> pd.DataFrame:
    """Percentages with rows = component, columns = floor (NaN where not run)."""
    subset = results[results["Scenario"] == scenario]
    wide = subset.pivot(index="Component", columns="Floor (ft IGLD85)", values="Percentage")
    return wide.reindex(index=[key for key, _ in ROWS], columns=list(FLOORS_FT))


def build_figure(results: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.2))
    cmap = ListedColormap(["#e0e0e0", *(CLASS_COLORS[c] for c in CLASS_CODES)])
    # Legend sits bottom-left (under baseline); dry panels fill the bottom row to its right.
    positions = [(0, 0), (0, 1), (0, 2), (1, 1), (1, 2)]
    for (row, col), (scenario, title) in zip(positions, PANELS.items(), strict=True):
        ax = axes[row, col]
        matrix = scenario_matrix(results, scenario).to_numpy(dtype=float)
        codes = np.zeros(matrix.shape)
        for i, (key, _) in enumerate(ROWS):
            for j in range(len(FLOORS_FT)):
                pct = matrix[i, j]
                cls = reliability_class(key, pct)
                codes[i, j] = CLASS_CODES.get(cls, 0) if cls else 0
                ax.text(j + 0.5, i + 0.5, "" if cls is None else f"{pct:.0f}", ha="center",
                        va="center", fontsize=9)
        ax.pcolormesh(codes, cmap=cmap, vmin=0, vmax=3, edgecolors="white", linewidth=1)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(np.arange(len(FLOORS_FT)) + 0.5, [f"{f:.0f}" for f in FLOORS_FT],
                      fontsize=9)
        ax.set_yticks(np.arange(len(ROWS)) + 0.5, [label for _, label in ROWS], fontsize=9)
        ax.invert_yaxis()
    for ax in (*axes[0], *axes[1, 1:]):
        ax.set_xlabel("Bottom elevation (ft, IGLD85)", fontsize=9)
    legend_ax = axes[1, 0]
    legend_ax.axis("off")
    handles = [
        Patch(color=CLASS_COLORS["reliable"], label="Reliable (>= 75% of years)"),
        Patch(color=CLASS_COLORS["marginal"], label="Marginal (50-75%)"),
        Patch(color=CLASS_COLORS["unreliable"], label="Unreliable (< 50%)"),
        Patch(color="#e0e0e0", label="Not run"),
        Patch(color="none",
              label="Recruitment: % of 5-yr\nwindows; reliable >= 8%,\nmarginal 4-8%"),
    ]
    legend_ax.legend(handles=handles, loc="center left", fontsize=8, frameon=False,
                     bbox_to_anchor=(0.0, 0.5))
    fig.suptitle("Habitat reliability by bottom elevation (% of years in each scenario)",
                 fontsize=11)
    fig.tight_layout()
    return fig


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    fig = build_figure(habitat.reliability_results(layout))
    typer.echo(f"Wrote {habitat.save_figure(fig, layout, 'F6')}")


if __name__ == "__main__":
    typer.run(main)
