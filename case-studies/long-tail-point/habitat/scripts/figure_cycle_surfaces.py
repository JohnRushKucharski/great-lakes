"""F8 cycle-rate surfaces: low- and high-water cycles per 100 years, by scenario (habitat memo).

A cycle is one maximal run of months whose trailing 12-month mean level stays in a magnitude
band for a number of months in a duration range (whole runs only). Definitions follow the
`low_water_cycles` and `high_water_cycles` notebooks (`methods/`):
  low  = 175.90-176.30 m, 24-60 months;  high = >= 176.75 m (~579.9 ft), >= 24 months.
Levels stay in meters here (source units, IGLD85); only the axis labels add feet. The first
11 months have no trailing mean and cannot start a cycle. Each scenario's full record (1,030
years) is the exposure. Cells show the rate; color shows the change from baseline.

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_cycle_surfaces.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

LEVELS_CSV = habitat.levels_csv(Layout())

MEAN_MONTHS = 12
M_TO_FT = 1 / 0.3048
# name: (lower m, upper m or None, min months, max months or None)
CYCLES = {
    "Low-water cycles": (175.90, 176.30, 24, 60),
    "High-water cycles": (176.75, None, 24, None),
}
ROBUST_SET = ("_0_1.5", "_5_1.5", "_0_3", "_5_3", "_10_3", "_15_3")


def count_cycle_events(
    levels: pd.Series,
    lower: float,
    upper: float | None,
    mean_months: int,
    min_months: int,
    max_months: int | None,
) -> int:
    """Count whole runs whose trailing mean is within the band for the allowed duration."""
    smoothed = levels.rolling(mean_months, min_periods=mean_months).mean()
    inside = smoothed.ge(lower) if upper is None else smoothed.between(lower, upper)
    count = 0
    run = 0
    for flag in [*inside.to_numpy(), False]:
        if flag:
            run += 1
            continue
        if run >= min_months and (max_months is None or run <= max_months):
            count += 1
        run = 0
    return count


def cycle_rate(
    levels: pd.Series,
    lower: float,
    upper: float | None,
    mean_months: int,
    min_months: int,
    max_months: int | None,
) -> float:
    """Cycles per 100 years of record."""
    events = count_cycle_events(levels, lower, upper, mean_months, min_months, max_months)
    return 100 * events / (len(levels) / 12)


def parse_scenario(name: str) -> tuple[float, float]:
    """'_P_T' -> (precipitation %, warming C)."""
    _, precip, warming = name.split("_")
    return float(precip), float(warming)


def rate_grid(rates: dict[str, float]) -> pd.DataFrame:
    """Rates with rows = warming (C), columns = precipitation change (%); NaN where no run."""
    grid = pd.DataFrame(dtype=float)
    for name, rate in rates.items():
        precip, warming = parse_scenario(name)
        grid.loc[warming, precip] = rate
    return grid.sort_index().sort_index(axis=1)


def scenario_rates(levels: pd.DataFrame, definition: tuple) -> dict[str, float]:
    lower, upper, min_months, max_months = definition
    return {
        name: cycle_rate(levels[name], lower, upper, MEAN_MONTHS, min_months, max_months)
        for name in levels.columns
    }


def build_figure(levels: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, (title, definition) in zip(axes, CYCLES.items(), strict=True):
        rates = scenario_rates(levels, definition)
        grid = rate_grid(rates)
        baseline = rates["_0_0"]
        values = grid.to_numpy(dtype=float)
        span = max(np.abs(values[~np.isnan(values)] - baseline).max(), 1e-9)
        norm = TwoSlopeNorm(vcenter=baseline, vmin=baseline - span, vmax=baseline + span)
        masked = np.ma.masked_invalid(values)
        cmap = plt.get_cmap("RdBu")
        ax.pcolormesh(masked, cmap=cmap, norm=norm, edgecolors="white", linewidth=1.5)
        ax.set_facecolor("#eeeeee")
        for i, warming in enumerate(grid.index):
            for j, precip in enumerate(grid.columns):
                value = grid.iloc[i, j]
                if not np.isnan(value):
                    is_baseline = warming == 0 and precip == 0
                    dark = sum(cmap(norm(value))[:3]) < 1.6
                    ax.text(j + 0.5, i + 0.5, f"{value:.1f}", ha="center", va="center",
                            fontsize=10, color="white" if dark else "black",
                            fontweight="bold" if is_baseline else "normal")
        ax.set_xticks(np.arange(len(grid.columns)) + 0.5, [f"+{p:g}%" for p in grid.columns])
        ax.set_yticks(np.arange(len(grid.index)) + 0.5, [f"+{w:g} C" for w in grid.index])
        ax.set_xlabel("Precipitation change")
        ax.set_title(f"{title} per 100 years (baseline {baseline:.1f})", fontsize=11)
        ax.tick_params(length=0)
    axes[0].set_ylabel("Warming")
    fig.suptitle("How often the lake enters multi-year low- and high-water cycles, "
                 "by scenario", fontsize=11)
    fig.text(0.5, 0.01, "Red: less often than baseline. Blue: more often. Grey: scenario not "
             "in the GLRI set. Baseline is the +0 C row, +0% column.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    levels = pd.read_csv(habitat.levels_csv(layout), index_col="time")
    typer.echo(f"Wrote {habitat.save_figure(build_figure(levels), layout, 'F8')}")
    for title, definition in CYCLES.items():
        rates = scenario_rates(levels, definition)
        typer.echo(f"{title} {({k: round(v, 2) for k, v in rates.items()})}")


if __name__ == "__main__":
    typer.run(main)
