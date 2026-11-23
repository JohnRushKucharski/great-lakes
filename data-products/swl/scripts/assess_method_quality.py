"""swl method quality: regression of swl on avg and leave-one-out checks at one save point."""
from pathlib import Path

import typer

from great_lakes import swl_method_quality
from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run

NAMING = (
    "B1_*: swl-on-avg regression (residuals, predictions, plot). LOO_*: leave-one-out checks "
    "of the row-shift and interpolation steps of scenario completion."
)


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    lake: str = typer.Option("michigan", help="swl lake (data/swl/complete/<lake>_swl.xlsx)."),
    avg_lake: str = typer.Option("michiganhuron", help="Matching avg dataset."),
    save_point_id: int = typer.Option(
        swl_method_quality.SAVE_POINT_ID, help="Save point the checks are run at."),
    ari: float = typer.Option(
        swl_method_quality.PRIMARY_ARI, help="ARI (years) shown in the regression plot."),
) -> None:
    layout = Layout(root)
    avg_csv = layout.avg / f"{avg_lake}_avg.csv"
    swl_path = layout.swl_complete / f"{lake}_swl.xlsx"
    output_dir = layout.swl_methods_outputs / "method_quality"
    written = swl_method_quality.run(avg_csv, swl_path, output_dir, save_point_id, ari)
    record_run(output_dir, f"swl method quality (save point {save_point_id}, ARI {ari:g})",
               [("avg csv", avg_csv), ("complete swl workbook", swl_path)],
               NAMING, written, layout.root)
    for path in written:
        typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    typer.run(main)
