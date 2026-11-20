"""Repository folder layout for the data products, shared by the workflow scripts."""

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Layout:
    """Data and data-product folders under `root` (default: this repo).

    Scripts take an optional `--root` so tests can run them on a small fixture tree.
    """

    root: Path = REPO_ROOT

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def avg(self) -> Path:
        return self.root / "data" / "avg"

    @property
    def avg_figures(self) -> Path:
        return self.avg / "figures"

    @property
    def swl_clean(self) -> Path:
        return self.root / "data" / "swl" / "clean"

    @property
    def swl_complete(self) -> Path:
        return self.root / "data" / "swl" / "complete"

    @property
    def swl_clean_figures(self) -> Path:
        return self.swl_clean / "figures"

    @property
    def swl_complete_figures(self) -> Path:
        return self.swl_complete / "figures"

    @property
    def avg_product(self) -> Path:
        return self.root / "data-products" / "avg"

    @property
    def swl_product(self) -> Path:
        return self.root / "data-products" / "swl"

    @property
    def avg_bulk_figures(self) -> Path:
        return self.avg_product / "outputs" / "figures"

    @property
    def swl_bulk_figures(self) -> Path:
        return self.swl_product / "outputs" / "figures"

    @property
    def swl_filled(self) -> Path:
        return self.swl_product / "outputs" / "filled"

    @property
    def swl_fill_gate_outputs(self) -> Path:
        return self.swl_product / "outputs" / "gates" / "fill_vs_climate_canvas"

    @property
    def swl_ari_gate_outputs(self) -> Path:
        return self.swl_product / "outputs" / "gates" / "ari_curves"

    @property
    def swl_methods_outputs(self) -> Path:
        return self.swl_product / "outputs" / "methods"
