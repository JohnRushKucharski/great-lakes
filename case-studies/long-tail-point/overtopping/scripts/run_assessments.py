"""Run the two Long Tail Point resource worksheets (avg and swl) through assess.py's engine."""
import os
from pathlib import Path

import typer

from great_lakes.batch import assess
from great_lakes.paths import REPO_ROOT, Layout

WORKSHEETS = (("avg", "batch_avg.xlsx"), ("swl", "batch_swl-longtail.xlsx"))


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    inputs = layout.overtopping / "inputs"
    # The worksheets' output_directory cells are relative to the repo root.
    os.chdir(layout.root)
    codes = [
        assess.assess_resources(kind, layout, inputs / name)  # type: ignore[arg-type]
        for kind, name in WORKSHEETS
    ]
    raise typer.Exit(1 if any(codes) else 0)


if __name__ == "__main__":
    typer.run(main)
