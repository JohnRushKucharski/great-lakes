"""Scenario avg statistics (avg change, persistence, Poisson examples) for one lake dataset."""
from pathlib import Path

import typer

from great_lakes import avg_scenario_stats
from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run

NAMING = (
    "F2_*: full-record mean avg change per scenario. F3_*: annual-maximum persistence by "
    "scenario. T2_*: Poisson-method worked examples."
)


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    lake: str = typer.Option("michiganhuron", help="Avg dataset (data/avg/<lake>_avg.csv)."),
) -> None:
    layout = Layout(root)
    avg_csv = layout.avg / f"{lake}_avg.csv"
    output_dir = layout.avg_statistics_outputs / "scenario_statistics"
    written = avg_scenario_stats.run(avg_csv, output_dir)
    record_run(output_dir, f"Scenario avg statistics ({lake})", [("avg csv", avg_csv)],
               NAMING, written, layout.root)
    for path in written:
        typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    typer.run(main)
