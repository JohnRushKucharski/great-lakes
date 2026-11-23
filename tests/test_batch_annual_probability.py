"""Tests for great_lakes.batch.annual_probability (avg batch `annual_probability` metric)."""
import math

import pandas as pd
import pytest

from great_lakes.batch import annual_probability as ap

COLUMNS = [
    "scenario", "outcome_column", "interval", "completeness",
    "event_count_lower", "event_count_upper",
]


def write_summary(path, rows):
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows, columns=COLUMNS).to_excel(
            writer, sheet_name="reporting_details", index=False
        )
    return path


def test_counts_complete_water_years_with_at_least_one_occurrence(tmp_path):
    path = write_summary(tmp_path / "x_summary.xlsx", [
        ("_0_0", "comp", "total", "whole_record", 3, 3),
        ("_0_0", "comp", 1970, "complete", 2, 2),
        ("_0_0", "comp", 1971, "complete", 0, 0),
        ("_0_0", "comp", 1972, "complete", 1, 1),
        ("_0_0", "comp", 1973, "complete", 0, 0),
    ])
    table = ap.annual_probability_by_scenario(path, "comp")
    row = table.loc["_0_0"]
    assert (row["eligible_water_years"], row["occurrence_water_years"]) == (4, 2)
    assert row["annual_probability"] == pytest.approx(0.5)


def test_incomplete_indeterminate_and_other_columns_are_excluded(tmp_path):
    path = write_summary(tmp_path / "x_summary.xlsx", [
        ("_0_0", "comp", 1970, "complete", 1, 1),
        ("_0_0", "comp", 1971, "incomplete", 1, 1),  # partial water year
        ("_0_0", "comp", 1972, "complete", 0, 2),  # unknown outcomes: occurrence count not pinned
        ("_0_0", "comp", 1973, "complete", 1, 2),  # at least one occurrence is certain
        ("_0_0", "other", 1974, "complete", 0, 0),  # another outcome column
    ])
    row = ap.annual_probability_by_scenario(path, "comp").loc["_0_0"]
    assert (row["eligible_water_years"], row["occurrence_water_years"]) == (2, 2)
    assert row["annual_probability"] == pytest.approx(1.0)


def test_no_eligible_water_years_is_nan(tmp_path):
    path = write_summary(tmp_path / "x_summary.xlsx", [
        ("_0_0", "comp", 1970, "incomplete", 1, 1),
    ])
    row = ap.annual_probability_by_scenario(path, "comp").loc["_0_0"]
    assert row["eligible_water_years"] == 0
    assert math.isnan(row["annual_probability"])


def test_write_outputs_writes_table_grid_and_plot(tmp_path):
    rows = []
    for p in (0, 5):
        for t in (0, 1.5, 3):
            events = 1 if t > 0 else 0
            rows.append((f"_{p}_{t}", "comp", 1970, "complete", events, events))
            rows.append((f"_{p}_{t}", "comp", 1971, "complete", 0, 0))
    summary = write_summary(tmp_path / "comp_summary.xlsx", rows)
    plots = []

    def fake_plot(xs, ys, zs, **kwargs):
        plots.append((zs, kwargs))

    written = ap.write_outputs(
        summary, "comp", tmp_path, success_pattern=False, plot_enabled=True,
        plot_options={"color_map": "RdBu", "threshold": 0.4}, plot_fn=fake_plot,
    )

    assert {p.name for p in written} == {
        "comp_annual_probability.csv", "comp_grid.csv", "comp_plot.png"
    }
    table = pd.read_csv(tmp_path / "comp_annual_probability.csv", index_col="scenario")
    assert table.loc["_0_1.5", "annual_probability"] == pytest.approx(0.5)
    assert (tmp_path / "comp_grid.csv").exists()
    zs, kwargs = plots[0]
    assert kwargs["save_path"] == tmp_path / "comp_plot.png"
    assert kwargs["show"] is False
    assert kwargs["color_map"] == "RdBu_r"  # not success_pattern: red = more occurrences
    assert "annual probability" in kwargs["labels"][2].lower()


def test_write_outputs_without_plot_writes_table_only(tmp_path):
    summary = write_summary(tmp_path / "comp_summary.xlsx", [
        ("_0_0", "comp", 1970, "complete", 1, 1),
    ])
    written = ap.write_outputs(
        summary, "comp", tmp_path, success_pattern=True, plot_enabled=False, plot_options={},
    )
    assert [p.name for p in written] == ["comp_annual_probability.csv"]
