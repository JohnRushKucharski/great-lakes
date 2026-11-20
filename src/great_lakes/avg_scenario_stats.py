"""avg statistics across the 17 scenarios: mean change, high-year persistence, Poisson counts."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from great_lakes import units
from great_lakes.avg_stats import (
    WINDOW_CATEGORIES,
    annual_maxima,
    high_year_flags,
    poisson_probability_at_least,
    poisson_window_category_shares,
    rolling_window_category_shares,
)
from great_lakes.scenario_grid import (
    WARMING_SCENARIOS,
    draw_scenario_grid,
    scenario_coordinates,
    scenario_means,
    scenario_status,
)
from great_lakes.swl import complete as swl_complete

TIMELINE_YEARS = 100
RANDOM_SEED = 20261028
OUTPUT_NAMES = (
    "F2_scenario_avg_change.csv",
    "F2_scenario_avg_change.png",
    "F3_annual_high_years.csv",
    "F3_avg_persistence.png",
    "F3_persistence_summary.csv",
    "T2_poisson_examples.csv",
)

_CaseData = tuple[str, str, pd.Series, pd.Series, dict[str, float], float]


def run(avg_csv: Path, output_dir: Path) -> list[Path]:
    """Write the scenario avg statistics for one avg csv (17 scenario columns) to `output_dir`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(avg_csv)
    write_scenario_avg_change(scenario_means(monthly), output_dir)
    write_persistence(annual_maxima(monthly), scenario_means(monthly), output_dir)
    write_poisson_examples(output_dir)
    return [output_dir / name for name in OUTPUT_NAMES]


