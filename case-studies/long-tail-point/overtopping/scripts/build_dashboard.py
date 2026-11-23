"""Build outputs/dashboard.html and manifest.js from the already-run swl worksheet.

The original dashboard covered swl only; pass --include-avg to add the avg rows.
"""
import os
from pathlib import Path

import typer

from great_lakes import build_dashboard
from great_lakes.paths import REPO_ROOT, Layout


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    include_avg: bool = typer.Option(False, help="Also list the avg worksheet's outputs."),
) -> None:
    layout = Layout(root)
    inputs = layout.overtopping / "inputs"
    # The worksheets' output_directory cells are relative to the repo root.
    os.chdir(layout.root)
    avg_workbooks = [inputs / "batch_avg.xlsx"] if include_avg else []
    build_dashboard.build_dashboard(
        [inputs / "batch_swl-longtail.xlsx"], avg_workbooks, layout.overtopping / "outputs")
    typer.echo(f"Wrote {layout.overtopping / 'outputs' / 'dashboard.html'}")


if __name__ == "__main__":
    typer.run(main)
