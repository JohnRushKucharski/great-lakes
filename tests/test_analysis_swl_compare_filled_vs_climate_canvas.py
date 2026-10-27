"""Tests for great_lakes.analysis.swl.compare_filled_vs_climate_canvas."""
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from great_lakes.analysis.swl import compare_filled_vs_climate_canvas as cfc
from great_lakes.ari_constants import SWL_ARIS

runner = CliRunner()

# 5 known scenarios + 1 in-hull filled scenario, enough to exercise the comparison
# at ARI=1 for a single lake.
_KNOWN_SHEETS = {
    "baseline-_0_0": (0.0, 0.0),
    "nearterm-_5_1.5": (5.0, 1.5),
    "moderate_low-_10_5": (10.0, 5.0),
    "extreme_low-_20_5": (20.0, 5.0),
    "extreme_high-_0_7": (0.0, 7.0),
}


def _sheet(value: float) -> pd.DataFrame:
    rows = {"ID": [1], "lat": [44.0], "lon": [-87.0]}
    for ari in SWL_ARIS:
        rows[ari] = [value]
    return pd.DataFrame(rows)


def _write_workbook(path: Path, sheets: dict) -> None:
    with pd.ExcelWriter(path) as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)


@pytest.fixture
def clean_dir(tmp_path):
    d = tmp_path / "data" / "clean"
    d.mkdir(parents=True)
    sheets = {name: _sheet(100.0 + i) for i, name in enumerate(_KNOWN_SHEETS)}
    _write_workbook(d / "superior_swl.xlsx", sheets)
    return d


@pytest.fixture
def filled_dir(tmp_path):
    d = tmp_path / "data" / "filled"
    d.mkdir(parents=True)
    sheets = {"filled-_5_3": _sheet(103.5)}  # one in-hull target scenario
    _write_workbook(d / "superior_swl.xlsx", sheets)
    return d


@pytest.fixture
def small_scope(monkeypatch):
    monkeypatch.setattr(cfc, "LAKES", ("superior",))
    monkeypatch.setattr(cfc, "ARIS", (1.0,))


def test_resolve_default_output_dir_is_img_comparison_sibling_of_filled_dir():
    assert cfc.resolve_default_output_dir(Path("data/filled")) == Path(
        "data/filled/img/comparison"
    )


def test_run_produces_one_row_per_in_hull_target_scenario(clean_dir, filled_dir, small_scope):
    df = cfc.run(clean_dir, filled_dir)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["lake"] == "superior"
    assert row["scenario"] == "_5_3"
    assert row["ari"] == 1.0
    assert "fillin_swl_ft" in row
    assert "climate_canvas_ft" in row
    assert "diff_ft" in row


def test_main_writes_csv_and_readme(clean_dir, filled_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    result = runner.invoke(cfc.app, [str(clean_dir), str(filled_dir), str(output_dir)])
    assert result.exit_code == 0, result.output
    csv_path = output_dir / "filled_vs_climate_canvas_comparison.csv"
    assert csv_path.exists()
    text = (output_dir / "README.txt").read_text()
    assert "superior_swl.xlsx" in text
    assert "filled_vs_climate_canvas_comparison.csv" in text


def test_main_defaults_output_dir_when_omitted(clean_dir, filled_dir, small_scope):
    result = runner.invoke(cfc.app, [str(clean_dir), str(filled_dir)])
    assert result.exit_code == 0, result.output
    default_output = cfc.resolve_default_output_dir(filled_dir)
    assert (default_output / "filled_vs_climate_canvas_comparison.csv").exists()
    assert (default_output / "README.txt").exists()