def write_scenario_avg_change(means: dict[str, float], output_dir: Path) -> None:
    """Full-record mean avg change from baseline per scenario (csv + scenario-grid figure)."""
    baseline = means["_0_0"]
    rows = []
    for suffix in swl_complete.ALL_SCENARIO_SUFFIXES:
        precip, temp = scenario_coordinates(suffix)
        rows.append(
            {
                "scenario": suffix,
                "precip_delta_pct": precip,
                "temp_delta_c": temp,
                "status": scenario_status(suffix),
                "avg_mean_m_igld85": means[suffix],
                "avg_change_ft": units.convert_units(means[suffix] - baseline, "m", "ft"),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "F2_scenario_avg_change.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 7))
    draw_scenario_grid(ax, dict(zip(frame["scenario"], frame["avg_change_ft"])),
                       "AVG change vs baseline (ft)", value_fontsize=10, blocky=True,
                       threshold=0.0)
    ax.set_title("Full-record average lake level change from baseline")
    fig.text(
        0.01, 0.01,
        "Black outline: modeled; * interpolated; ** extrapolated.",
    )
    fig.savefig(output_dir / "F2_scenario_avg_change.png", dpi=180)
    plt.close(fig)


def _persistence_cases(means: dict[str, float]) -> list[tuple[str, str]]:
    cases = [("_0_0", "baseline")]
    for temp, suffixes in WARMING_SCENARIOS.items():
        low = min(suffixes, key=lambda suffix: means[suffix])
        high = max(suffixes, key=lambda suffix: means[suffix])
        cases.extend(((low, f"{temp:g} C low AVG"), (high, f"{temp:g} C high AVG")))
    return cases


def write_persistence(annual: pd.DataFrame, means: dict[str, float], output_dir: Path) -> None:
    """High-year persistence (lag-1 correlation, 15-year window shares) for 5 cases."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)
    poisson = poisson_window_category_shares()
    summary_rows = []
    annual_rows: list[dict[str, object]] = []
    case_data: list[_CaseData] = []
    for suffix, label in _persistence_cases(means):
        values = annual[suffix]
        flags = high_year_flags(values)
        shuffled = pd.Series(rng.permutation(flags.to_numpy()), index=flags.index)
        actual_shares = rolling_window_category_shares(flags)
        lag1 = float(values.autocorr(lag=1))
        summary_rows.append(
            {
                "scenario": suffix,
                "case": label,
                "avg_mean_m_igld85": means[suffix],
                "lag1_correlation": lag1,
                "high_year_count": int(flags.sum()),
                "annual_record_count": len(flags),
                **{f"actual_window_share_{k}": v for k, v in actual_shares.items()},
            }
        )
        annual_rows.extend(
            {
                "scenario": suffix,
                "case": label,
                "year": int(year),
                "annual_max_monthly_avg_m_IGLD85": float(value),
                "high_year": bool(flag),
                "shuffled_high_year": bool(shuffled_flag),
            }
            for year, value, flag, shuffled_flag in zip(
                annual.index.to_numpy(),
                values.to_numpy(dtype=float),
                flags.to_numpy(dtype=bool),
                shuffled.to_numpy(dtype=bool),
                strict=True,
            )
        )
        case_data.append((suffix, label, flags, shuffled, actual_shares, lag1))
    summary = pd.DataFrame(summary_rows)
    summary["lag1_low_high_delta"] = np.nan
    for temp in (1.5, 3.0):
        mask = summary["case"].str.startswith(f"{temp:g} C")
        correlation = summary.loc[mask, "lag1_correlation"].to_numpy()
        summary.loc[mask, "lag1_low_high_delta"] = abs(correlation[1] - correlation[0])
    summary.to_csv(output_dir / "F3_persistence_summary.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(output_dir / "F3_annual_high_years.csv", index=False)
    _plot_persistence(case_data, annual.index, poisson, output_dir)


def _plot_persistence(
    case_data: list[_CaseData],
    years: pd.Index,
    poisson: dict[str, float],
    output_dir: Path,
) -> None:
    fig = plt.figure(figsize=(13, 10))
    outer = fig.add_gridspec(3, 1, height_ratios=(1.0, 0.1, 1.5), hspace=0.4)
    timeline = fig.add_subplot(outer[0])
    displayed_years = years[:TIMELINE_YEARS]
    for index, (_, label, flags, shuffled, _, _) in enumerate(case_data):
        start = 2 * index
        for offset, series, name in (
            (0, flags, "actual"),
            (1, shuffled, "shuffled"),
        ):
            selected = series.loc[displayed_years]
            row = start + offset
            timeline.scatter(
                selected.index[selected].to_numpy() - displayed_years[0] + 1,
                np.full(int(selected.sum()), row),
                s=12, color="#246a73" if offset == 0 else "#929292",
            )
    timeline.set_xlim(0, len(displayed_years) + 1)
    timeline.set_ylim(2 * len(case_data), -1)
    timeline.set_yticks(
        range(2 * len(case_data)),
        labels=[
            f"{label} - {name}"
            for _, label, _, _, _, _ in case_data
            for name in ("actual", "shuffled")
        ],
        fontsize=8,
    )
    timeline.set_xlabel(
        f"Synthetic year (1-{len(displayed_years)}; not calendar years; "
        "dots = top 1-in-15 annual maxima)"
    )
    timeline.set_title("A. High-year timing: observed sequence vs shuffled independence")

    heading = fig.add_subplot(outer[1])
    heading.axis("off")
    heading.text(
        0, 0.5, "B. Overlapping 15-year windows: actual vs Poisson(lambda=1)",
        transform=heading.transAxes, va="center", fontsize=11,
    )
    panel = outer[2].subgridspec(2, 3, wspace=0.3, hspace=0.7)
    for index, (suffix, label, _, _, actual, lag1) in enumerate(case_data):
        ax = fig.add_subplot(panel[index // 3, index % 3])
        positions = np.arange(len(WINDOW_CATEGORIES))
        width = 0.38
        ax.bar(positions - width / 2, [actual[c] for c in WINDOW_CATEGORIES],
               width, label="Actual windows", color="#246a73")
        ax.bar(positions + width / 2, [poisson[c] for c in WINDOW_CATEGORIES],
               width, label="Poisson(1)", color="#d39b35")
        ax.set_xticks(positions, WINDOW_CATEGORIES)
        ax.set_ylim(0, 0.72)
        ax.set_title(f"{label} ({suffix})\nr = {lag1:.2f}", fontsize=10)
        if index >= 3:
            ax.set_xlabel("High years per 15-year window")
        if index % 3 == 0:
            ax.set_ylabel("Share of windows")
        if index == 0:
            ax.legend(fontsize=8)
    fig.suptitle("AVG persistence is a proxy for storm water level, not SWL")
    fig.subplots_adjust(left=0.17, right=0.99, top=0.94, bottom=0.08)
    fig.savefig(output_dir / "F3_avg_persistence.png", dpi=180)
    plt.close(fig)


def write_poisson_examples(output_dir: Path) -> None:
    """Probability of at least 1, 3 and 4 exceedance years in 15 years (Poisson, rate 1)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    examples = [
        ("At least 1", "P(N > 0)", poisson_probability_at_least(1)),
        ("At least 3", "P(N > 2)", poisson_probability_at_least(3)),
        ("At least 4", "P(N > 3)", poisson_probability_at_least(4)),
    ]
    pd.DataFrame(
        [
            {
                "label": label,
                "probability": expression,
                "probability_pct": 100 * probability,
                "model": "Poisson(lambda=1 over 15 years)",
                "event_name": "threshold-exceedance / overtopping-proxy years",
            }
            for label, expression, probability in examples
        ]
    ).to_csv(output_dir / "T2_poisson_examples.csv", index=False)
