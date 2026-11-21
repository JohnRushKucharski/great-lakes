"""F7 hydrographs: monthly and 12-month mean lake level for three scenarios (habitat memo).

Shows what a low-water or high-water cycle looks like: the trailing 12-month mean (thick line)
against the low-water band and high-water threshold used in F8. A 200-year window (the first
200 years of each scenario record) in feet, IGLD85.

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_hydrograph.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

LEVELS_CSV = habitat.levels_csv(Layout())

M_TO_FT = 1 / 0.3048
LOW_BAND_M = (175.90, 176.30)
HIGH_M = 176.75
WINDOW_YEARS = 200
PANELS = (
    ("_0_0", "Baseline (no change)"),
    ("_0_3", "+3 C, precipitation +0%"),
    ("_15_3", "+3 C, precipitation +15%"),
)


def window_series(levels: pd.Series, years: int) -> pd.DataFrame:
    """First `years` years as monthly and trailing 12-month mean levels (ft), indexed by year."""
    series = levels.iloc[: years * 12]
    smoothed = series.rolling(12, min_periods=12).mean()
    year = [int(t[:4]) + (int(t[5:7]) - 1) / 12 for t in series.index]
    return pd.DataFrame(
        {"monthly": series.to_numpy() * M_TO_FT, "mean12": smoothed.to_numpy() * M_TO_FT},
        index=year,
    )


def build_figure(levels: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(len(PANELS), 1, figsize=(10, 7), sharex=False, sharey=True)
    low = [m * M_TO_FT for m in LOW_BAND_M]
    for ax, (name, title) in zip(axes, PANELS, strict=True):
        data = window_series(levels[name], WINDOW_YEARS)
        ax.plot(data.index, data["monthly"], color="#b0b8c4", lw=0.5, label="Monthly level")
        ax.plot(data.index, data["mean12"], color="#1f4e79", lw=1.2, label="12-month mean")
        ax.axhspan(*low, color="#d9822b", alpha=0.25, label="Low-water band (24-60 months)")
        ax.axhline(HIGH_M * M_TO_FT, color="#b22222", ls="--", lw=1,
                   label="High-water threshold (>= 24 months)")
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_ylabel("Lake level (ft, IGLD85)")
        ax.margins(x=0)
    axes[-1].set_xlabel(f"Year (first {WINDOW_YEARS} years of each scenario record)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.suptitle("Monthly lake level and 12-month mean: low- and high-water cycles", fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    levels = pd.read_csv(habitat.levels_csv(layout), index_col="time")
    typer.echo(f"Wrote {habitat.save_figure(build_figure(levels), layout, 'F7')}")


if __name__ == "__main__":
    typer.run(main)
