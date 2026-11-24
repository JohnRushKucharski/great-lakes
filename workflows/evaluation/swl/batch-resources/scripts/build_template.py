"""Rebuild the blank swl resources+config template (inputs/templates/template_swl.xlsx)."""
from pathlib import Path

import typer

from great_lakes.batch import assess
from great_lakes.paths import REPO_ROOT, Layout


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    typer.echo(f"Wrote {assess.build_template('swl', Layout(root))}")


if __name__ == "__main__":
    typer.run(main)
