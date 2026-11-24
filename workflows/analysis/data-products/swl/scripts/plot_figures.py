"""Plot storm water level response surfaces of the clean and complete swl workbooks."""
from pathlib import Path

import typer

from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run
from great_lakes.swl import figures


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    units: str = typer.Option("ft", help="Water-level units: m or ft."),
    datum: str = typer.Option("NAVD88", help="Vertical datum: IGLD85 or NAVD88."),
    summary_only: bool = typer.Option(False, help="Only the 2x2 summary per lake."),
) -> None:
    layout = Layout(root)
    written = figures.write_swl_figures(
        layout, to_units=units, to_datum=datum,  # type: ignore[arg-type]
        summary_only=summary_only)
    for path in written:
        typer.echo(f"Wrote {path}")
    record_run(
        layout.swl_bulk_figures,
        "swl figures report",
        inputs=[("known-scenario swl workbooks", layout.swl_clean),
                ("complete swl workbooks", layout.swl_complete),
                ("average lake level csvs", layout.avg)],
        naming_scheme_text=(
            "<clean|complete>/<lake>_<ari>.png - one figure per lake and ARI. "
            "summary_<units>_<datum>/<clean|complete>/<lake>.png - 2x2 summary for a "
            "non-default --units/--datum. With the defaults (ft, NAVD88) the summaries go to "
            "data/swl/<clean|complete>/figures/ instead."),
        written=written,
        workspace_root=layout.root,
    )


if __name__ == "__main__":
    typer.run(main)
