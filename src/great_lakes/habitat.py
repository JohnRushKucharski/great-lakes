"""Shared paths and run record for the Long Tail Point habitat scripts."""
from pathlib import Path
from typing import Sequence

import pandas as pd
from matplotlib.figure import Figure

from great_lakes.paths import Layout
from great_lakes.run_record import record_run

FIGURES_NAMING = (
    "F<n>.png is figure n of the habitat memo (see docs/plans/ltp_habitat_report_plan.md); "
    "F4B and F4C are Jenny's depth maps, copied unchanged."
)

RELIABILITY_NAMING = (
    "<species>_reliability.csv: per scenario and floor elevation (ft IGLD85), the share of "
    "complete years (musky recruitment: rolling 5-year windows) meeting each habitat component."
)


def levels_csv(layout: Layout) -> Path:
    """Michigan-Huron avg levels (m, IGLD85), one column per scenario."""
    return layout.avg / "michiganhuron_avg.csv"


def survey_xlsx(layout: Layout) -> Path:
    """Dead Horse Bay survey points (depth_analysis sheet)."""
    return layout.habitat / "inputs" / "Compiled PI Survey Data_jo.xlsx"


def jenny_maps_dir(layout: Layout) -> Path:
    """Jenny's 3C dry / 3C wet survey-point depth maps (F4B.png, F4C.png)."""
    return layout.habitat / "inputs" / "jenny_maps"


def figures_dir(layout: Layout) -> Path:
    return layout.habitat / "outputs" / "figures"


def reliability_dir(layout: Layout) -> Path:
    return layout.habitat / "outputs" / "reliability"


def reliability_results(layout: Layout) -> pd.DataFrame:
    """Musky and pondweed reliability tables stacked into one frame."""
    folder = reliability_dir(layout)
    return pd.concat(
        [pd.read_csv(folder / "musky_reliability.csv"),
         pd.read_csv(folder / "pondweed_reliability.csv")]
    )


def figure_inputs(layout: Layout) -> list[tuple[str, Path]]:
    """Inputs the habitat figures read, for the figures run record."""
    return [
        ("avg levels (m, IGLD85)", levels_csv(layout)),
        ("survey points", survey_xlsx(layout)),
        ("reliability tables", reliability_dir(layout)),
        ("Jenny's depth maps", jenny_maps_dir(layout)),
    ]


def save_figure(fig: Figure, layout: Layout, fig_id: str) -> Path:
    """Save `fig` as outputs/figures/<fig_id>.png and refresh the figures README.txt."""
    out = figures_dir(layout) / f"{fig_id}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    refresh_figures_readme(layout)
    return out


def refresh_figures_readme(layout: Layout) -> Path:
    """Rewrite outputs/figures/README.txt to list the folder's current files."""
    return record_outputs(
        figures_dir(layout), "Habitat memo figures", figure_inputs(layout), FIGURES_NAMING, layout
    )


def refresh_reliability_readme(layout: Layout) -> Path:
    """Rewrite outputs/reliability/README.txt to list the folder's current files."""
    return record_outputs(
        reliability_dir(layout),
        "Habitat reliability tables",
        [("avg levels (m, IGLD85)", levels_csv(layout))],
        RELIABILITY_NAMING,
        layout,
    )


def record_outputs(
    output_dir: Path,
    title: str,
    inputs: Sequence[tuple[str, Path]],
    naming: str,
    layout: Layout,
) -> Path:
    """Write the folder's README.txt listing every file in it.

    Several scripts write into one folder, so the record covers the whole folder rather
    than one run's files; whichever script runs last leaves a complete README.
    """
    written = sorted(p for p in output_dir.iterdir() if p.is_file() and p.name != "README.txt")
    return record_run(output_dir, title, inputs, naming, written, layout.root)
