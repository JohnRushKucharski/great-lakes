"""Tests for great_lakes.analysis.twl.plot_filled_and_extrapolated."""
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from great_lakes.analysis.twl import plot_filled_and_extrapolated as pfe
from great_lakes.ari_constants import TWL_ARIS

runner = CliRunner()

# A handful of the 17 real scenario suffixes -- enough to exercise the full-grid
# NaN-for-missing-scenario behavior (data/filled only has 12 of 17).
_SHEETS_BY_SUFFIX = {
    "baseline-_0_0": (0.0, 0.0),
    "nearterm-_5_1.5": (5.0, 1.5),
    "filled-_10_3": (10.0, 3.0),
}


def _tiny_twl_sheet(offset: float) -> pd.DataFrame:
    rows = {"ID": [1, 2], "lat": [44.0, 45.0], "lon": [-87.0, -86.0]}
    for i, ari in enumerate(TWL_ARIS):
        rows[ari] = [100.0 + offset + i, 105.0 + offset + i]
    return pd.DataFrame(rows)


def _write_workbook(path: Path) -> None:
    with pd.ExcelWriter(path) as writer:
        for i, sheet_name in enumerate(_SHEETS_BY_SUFFIX):
            _tiny_twl_sheet(offset=float(i)).to_excel(writer, sheet_name=sheet_name, index=False)


@pytest.fixture
def filled_dir(tmp_path):
    d = tmp_path / "data" / "filled"
    d.mkdir(parents=True)
    _write_workbook(d / "superior_twl.xlsx")
    return d


@pytest.fixture
def clean_dir(tmp_path):
    d = tmp_path / "data" / "clean"
    d.mkdir(parents=True)
    (d / "superior_avg.csv").write_text("time,_0_0\n1970-01-01,183.0\n1970-02-01,183.2\n")
    return d


@pytest.fixture
def small_scope(monkeypatch):
    monkeypatch.setattr(pfe, "LAKES", ("superior",))
    monkeypatch.setattr(pfe, "ARIS", (1.0, 10.0))


def test_resolve_default_output_dir_is_img_sibling_of_data_dir():
    assert pfe.resolve_default_output_dir(Path("data/filled")) == Path("data/filled/img")


def test_resolve_default_avg_data_dir_is_clean_sibling_of_data_dir():
    assert pfe.resolve_default_avg_data_dir(Path("data/filled")) == Path("data/clean")
    assert pfe.resolve_default_avg_data_dir(Path("data/extrapolated")) == Path("data/clean")


def test_run_writes_raw_and_interpolated_plots(filled_dir, clean_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    written = pfe.run(filled_dir, output_dir, clean_dir)
    assert (output_dir / "superior_1.png").exists()
    assert (output_dir / "interpolated" / "superior_1.png").exists()
    assert (output_dir / "superior_10.png").exists()
    assert (output_dir / "interpolated" / "superior_10.png").exists()
    for path in written:
        assert path.exists()


def test_main_writes_readme_and_defaults(filled_dir, clean_dir, small_scope):
    result = runner.invoke(pfe.app, [str(filled_dir)])
    assert result.exit_code == 0, result.output
    default_output = pfe.resolve_default_output_dir(filled_dir)
    text = (default_output / "README.txt").read_text()
    assert "superior_twl.xlsx" in text
    assert (default_output / "superior_1.png").exists()
