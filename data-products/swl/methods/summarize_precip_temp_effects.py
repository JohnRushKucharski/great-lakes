"""Percent change in swl per precip / temp delta, from the known scenarios (see effects.py)."""
from pathlib import Path

import typer

from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.run_record import record_run
from great_lakes.swl import effects


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    written = effects.run(layout.swl_complete, layout.swl_methods_outputs)
    record_run(
        layout.swl_methods_outputs,
        "Known-scenario precip/temp effects report",
        inputs=[("complete swl workbooks", layout.swl_complete)],
        naming_scheme_text=(
            "known_scenario_directionality.csv - per lake, save point and ARI: change in swl "
            "per precip and temp delta between known scenarios. "
            "known_scenario_directionality_summary.xlsx - per-lake summary statistics."),
        written=list(written),
        workspace_root=layout.root,
    )


if __name__ == "__main__":
    typer.run(main)
