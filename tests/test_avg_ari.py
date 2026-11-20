"""Tests for great_lakes.avg_ari."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from great_lakes import avg_ari as plot_levels
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES

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
    exercises every branch (high/low tail, clustered/declustered, interpolated)."""
    monkeypatch.setattr(plot_levels, "AVG_LAKES", ("superior",))
    monkeypatch.setattr(plot_levels, "AVG_ARIS", (2.0,))


# ---- run() writes the new folder layout ---------------------------------------------


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
    all_files = {p for p in output_dir.rglob("*") if p.is_file()}
    assert set(written) == all_files


def test_run_writes_levels_csv_matching_grid(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    plot_levels.run(data_dir, output_dir)
    table = pd.read_csv(output_dir / "ari" / "superior_ari_levels.csv")
    assert list(table.columns) == [
        "lake", "tail", "population", "ari", "ari_is_min_floor", "scenario",
        "precip_delta", "temp_delta", "level_ft"]
    assert set(table["tail"]) == {"high", "low"}
    assert set(table["population"]) == {"clustered", "declustered"}
    assert set(table["scenario"]) == set(ALL_SCENARIO_SUFFIXES)
    # One row per scenario for each (tail, population, ARI): 2 ARIs (floor + 2.0) here.
    assert len(table) == 2 * 2 * 2 * len(ALL_SCENARIO_SUFFIXES)
    df = pd.read_csv(data_dir / "superior_avg.csv")
    columns = {c: df[c].to_numpy(dtype=float) for c in df.columns if c != "time"}
    _, _, z = plot_levels.build_grid(columns, ari=2.0, tail="high", decluster=False)
    row = table[(table["tail"] == "high") & (table["population"] == "clustered")
                & (table["ari"] == 2.0) & (table["scenario"] == "_0_0")].iloc[0]
    expected = z[plot_levels.ALL_TEMPS.index(row.temp_delta),
                 plot_levels.ALL_PRECIPS.index(row.precip_delta)]
    assert row.level_ft == pytest.approx(expected)


# Superior baseline (_0_0), feet; the worked example in avg_ari_poisson_method.md.
SUPERIOR_BASELINE_FT = {
    ("high", "clustered", 2.0): 602.789, ("high", "clustered", 100.0): 603.707,
    ("high", "declustered", 2.0): 601.804, ("high", "declustered", 100.0): 603.596,
    ("low", "clustered", 2.0): 600.722, ("low", "clustered", 100.0): 600.077,
    ("low", "declustered", 2.0): 601.608, ("low", "declustered", 100.0): 600.098,
}


def test_superior_baseline_matches_method_doc_worked_example(tmp_path):
    avg_dir = Path(__file__).resolve().parents[1] / "data" / "avg"
    out = tmp_path / "out"
    plot_levels.run(avg_dir, out, lakes=["superior"], aris=[2.0, 100.0])
    table = pd.read_csv(out / "ari" / "superior_ari_levels.csv")
    baseline = table[table["scenario"] == "_0_0"]
    for (tail, population, ari), expected in SUPERIOR_BASELINE_FT.items():
        row = baseline[(baseline["tail"] == tail) & (baseline["population"] == population)
                       & (baseline["ari"] == ari)]
        assert row["level_ft"].iloc[0] == pytest.approx(expected, abs=5e-4)


def test_plot_ari_surfaces_writes_plots_and_readme(data_dir, small_scope, tmp_path):
    output_dir = tmp_path / "out"
    written = plot_levels.plot_ari_surfaces(data_dir, output_dir, workspace_root=tmp_path)
    assert written and all(path.exists() for path in written)
    readme_text = (output_dir / "README.txt").read_text()
    assert "superior_avg.csv" in readme_text
    assert "ari/" in readme_text


