"""Gate: the in-hull fill must match climate_canvas's own interpolation (within 0.05 ft)."""
from pathlib import Path

import typer

from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.swl import gates


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    try:
        gates.run_gate(
            layout.swl_clean, layout.swl_filled, layout.swl_fill_gate_outputs, layout.root)
    except gates.GateFailure as error:
        typer.echo(f"GATE FAILED: {error}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
