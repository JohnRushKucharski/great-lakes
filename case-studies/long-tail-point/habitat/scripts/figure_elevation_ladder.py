"""F3 Elevation Ladder: floor elevations vs future lake levels (habitat memo).

y = elevation (ft IGLD85). One column per scenario group: monthly lake-level band, Jenny's
marsh-zone elevations (level minus zone depth range), woody debris (WD) floors, plus a side
histogram of surveyed survey-point bottom elevations. Lake levels convert m -> ft here only;
no datum change (all IGLD85).

Usage: uv run python case-studies/long-tail-point/habitat/scripts/figure_elevation_ladder.py
"""

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from great_lakes import habitat  # noqa: E402
from great_lakes.paths import REPO_ROOT, Layout  # noqa: E402

LEVELS_CSV = habitat.levels_csv(Layout())
SURVEY_XLSX = habitat.survey_xlsx(Layout())

M_TO_FT = 1 / 0.3048
Y_RANGE_FT = (571.0, 583.0)  # 3 C wet level (~581 ft) sits above the 571-579 ft floor range

SCENARIO_GROUPS = {
    "3 C dry\n(3C/0)": ["_0_3"],
    "1.5 C dry\n(1.5C/0)": ["_0_1.5"],
    "Baseline": ["_0_0"],
    "1.5 C wet\n(1.5C/5)": ["_5_1.5"],
    "3 C wet\n(3C/15)": ["_15_3"],
}

# Jenny T3 depth key (ft below water level). Unrooted floating (any depth) is omitted.
ZONE_DEPTHS_FT = {
    "Shoreline marsh": (0.0, 1.0),
    "Shallow marsh": (0.5, 2.0),
    "Shallow emergent": (0.0, 2.0),
    "Rooting floating": (1.0, 4.0),
    "Deep emergent": (2.0, 4.0),
    "Shallow submergent": (2.0, 6.0),
    "Deep submergent": (4.0, 6.0),
}
ZONE_COLORS = {
    "Shoreline marsh": "#8c6d31",
    "Shallow marsh": "#b5a642",
    "Shallow emergent": "#7fb069",
    "Rooting floating": "#e6a8d7",
    "Deep emergent": "#2e8b57",
    "Shallow submergent": "#5fa8d3",
    "Deep submergent": "#1b4965",
}

# Jenny T8: WD structure end floors, ft IGLD85. Plan LWD from the 35% plan.
WD_FLOORS_FT = {
    "1w": 575.11,
    "1e": 575.01,
    "2w": 575.26,
    "2e": 575.56,
    "3w": 576.01,
    "3e": 576.46,
}
PLAN_LWD_FT = 576.15


def level_bands_ft(levels_m: pd.DataFrame, scenarios: Sequence[str]) -> dict[str, float]:
    """Pooled monthly level stats (ft) across the given scenario columns (input in m)."""
    values = levels_m[list(scenarios)].to_numpy().ravel() * M_TO_FT
    return {
        "p10": float(np.percentile(values, 10)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "mean": float(values.mean()),
    }


def zone_elevations(level_ft: float) -> pd.DataFrame:
    """Elevation range (ft) of each marsh zone when the water level is level_ft."""
    rows = [
        {"zone": zone, "low": level_ft - deep, "high": level_ft - shallow}
        for zone, (shallow, deep) in ZONE_DEPTHS_FT.items()
    ]
    return pd.DataFrame(rows)


def save_point_elevations(path: Path = SURVEY_XLSX) -> np.ndarray:
    """Survey-point bottom elevations (ft IGLD85) from the depth_analysis sheet."""
    sheet = pd.read_excel(path, sheet_name="depth_analysis")
    return sheet["Estimated Bottom elevation (ft)"].dropna().to_numpy()


def build_figure(levels_m: pd.DataFrame, save_points: np.ndarray) -> plt.Figure:
    fig, (ax, hist) = plt.subplots(
        1, 2, figsize=(10, 6.5), sharey=True, gridspec_kw={"width_ratios": [7, 1], "wspace": 0.03}
    )
    bar_w = 0.1
    for i, (label, scenarios) in enumerate(SCENARIO_GROUPS.items()):
        band = level_bands_ft(levels_m, scenarios)
        ax.fill_between(
            [i - 0.45, i + 0.45], band["p10"], band["p90"], color="#9ecae1", alpha=0.45, lw=0
        )
        ax.hlines(band["median"], i - 0.45, i + 0.45, color="#08519c", lw=2)
        zones = zone_elevations(band["mean"])
        for j, (zone, low, high) in enumerate(zip(zones["zone"], zones["low"], zones["high"])):
            x = i - 0.4 + j * (bar_w + 0.0075)
            ax.bar(
                x, high - low, bar_w, bottom=low, align="edge",
                color=ZONE_COLORS[zone], edgecolor="none", alpha=0.9,
            )
    wd_lo, wd_hi = min(WD_FLOORS_FT.values()), max(WD_FLOORS_FT.values())
    for axis in (ax, hist):
        axis.axhspan(wd_lo, wd_hi, color="#7f5539", alpha=0.18, lw=0)
    ax.axhline(PLAN_LWD_FT, color="#7f5539", ls="--", lw=1.5)
    # Labels sit right of the histogram so they never cover bars.
    hist.text(1.05, PLAN_LWD_FT, "35% plan LWD\n576.15 ft", va="center", fontsize=8,
              color="#7f5539", transform=hist.get_yaxis_transform())
    hist.text(1.05, (wd_lo + wd_hi) / 2 - 0.9, "WD bottom elevations\n575.01-576.46 ft",
              va="center", fontsize=8, color="#7f5539", transform=hist.get_yaxis_transform())

    ax.set_xticks(range(len(SCENARIO_GROUPS)), list(SCENARIO_GROUPS))
    ax.set_xlim(-0.5, len(SCENARIO_GROUPS) - 0.5)
    ax.set_ylim(*Y_RANGE_FT)
    ax.set_ylabel("Elevation (ft, IGLD85)")
    ax.grid(axis="y", alpha=0.3)
    handles = [Patch(color=c, label=z) for z, c in ZONE_COLORS.items()]
    handles.append(Patch(color="#9ecae1", alpha=0.6, label="Lake level p10-p90 (median line)"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=7,
              ncol=4, framealpha=0.9)

    bins = np.arange(np.floor(save_points.min()), np.ceil(save_points.max()) + 0.5, 0.5)
    hist.hist(save_points, bins=bins, orientation="horizontal", color="#6c757d")
    hist.set_xlabel("Survey points\n(count)")
    hist.tick_params(labelleft=False)
    fig.suptitle("Elevation Ladder: zones and structure bottom elevations vs lake level",
                 fontsize=11)
    return fig


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    levels = pd.read_csv(habitat.levels_csv(layout), index_col="time")
    fig = build_figure(levels, save_point_elevations(habitat.survey_xlsx(layout)))
    typer.echo(f"Wrote {habitat.save_figure(fig, layout, 'F3')}")


if __name__ == "__main__":
    typer.run(main)
