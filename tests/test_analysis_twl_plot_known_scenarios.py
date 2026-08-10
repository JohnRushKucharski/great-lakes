"""Tests for great_lakes.analysis.twl.plot_known_scenarios."""
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from great_lakes.analysis.twl import plot_known_scenarios

runner = CliRunner()

# Real known-scenario sheet names/coords shared by every <lake>_twl.xlsx workbook.
_KNOWN_SHEETS = {
    "baseline-_0_0": (0.0, 0.0),
    "nearterm-_5_1.5": (5.0, 1.5),
    "moderate_low-_10_5": (10.0, 5.0),
    "extreme_low-_20_5": (20.0, 5.0),
    "extreme_high-_0_7": (0.0, 7.0),
}


def _tiny_twl_sheet(offset: float) -> pd.DataFrame:
    """2 save points, all 13 real ARI columns."""
    from great_lakes.ari_constants import TWL_ARIS
    rows = {
        "ID": [1, 2],
        "lat": [44.0, 45.0],
        "lon": [-87.0, -86.0],
    }
    for i, ari in enumerate(TWL_ARIS):
        rows[ari] = [100.0 + offset + i, 105.0 + offset + i]
    return pd.DataFrame(rows)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "clean"
    d.mkdir()
    for lake, filename in {"superior": "superior_twl.xlsx"}.items():
        path = d / filename
        with pd.ExcelWriter(path) as writer:
            for i, (sheet_name, _coord) in enumerate(_KNOWN_SHEETS.items()):
                _tiny_twl_sheet(offset=float(i)).to_excel(
                    writer, sheet_name=sheet_name, index=False
                )
    (d / "superior_avg.csv").write_text("time,_0_0\n1970-01-01,183.0\n1970-02-01,183.2\n")
    return d


@pytest.fixture
def small_scope(monkeypatch):
    monkeypatch.setattr(plot_known_scenarios, "LAKES", ("superior",))
    monkeypatch.setattr(plot_known_scenarios, "ARIS", (1.0, 10.0))


def test_resolve_default_output_dir_is_img_twl_known_sibling_of_data_dir():
    data_dir = Path("data/clean")
    assert plot_known_scenarios.resolve_default_output_dir(data_dir) == Path(
        "data/clean/img/twl/known"
    )


def test_run_writes_known_plots_raw_and_interpolated(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    written = plot_known_scenarios.run(data_dir, output_dir)
    assert (output_dir / "superior_1.png").exists()
    assert (output_dir / "interpolated" / "superior_1.png").exists()
    assert (output_dir / "superior_10.png").exists()
    assert (output_dir / "interpolated" / "superior_10.png").exists()
    for path in written:
        assert path.exists()


def test_main_writes_readme(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    result = runner.invoke(plot_known_scenarios.app, [str(data_dir), str(output_dir)])
    assert result.exit_code == 0, result.output
    text = (output_dir / "README.txt").read_text()
    assert "superior_twl.xlsx" in text
    assert "interpolated" in text


def test_main_defaults_output_dir_when_omitted(data_dir, small_scope):
    result = runner.invoke(plot_known_scenarios.app, [str(data_dir)])
    assert result.exit_code == 0, result.output
    default_output = plot_known_scenarios.resolve_default_output_dir(data_dir)
    assert (default_output / "README.txt").exists()
    assert (default_output / "superior_1.png").exists()
