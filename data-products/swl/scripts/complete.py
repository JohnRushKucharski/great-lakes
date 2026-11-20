"""Estimate the 12 scenarios the swl source data lacks (data/swl/clean/ -> data/swl/complete/)."""
from pathlib import Path

import typer

from great_lakes import lakes
from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run
from great_lakes.swl import complete


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    overwrite: bool = typer.Option(False, help="Replace existing outputs."),
) -> None:
    layout = Layout(root)
    try:
        complete.complete_workbooks(
            layout.swl_clean, layout.avg, layout.swl_filled, layout.swl_complete, overwrite)
    except FileExistsError as error:
        typer.echo(f"{error}\nRe-run with --overwrite to replace them.", err=True)
        raise typer.Exit(1)
    names = lakes.LAKE_SWL_FILENAMES.values()
    record_run(
        layout.swl_filled,
        "swl completion report",
        inputs=[("known-scenario swl workbooks", layout.swl_clean),
                ("average lake level csvs", layout.avg)],
        naming_scheme_text=(
            "<lake>_swl.xlsx here - 12 scenarios (5 known + 7 Delaunay-filled). The 17-scenario "
            f"workbooks (adding 5 extrapolated) are written to {layout.swl_complete}."),
        written=[layout.swl_filled / n for n in names] + [layout.swl_complete / n for n in names],
        workspace_root=layout.root,
    )


if __name__ == "__main__":
    typer.run(main)
