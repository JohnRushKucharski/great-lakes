"""Write the overtopping memo figures and tables (F2, F3, F4, B1, T1, T2, LOO_*)."""
from pathlib import Path

import typer

from great_lakes import overtopping
from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run

NAMING = (
    "F2_*: avg change by scenario. F3_*: avg persistence. B1_*/LOO_*: swl method quality. "
    "T1_*: design coverage. T2_*: Poisson examples. <save point>_ari<N>_*: swl elevation "
    "surface; `elevation` is the SWL, `p<runup>runup` adds that runup allowance (ft NAVD88)."
)


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    save_point_id: int = typer.Option(overtopping.SAVE_POINT_ID, help="Save point for F4."),
    ari: float = typer.Option(overtopping.PRIMARY_ARI, help="ARI (years) for F4."),
) -> None:
    layout = Layout(root)
    avg_csv = layout.avg / "michiganhuron_avg.csv"
    swl_path = layout.swl_complete / "michigan_swl.xlsx"
    output_dir = layout.overtopping / "outputs" / "figures"
    written = overtopping.run(avg_csv, swl_path, output_dir, save_point_id, ari)
    record_run(output_dir, "Overtopping memo figures and tables",
               [("avg csv", avg_csv), ("complete swl workbook", swl_path)],
               NAMING, written, layout.root)
    for path in written:
        typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    typer.run(main)
