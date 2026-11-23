"""Plot Poisson-method ARI response surfaces of the avg lake levels (high and low tails)."""
from pathlib import Path
from typing import Optional

import typer

from great_lakes import avg_ari
from great_lakes.paths import REPO_ROOT, Layout


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    lake: Optional[list[str]] = typer.Option(
        None, help=f"Lake dataset to plot (repeatable). Default: {', '.join(avg_ari.AVG_LAKES)}."),
    ari: Optional[list[float]] = typer.Option(
        None, help="ARI in years to plot (repeatable, > 1). Default: all."),
) -> None:
    layout = Layout(root)
    written = avg_ari.plot_ari_surfaces(
        layout.avg, layout.avg_statistics_outputs, layout.root,
        lakes=lake or None, aris=ari or None)
    for path in written:
        typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    typer.run(main)
