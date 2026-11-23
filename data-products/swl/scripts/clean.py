"""Split the swl source workbook (data/raw/) into one workbook per lake (data/swl/clean/)."""
from pathlib import Path

import typer

from great_lakes.cleaning import swl
from great_lakes.paths import REPO_ROOT, Layout


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    overwrite: bool = typer.Option(False, help="Replace existing outputs."),
) -> None:
    layout = Layout(root)
    try:
        written = swl.clean_workbook(layout.raw, layout.swl_clean, overwrite)
    except FileExistsError as error:
        typer.echo(f"{error}\nRe-run with --overwrite to replace them.", err=True)
        raise typer.Exit(1)
    for path in written:
        typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    typer.run(main)
