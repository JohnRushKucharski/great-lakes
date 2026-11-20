"""Plot the mean average lake level response surface of each lake (all five lakes)."""
from pathlib import Path

import typer

from great_lakes import avg_figures
from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    units: str = typer.Option("ft", help="Water-level units: m or ft."),
    datum: str = typer.Option("NAVD88", help="Vertical datum: IGLD85 or NAVD88."),
) -> None:
    layout = Layout(root)
    written = avg_figures.write_avg_figures(
        layout, to_units=units, to_datum=datum)  # type: ignore[arg-type]
    for path in written:
        typer.echo(f"Wrote {path}")
    record_run(
        layout.avg_bulk_figures,
        "avg figures report",
        inputs=[("average lake level csvs", layout.avg)],
        naming_scheme_text=(
            "<lake>.png - mean level surface per lake (all five lakes). "
            "interpolated/<lake>.png - same, interpolated. <units>_<datum>/ - the same for a "
            "non-default --units/--datum. With the defaults (ft, NAVD88) the raw figures are "
            f"also written to {layout.avg_figures}."),
        written=written,
        workspace_root=layout.root,
    )


if __name__ == "__main__":
    typer.run(main)
