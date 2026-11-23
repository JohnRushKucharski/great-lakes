"""Tests for the scenario-grid avg statistics (change, persistence, Poisson examples)."""
import pandas as pd
import pytest
from ltp_fixtures import monthly_avg

from great_lakes import avg_scenario_stats as stats
from great_lakes import scenario_grid as sg
from great_lakes.avg_stats import annual_maxima


@pytest.fixture
def monthly():
    return monthly_avg(years=20)


def test_scenario_avg_change_is_zero_for_baseline(monthly, tmp_path):
    stats.write_scenario_avg_change(sg.scenario_means(monthly), tmp_path)
    frame = pd.read_csv(tmp_path / "F2_scenario_avg_change.csv")
    assert len(frame) == 17
    assert frame.loc[frame["scenario"] == "_0_0", "avg_change_ft"].iloc[0] == 0.0
    assert (tmp_path / "F2_scenario_avg_change.png").stat().st_size > 0


def test_persistence_writes_summary_annual_flags_and_plot(monthly, tmp_path):
    means = sg.scenario_means(monthly)
    stats.write_persistence(annual_maxima(monthly), means, tmp_path)
    summary = pd.read_csv(tmp_path / "F3_persistence_summary.csv")
    assert summary["case"].iloc[0] == "baseline"
    assert len(summary) == 5
    assert (tmp_path / "F3_annual_high_years.csv").exists()
    assert (tmp_path / "F3_avg_persistence.png").stat().st_size > 0


def test_persistence_is_reproducible(monthly, tmp_path):
    means = sg.scenario_means(monthly)
    for name in ("a", "b"):
        stats.write_persistence(annual_maxima(monthly), means, tmp_path / name)
    assert (tmp_path / "a" / "F3_annual_high_years.csv").read_bytes() == (
        tmp_path / "b" / "F3_annual_high_years.csv").read_bytes()


def test_poisson_examples(tmp_path):
    stats.write_poisson_examples(tmp_path)
    frame = pd.read_csv(tmp_path / "T2_poisson_examples.csv")
    assert list(frame["label"]) == ["At least 1", "At least 3", "At least 4"]
    assert frame["probability_pct"].iloc[0] == pytest.approx(100 * (1 - 2.718281828 ** -1),
                                                             abs=1e-6)


def test_run_writes_every_output(monthly, tmp_path):
    csv = tmp_path / "michiganhuron_avg.csv"
    monthly.to_csv(csv, index=False)
    paths = stats.run(csv, tmp_path / "out")
    assert [p.name for p in paths] == list(stats.OUTPUT_NAMES)
    assert all(p.exists() for p in paths)
