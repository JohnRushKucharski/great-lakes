"""Gate: every complete swl curve must be present and non-decreasing as the ARI grows."""
from pathlib import Path

import typer

from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.swl import gates


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    try:
        gates.run_ari_gate(layout.swl_complete, layout.swl_ari_gate_outputs, layout.root)
    except gates.GateFailure as error:
        typer.echo(f"GATE FAILED: {error}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
