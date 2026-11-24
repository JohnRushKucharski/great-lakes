"""Assess avg resources (hydropattern runs) listed in a resources workbook."""
from pathlib import Path
from typing import Optional

import typer

from great_lakes.batch import assess
from great_lakes.paths import REPO_ROOT, Layout


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    resources: Optional[Path] = typer.Option(
        None, help="Resources+config workbook. Default: inputs/templates/template_avg.xlsx."),
    data_dir: Optional[Path] = typer.Option(None, help="Folder of avg csvs. Default: data/avg."),
    output_dir: Optional[Path] = typer.Option(
        None, help="Overrides the workbook's output_directory. Default with the shipped "
                   "template: this workflow's outputs/ folder."),
) -> None:
    code = assess.assess_resources("avg", Layout(root), resources, data_dir, output_dir)
    raise typer.Exit(code)


if __name__ == "__main__":
    typer.run(main)
