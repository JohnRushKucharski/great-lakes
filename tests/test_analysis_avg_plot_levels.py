"""Tests for great_lakes.analysis.avg.plot_levels."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from great_lakes.analysis.avg import plot_levels
from great_lakes.fillin_twl import ALL_SCENARIO_SUFFIXES

runner = CliRunner()


# ---- resolve_default_output_dir -----------------------------------------------------

def test_resolve_default_output_dir_is_img_avg_sibling_of_data_dir():
    data_dir = Path("data/clean")
    assert plot_levels.resolve_default_output_dir(data_dir) == Path("data/clean/img/avg")


# ---- fixture: tiny synthetic <lake>_avg.csv, all 17 scenario columns ----------------

def _write_tiny_avg_csv(path: Path, seed: int = 0) -> None:
    """24 monthly rows (2 years), one column per real scenario suffix, values varying
    enough to exercise mean + Poisson ARI math without a full ~12,360-row record."""
    rng = np.random.default_rng(seed)
    n = 24
    data = {"time": pd.date_range("1970-01-01", periods=n, freq="MS")}
    for suffix in ALL_SCENARIO_SUFFIXES:
        data[suffix] = 183.0 + rng.normal(0, 0.3, n)
    pd.DataFrame(data).to_csv(path, index=False)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "clean"
    d.mkdir()
    for lake in ("superior", "michiganhuron", "ontario"):
        _write_tiny_avg_csv(d / f"{lake}_avg.csv")
    return d


@pytest.fixture
def small_scope(monkeypatch):
    """Restrict the module's lake/ARI scope so tests run in reasonable time -- still
    exercises every branch (mean, high/low tail, clustered/declustered, interpolated)."""
    monkeypatch.setattr(plot_levels, "AVG_LAKES", ("superior",))
    monkeypatch.setattr(plot_levels, "AVG_ARIS", (2.0,))


# ---- run() writes the new folder layout ---------------------------------------------

def test_run_writes_mean_plots_raw_and_interpolated(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    plot_levels.run(data_dir, output_dir)
    assert (output_dir / "mean" / "superior.png").exists()
    assert (output_dir / "mean" / "interpolated" / "superior.png").exists()


def test_run_writes_ari_plots_under_clustered_and_declustered(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    plot_levels.run(data_dir, output_dir)
    for cluster in ("clustered", "declustered"):
        for tail in ("high", "low"):
            base = output_dir / "ari" / cluster / tail
            matches = list(base.glob("superior_*.png"))
            assert matches, f"no ari plot under {base}"
            assert (base / "interpolated").exists()
            assert list((base / "interpolated").glob("superior_*.png"))


def test_run_returns_every_written_path(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    written = plot_levels.run(data_dir, output_dir)
    for path in written:
        assert path.exists()
    all_pngs = set(output_dir.rglob("*.png"))
    assert set(written) == all_pngs


# ---- CLI: main() writes README.txt ---------------------------------------------------

def test_main_writes_readme_with_inputs_and_naming_scheme(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    result = runner.invoke(plot_levels.app, [str(data_dir), str(output_dir)])
    assert result.exit_code == 0, result.output
    readme_text = (output_dir / "README.txt").read_text()
    assert "superior_avg.csv" in readme_text
    assert "mean/" in readme_text
    assert "ari/" in readme_text


def test_main_defaults_output_dir_when_omitted(data_dir, small_scope):
    result = runner.invoke(plot_levels.app, [str(data_dir)])
    assert result.exit_code == 0, result.output
    default_output = plot_levels.resolve_default_output_dir(data_dir)
    assert (default_output / "README.txt").exists()
    assert (default_output / "mean" / "superior.png").exists()
