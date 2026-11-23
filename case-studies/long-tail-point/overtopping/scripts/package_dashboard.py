"""Zip the dashboard and the files it links into outputs/long-tail-point-dashboard.zip."""
from pathlib import Path

import typer

from great_lakes import dashboard_package
from great_lakes.paths import REPO_ROOT, Layout


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    outputs = Layout(root).overtopping / "outputs"
    zip_path = dashboard_package.package_dashboard(
        outputs, outputs / "long-tail-point-dashboard.zip")
    typer.echo(f"Wrote {zip_path}")


if __name__ == "__main__":
    typer.run(main)
