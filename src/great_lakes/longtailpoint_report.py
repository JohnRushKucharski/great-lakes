"""Generate analysis tables and figures for the Long Tail Point SWL memo."""

import argparse
from dataclasses import dataclass
from math import ceil, exp, factorial
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from climate_canvas.data_utilities import (  # type: ignore[import-untyped]
    check_threshold,
    evenly_space,
    resample_resolution,
)
from climate_canvas.data_utilities import (  # type: ignore[import-untyped]
    contour_levels as canvas_contour_levels,
)
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
from matplotlib.ticker import FormatStrFormatter
from scipy.stats import t  # type: ignore[import-untyped]

from great_lakes import batch_run_swl, common_swl, fillin_swl

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = WORKSPACE_ROOT / "data" / "clean"
SWL_PATH = WORKSPACE_ROOT / "data" / "extrapolated" / "michigan_swl.xlsx"
PRESENTATION_DIR = WORKSPACE_ROOT / "longtailpoint" / "presentation"

SAVE_POINT_ID = 4999
PRIMARY_ARI = 15.0
RUNUP_ALLOWANCES_FT = (0.0, 2.0, 2.5, 3.0)
DESIGN_ELEVATIONS_FT = (584.0, 586.0)
KNOWN_SUFFIXES = {"_0_0", "_5_1.5", "_10_5", "_20_5", "_0_7"}
INTERPOLATED_SUFFIXES = {
    "_0_1.5", "_0_3", "_0_5", "_5_3", "_5_5", "_10_3", "_15_5",
}
EXTRAPOLATED_SUFFIXES = {"_15_3", "_5_7", "_10_7", "_15_7", "_20_7"}
WARMING_SCENARIOS = {
    1.5: ("_0_1.5", "_5_1.5"),
    3.0: ("_0_3", "_5_3", "_10_3", "_15_3"),
}
STATUS_MARKS = {"known": "", "interpolated": "*", "extrapolated": "**"}
WINDOW_CATEGORIES = ("0", "1", "2", "3+")
TIMELINE_YEARS = 100
RANDOM_SEED = 20261028
REPORT_OUTPUT_NAMES = (
    "4999_ari15_elevation.csv",
    "4999_ari15_elevation.png",
    "4999_ari15_p2d00runup.csv",
    "4999_ari15_p2d00runup.png",
    "B1_known_residuals.csv",
    "B1_regression_predictions.csv",
    "B1_swl_avg_regression.png",
    "F2_scenario_avg_change.csv",
    "F2_scenario_avg_change.png",
    "F3_annual_high_years.csv",
    "F3_avg_persistence.png",
    "F3_persistence_summary.csv",
    "LOO_interpolation.csv",
    "LOO_row_shift.csv",
    "T1_design_coverage.csv",
    "T2_poisson_examples.csv",
)


@dataclass(frozen=True)
class RegressionPrediction:
    """Linear prediction and residual-based 95% prediction interval."""

    slope: float
    intercept: float
    prediction: float
    residual_sd: float
    lower_95: float
    upper_95: float


def annual_maxima(monthly: pd.DataFrame) -> pd.DataFrame:
    """Return each scenario's annual maximum monthly level, indexed by year."""
    frame = monthly.copy()
    frame["year"] = frame["time"].astype(str).str.slice(0, 4).astype(int)
    return frame.groupby("year", sort=True).max(numeric_only=True)


def high_year_flags(values: pd.Series, fraction: float = 1 / 15) -> pd.Series:
    """Mark exactly the highest `fraction` of records, breaking ties by row order."""
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be greater than 0 and at most 1")
    count = ceil(len(values) * fraction)
    return values.rank(method="first", ascending=False) <= count


def rolling_window_category_shares(
    flags: pd.Series, window_years: int = 15
) -> dict[str, float]:
    """Return shares of overlapping windows with 0, 1, 2, or 3+ flagged years."""
    if window_years < 1 or len(flags) < window_years:
        raise ValueError("flags must contain at least one complete window")
    counts = np.convolve(flags.to_numpy(dtype=int), np.ones(window_years, dtype=int), "valid")
    return {
        category: float(np.count_nonzero(_category_mask(counts, category)) / len(counts))
        for category in WINDOW_CATEGORIES
    }


def _category_mask(counts: np.ndarray, category: str) -> np.ndarray:
    if category == "3+":
        return counts >= 3
    return counts == int(category)


def poisson_window_category_shares(rate: float = 1.0) -> dict[str, float]:
    """Return Poisson probabilities for 0, 1, 2, and 3+ events in a window."""
    if rate < 0:
        raise ValueError("rate cannot be negative")
    probabilities = [exp(-rate) * rate**count / factorial(count) for count in range(3)]
    return dict(zip(WINDOW_CATEGORIES, [*probabilities, 1.0 - sum(probabilities)]))


def poisson_probability_at_least(minimum_count: int, rate: float = 1.0) -> float:
    """Return the Poisson probability of at least `minimum_count` events."""
    if minimum_count < 0 or rate < 0:
        raise ValueError("minimum_count and rate cannot be negative")
    below = sum(exp(-rate) * rate**count / factorial(count) for count in range(minimum_count))
    return 1.0 - below


def regression_prediction(
    x_values: Sequence[float], y_values: Sequence[float], target_x: float
) -> RegressionPrediction:
    """Fit ordinary least squares and calculate a 95% prediction interval."""
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if len(x) != len(y) or len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("regression requires at least three finite, paired observations")
    x_mean = float(x.mean())
    centered_x = x - x_mean
    sum_squares_x = float(centered_x @ centered_x)
    if sum_squares_x == 0:
        raise ValueError("regression requires variation in x")
    slope = float(centered_x @ (y - y.mean()) / sum_squares_x)
    intercept = float(y.mean() - slope * x_mean)
    residuals = y - (intercept + slope * x)
    residual_sd = float(np.sqrt((residuals @ residuals) / (len(x) - 2)))
    prediction = intercept + slope * target_x
    standard_error = residual_sd * np.sqrt(
        1 + 1 / len(x) + (target_x - x_mean) ** 2 / sum_squares_x
    )
    margin = float(t.ppf(0.975, len(x) - 2) * standard_error)
    return RegressionPrediction(
        slope=slope,
        intercept=intercept,
        prediction=float(prediction),
        residual_sd=residual_sd,
        lower_95=float(prediction - margin),
        upper_95=float(prediction + margin),
    )


def _scenario_status(suffix: str) -> str:
    if suffix in KNOWN_SUFFIXES:
        return "known"
    if suffix in INTERPOLATED_SUFFIXES:
        return "interpolated"
    if suffix in EXTRAPOLATED_SUFFIXES:
        return "extrapolated"
    raise ValueError(f"Unclassified scenario {suffix!r}")


def _load_scenario_sheets(swl_path: Path) -> dict[str, pd.DataFrame]:
    sheets = pd.read_excel(swl_path, sheet_name=None, engine="calamine")
    by_suffix: dict[str, pd.DataFrame] = {}
    for sheet_name, frame in sheets.items():
        suffix = common_swl.parse_scenario_sheet_name(sheet_name)
        if suffix is None:
            continue
        if suffix in by_suffix:
            raise ValueError(f"Multiple SWL sheets found for scenario {suffix}")
        by_suffix[suffix] = frame
    expected = set(fillin_swl.ALL_SCENARIO_SUFFIXES)
    if by_suffix.keys() != expected:
        raise ValueError(
            "SWL workbook scenarios do not match the expected 17-scenario set: "
            f"missing={sorted(expected - by_suffix.keys())}, "
            f"extra={sorted(by_suffix.keys() - expected)}"
        )
    return by_suffix


def _ari_columns(frame: pd.DataFrame) -> list[tuple[float, str | int | float]]:
    columns = []
    for column in frame.columns:
        if column in common_swl.NON_ARI_COLUMNS:
            continue
        if not isinstance(column, (str, int, float)):
            raise ValueError(f"Unexpected ARI column type: {type(column).__name__}")
        columns.append((float(column), column))
    return sorted(columns)


def _save_point_row(frame: pd.DataFrame, save_point_id: int) -> pd.Series:
    rows = frame.loc[frame["ID"] == save_point_id]
    if len(rows) != 1:
        raise ValueError(f"Expected one row for save point {save_point_id}; found {len(rows)}")
    return rows.iloc[0]


def _scenario_level_ft(
    frame: pd.DataFrame, save_point_id: int, ari: float
) -> float:
    row = _save_point_row(frame, save_point_id)
    columns = _ari_columns(frame)
    value_m = batch_run_swl.interpolate_level(
        [column[0] for column in columns],
        [float(row[column[1]]) for column in columns],
        ari,
    )
    return common_swl.m_igld85_to_ft_NAVD88(value_m)


def _scenario_means(monthly: pd.DataFrame) -> dict[str, float]:
    return {suffix: float(monthly[suffix].mean()) for suffix in fillin_swl.ALL_SCENARIO_SUFFIXES}


def m_igld85_delta_to_ft_NAVD88(delta_m_igld85: float) -> float:
    """Convert an IGLD85 elevation difference to ft without applying datum offset."""
    return (
        common_swl.m_igld85_to_ft_NAVD88(delta_m_igld85)
        - common_swl.m_igld85_to_ft_NAVD88(0.0)
    )


def _scenario_coordinates(suffix: str) -> tuple[float, float]:
    coordinates = parse_scenario_name(suffix)
    if coordinates is None:
        raise ValueError(f"Invalid scenario suffix {suffix!r}")
    return coordinates


def _save_grid_csv(
    values: dict[str, float], output_path: Path, offset_ft: float = 0.0
) -> None:
    coordinates = {suffix: _scenario_coordinates(suffix) for suffix in values}
    precips = sorted({point[0] for point in coordinates.values()})
    temps = sorted({point[1] for point in coordinates.values()})
    grid = pd.DataFrame(index=temps, columns=precips, dtype=float)
    grid.index.name = "temp_delta\\precip_delta"
    for suffix, value in values.items():
        precip, temp = coordinates[suffix]
        grid.loc[temp, precip] = value + offset_ft
    grid.to_csv(output_path)


def _cell_edges(centers: Sequence[float]) -> np.ndarray:
    points = np.asarray(centers, dtype=float)
    midpoints = (points[:-1] + points[1:]) / 2
    return np.concatenate(([points[0] - (midpoints[0] - points[0])], midpoints,
                           [points[-1] + (points[-1] - midpoints[-1])]))


def _draw_scenario_grid(
    ax: plt.Axes,
    values: dict[str, float],
    value_label: str,
    focus_suffixes: set[str] | None = None,
    contour_levels: Sequence[float] = (),
    value_fontsize: float = 8,
    threshold: float | None = None,
    blocky: bool = False,
) -> None:
    """Draw the scenario surface.

    Default: climate_canvas style (RdBu, bilinear resampling, centered on `threshold`).
    `blocky`: one flat cell per scenario (no interpolation), same RdBu scale and ticks.
    """
    coordinates = {suffix: _scenario_coordinates(suffix) for suffix in values}
    precips = sorted({point[0] for point in coordinates.values()})
    temps = sorted({point[1] for point in coordinates.values()})
    grid = np.full((len(temps), len(precips)), np.nan)
    for suffix, value in values.items():
        precip, temp = coordinates[suffix]
        grid[temps.index(temp), precips.index(precip)] = value
    if blocky:
        z_range = (float(np.nanmin(grid)), float(np.nanmax(grid)))
        norm = TwoSlopeNorm(
            vmin=z_range[0], vcenter=check_threshold(threshold, z_range), vmax=z_range[1]
        )
        image = ax.pcolormesh(
            _cell_edges(precips), _cell_edges(temps), np.ma.masked_invalid(grid),
            shading="flat", cmap="RdBu", norm=norm,
        )
        tick_levels, _ = canvas_contour_levels(z_range, norm.vcenter)
    else:
        fine_x, fine_y, fine_z = evenly_space(
            np.asarray(precips), np.asarray(temps), grid, None,
            (resample_resolution(len(precips)), resample_resolution(len(temps))),
        )
        z_range = (float(np.nanmin(fine_z)), float(np.nanmax(fine_z)))
        norm = TwoSlopeNorm(
            vmin=z_range[0], vcenter=check_threshold(threshold, z_range), vmax=z_range[1]
        )
        image = ax.pcolormesh(fine_x, fine_y, fine_z, shading="nearest", cmap="RdBu", norm=norm)
    colorbar = ax.figure.colorbar(image, ax=ax, label=value_label)
    if blocky:
        colorbar.set_ticks(list(tick_levels))
    colorbar.ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    for suffix, value in values.items():
        precip, temp = coordinates[suffix]
        known = _scenario_status(suffix) == "known"
        mark = STATUS_MARKS[_scenario_status(suffix)]
        if blocky:
            x_index, y_index = precips.index(precip), temps.index(temp)
            left, right = _cell_edges(precips)[x_index:x_index + 2]
            bottom, top = _cell_edges(temps)[y_index:y_index + 2]
            if known:
                # white halo under black line keeps the outline visible on dark cells
                for color, width in (("white", 3.0), ("black", 1.4)):
                    ax.add_patch(
                        Rectangle(
                            (left, bottom), right - left, top - bottom,
                            fill=False, edgecolor=color, linewidth=width, zorder=3,
                        )
                    )
            ax.text(
                precip, temp, f"{value:.1f}{mark}", ha="center", va="center",
                fontsize=value_fontsize, zorder=6,
                bbox={
                    "boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.88,
                    "edgecolor": "none",
                },
            )
            continue
        if focus_suffixes and suffix in focus_suffixes:
            ax.add_patch(
                Rectangle(
                    (precip - 1.6, temp - 0.3), 3.2, 0.6,
                    fill=False, edgecolor="#159d8c", linewidth=2.2, zorder=5,
                )
            )
        ax.text(
            precip, temp, f"{value:.1f}{mark}", ha="center", va="center",
            fontsize=value_fontsize, zorder=6,
            bbox={
                "boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.75,
                "edgecolor": "black" if known else "none", "linewidth": 0.9,
            },
        )
    if contour_levels and blocky:
        ordered = sorted(values, key=lambda suffix: coordinates[suffix])
        points = np.asarray([coordinates[suffix] for suffix in ordered])
        z_values = np.asarray([values[suffix] for suffix in ordered])
        ax.tricontour(
            points[:, 0], points[:, 1], z_values, levels=list(contour_levels),
            colors="#252525", linestyles=("--", "-"), linewidths=1.5, zorder=4,
        )
    elif contour_levels:
        ax.contour(
            fine_x, fine_y, fine_z, levels=list(contour_levels),
            colors="#252525", linestyles=("--", "-"), linewidths=1.5,
        )
    ax.set_xticks(precips)
    ax.set_yticks(temps)
    ax.set_xlabel("Precipitation delta (%)")
    ax.set_ylabel("Temperature delta (C)")
    x_edges = _cell_edges(precips)
    y_edges = _cell_edges(temps)
    ax.set_xlim(float(x_edges[0]), float(x_edges[-1]))
    ax.set_ylim(float(y_edges[0]), float(y_edges[-1]))


def _write_f2(means: dict[str, float], output_dir: Path) -> None:
    baseline = means["_0_0"]
    rows = []
    for suffix in fillin_swl.ALL_SCENARIO_SUFFIXES:
        precip, temp = _scenario_coordinates(suffix)
        rows.append(
            {
                "scenario": suffix,
                "precip_delta_pct": precip,
                "temp_delta_c": temp,
                "status": _scenario_status(suffix),
                "avg_mean_m_igld85": means[suffix],
                "avg_change_ft": (means[suffix] - baseline) * common_swl.METERS_TO_FEET,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "F2_scenario_avg_change.csv", index=False)
    fig, ax = plt.subplots(figsize=(10, 7))
    _draw_scenario_grid(ax, dict(zip(frame["scenario"], frame["avg_change_ft"])),
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


def _write_f3(
    annual: pd.DataFrame, means: dict[str, float], output_dir: Path
) -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    poisson = poisson_window_category_shares()
    summary_rows = []
    annual_rows: list[dict[str, object]] = []
    case_data: list[tuple[str, str, pd.Series, pd.Series, dict[str, float], float]] = []
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
    _plot_f3(case_data, annual.index, poisson, output_dir)


def _plot_f3(
    case_data: list[tuple[str, str, pd.Series, pd.Series, dict[str, float], float]],
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


def _write_t1(
    sheets: dict[str, pd.DataFrame], output_dir: Path
) -> dict[str, float]:
    thresholds = {
        suffix: _scenario_level_ft(sheets[suffix], SAVE_POINT_ID, PRIMARY_ARI)
        for suffix in fillin_swl.ALL_SCENARIO_SUFFIXES
    }
    rows = []
    for design in DESIGN_ELEVATIONS_FT:
        for runup in RUNUP_ALLOWANCES_FT:
            for temp, suffixes in WARMING_SCENARIOS.items():
                adjusted = {suffix: thresholds[suffix] + runup for suffix in suffixes}
                worst_suffix = max(adjusted, key=lambda suffix: adjusted[suffix])
                passes = sum(value <= design for value in adjusted.values())
                rows.append(
                    {
                        "design_elevation_ft_NAVD88": design,
                        "runup_allowance_ft": runup,
                        "temp_delta_c": temp,
                        "scenario_count": len(suffixes),
                        "coverage_count": passes,
                        "coverage_pct": 100 * passes / len(suffixes),
                        "worst_case_scenario": worst_suffix,
                        "worst_case_threshold_ft_NAVD88": adjusted[worst_suffix],
                        "margin_to_worst_case_ft": design - adjusted[worst_suffix],
                    }
                )
    pd.DataFrame(rows).to_csv(output_dir / "T1_design_coverage.csv", index=False)
    return thresholds


def _write_t2(output_dir: Path) -> None:
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


def _write_regression_and_loo(
    means: dict[str, float],
    sheets: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    known = sorted(KNOWN_SUFFIXES, key=fillin_swl.ALL_SCENARIO_SUFFIXES.index)
    targets = [
        suffix for suffix in fillin_swl.ALL_SCENARIO_SUFFIXES if suffix not in KNOWN_SUFFIXES
    ]
    x_m = [means[suffix] for suffix in known]
    x_ft = [common_swl.m_igld85_to_ft_NAVD88(value) for value in x_m]
    ari_values = sorted({ari for ari, _ in _ari_columns(sheets[known[0]])} | {PRIMARY_ARI})
    predictions: list[dict[str, object]] = []
    residual_rows: list[dict[str, object]] = []
    model_data: dict[float, tuple[list[float], list[float]]] = {}
    for ari in ari_values:
        y_ft = [
            _scenario_level_ft(sheets[suffix], SAVE_POINT_ID, ari)
            for suffix in known
        ]
        model = regression_prediction(x_ft, y_ft, x_ft[0])
        model_data[ari] = (x_ft, y_ft)
        for suffix, observed in zip(known, y_ft):
            residual_rows.append(
                {
                    "scenario": suffix,
                    "temp_delta_c": _scenario_coordinates(suffix)[1],
                    "ari_years": ari,
                    "observed_swl_ft_NAVD88": observed,
                    "slope": model.slope,
                    "intercept_ft_NAVD88": model.intercept,
                    "residual_ft": observed - (model.intercept + model.slope *
                                               common_swl.m_igld85_to_ft_NAVD88(means[suffix])),
                }
            )
        for suffix in targets:
            target_x = common_swl.m_igld85_to_ft_NAVD88(means[suffix])
            estimate = regression_prediction(x_ft, y_ft, target_x)
            predictions.append(
                {
                    "scenario": suffix,
                    "status": _scenario_status(suffix),
                    "temp_delta_c": _scenario_coordinates(suffix)[1],
                    "ari_years": ari,
                    "avg_ft_NAVD88": target_x,
                    "inside_known_avg_range": min(x_ft) <= target_x <= max(x_ft),
                    "slope": estimate.slope,
                    "intercept_ft_NAVD88": estimate.intercept,
                    "residual_sd_ft": estimate.residual_sd,
                    "prediction_ft_NAVD88": estimate.prediction,
                    "lower_95_ft_NAVD88": estimate.lower_95,
                    "upper_95_ft_NAVD88": estimate.upper_95,
                    "interval_width_ft": estimate.upper_95 - estimate.lower_95,
                }
            )
    predictions_frame = pd.DataFrame(predictions)
    residual_frame = pd.DataFrame(residual_rows)
    predictions_frame.to_csv(output_dir / "B1_regression_predictions.csv", index=False)
    residual_frame.to_csv(output_dir / "B1_known_residuals.csv", index=False)
    _write_b1_plot(predictions_frame, model_data[PRIMARY_ARI], output_dir)
    _write_loo_row_shift(means, sheets, ari_values, output_dir)
    _write_loo_interpolation(sheets, ari_values, output_dir)


def _write_b1_plot(
    predictions: pd.DataFrame,
    known_data: tuple[list[float], list[float]],
    output_dir: Path,
) -> None:
    x_known, y_known = known_data
    x_targets = predictions.loc[predictions["ari_years"] == PRIMARY_ARI]
    x_range = np.linspace(
        min(x_known + x_targets["avg_ft_NAVD88"].tolist()),
        max(x_known + x_targets["avg_ft_NAVD88"].tolist()),
        100,
    )
    model_line = [regression_prediction(x_known, y_known, x) for x in x_range]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.fill_between(
        x_range,
        [model.lower_95 for model in model_line],
        [model.upper_95 for model in model_line],
        color="#9ab7c4", alpha=0.35, label="95% prediction interval",
    )
    ax.plot(x_range, [model.prediction for model in model_line], color="#294c60",
            label="OLS fit")
    ax.scatter(x_known, y_known, color="#294c60", label="5 modeled scenarios", zorder=3)
    for status, marker in (("interpolated", "^"), ("extrapolated", "s")):
        group = x_targets.loc[x_targets["status"] == status]
        ax.scatter(group["avg_ft_NAVD88"], group["prediction_ft_NAVD88"], marker=marker,
                   label=f"{status.title()} predictions", zorder=3)
    ax.set_xlabel("Full-record average lake level (ft, NAVD88)")
    ax.set_ylabel("15-year ARI storm water level (ft, NAVD88)")
    ax.set_title("SWL vs AVG: 5 modeled scenarios; target estimates are illustrative")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "B1_swl_avg_regression.png", dpi=180)
    plt.close(fig)


def _write_loo_row_shift(
    means: dict[str, float],
    sheets: dict[str, pd.DataFrame],
    ari_values: Sequence[float],
    output_dir: Path,
) -> None:
    rows = []
    for anchor, target in (("_10_5", "_20_5"), ("_20_5", "_10_5")):
        for ari in ari_values:
            anchor_level = _scenario_level_ft(sheets[anchor], SAVE_POINT_ID, ari)
            observed = _scenario_level_ft(sheets[target], SAVE_POINT_ID, ari)
            delta_ft = m_igld85_delta_to_ft_NAVD88(means[target] - means[anchor])
            predicted = anchor_level + delta_ft
            error = predicted - observed
            rows.append(
                {
                    "method": "same-warming-row AVG shift",
                    "anchor_scenario": anchor,
                    "target_scenario": target,
                    "ari_years": ari,
                    "predicted_ft_NAVD88": predicted,
                    "observed_ft_NAVD88": observed,
                    "error_ft": error,
                    "abs_error_ft": abs(error),
                    "within_0d5ft_of_2ft_design_gap": abs(error) <= 0.5,
                }
            )
    pd.DataFrame(rows).to_csv(output_dir / "LOO_row_shift.csv", index=False)


def _write_loo_interpolation(
    sheets: dict[str, pd.DataFrame],
    ari_values: Sequence[float],
    output_dir: Path,
) -> None:
    rows = []
    for target in ("_5_1.5", "_10_5"):
        remaining = [suffix for suffix in KNOWN_SUFFIXES if suffix != target]
        coordinates = {suffix: _scenario_coordinates(suffix) for suffix in remaining}
        weights = fillin_swl.build_barycentric_weights(coordinates, [target])[target]
        vertices, coefficients = weights
        for ari in ari_values:
            observed = _scenario_level_ft(sheets[target], SAVE_POINT_ID, ari)
            predicted = sum(
                weight * _scenario_level_ft(sheets[vertex], SAVE_POINT_ID, ari)
                for vertex, weight in zip(vertices, coefficients)
            )
            error = predicted - observed
            rows.append(
                {
                    "method": "leave-one-out Delaunay interpolation",
                    "target_scenario": target,
                    "ari_years": ari,
                    "vertex_scenarios": "|".join(vertices),
                    "barycentric_weights": "|".join(f"{weight:.6f}" for weight in coefficients),
                    "predicted_ft_NAVD88": predicted,
                    "observed_ft_NAVD88": observed,
                    "error_ft": error,
                    "abs_error_ft": abs(error),
                    "within_0d5ft_of_2ft_design_gap": abs(error) <= 0.5,
                }
            )
    pd.DataFrame(rows).to_csv(output_dir / "LOO_interpolation.csv", index=False)


def run(
    data_dir: Path = DATA_DIR,
    swl_path: Path = SWL_PATH,
    output_dir: Path = PRESENTATION_DIR,
) -> list[Path]:
    """Generate phase-3 memo analyses from cleaned AVG and extrapolated SWL inputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(data_dir / "michiganhuron_avg.csv")
    annual = annual_maxima(monthly)
    means = _scenario_means(monthly)
    sheets = _load_scenario_sheets(swl_path)
    _write_f2(means, output_dir)
    _write_f3(annual, means, output_dir)
    thresholds = _write_t1(sheets, output_dir)
    _write_t2(output_dir)
    _write_regression_and_loo(means, sheets, output_dir)
    _write_f4(thresholds, output_dir)
    return [output_dir / name for name in REPORT_OUTPUT_NAMES]


def _write_f4(thresholds: dict[str, float], output_dir: Path) -> None:
    write_presentation_figure(
        thresholds,
        output_dir / "4999_ari15_elevation.png",
        output_dir / "4999_ari15_elevation.csv",
        SAVE_POINT_ID,
        PRIMARY_ARI,
    )
    write_presentation_figure(
        thresholds,
        output_dir / "4999_ari15_p2d00runup.png",
        output_dir / "4999_ari15_p2d00runup.csv",
        SAVE_POINT_ID,
        PRIMARY_ARI,
        elevation_offset_ft=2.0,
    )


def write_presentation_figure(
    values: dict[str, float],
    output_path: Path,
    csv_path: Path,
    save_point_id: int,
    ari: float,
    elevation_offset_ft: float = 0.0,
) -> Path:
    """Write a marked threshold-ARI surface with optional runup allowance."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _save_grid_csv(values, csv_path, offset_ft=elevation_offset_ft)
    fig, ax = plt.subplots(figsize=(10, 7))
    _draw_scenario_grid(
        ax,
        {suffix: value + elevation_offset_ft for suffix, value in values.items()},
        f"{ari:g}-year ARI elevation (ft, NAVD88)",
        contour_levels=(584.0, 586.0),
        value_fontsize=10,
        blocky=True,
        threshold=values["_0_0"] + elevation_offset_ft,
    )
    runup_text = f" - +{elevation_offset_ft:g} ft runup" if elevation_offset_ft else ""
    ax.set_title(f"Save point {save_point_id} - {ari:g}-year ARI{runup_text}")
    fig.text(
        0.01, 0.01,
        "Solid: 586 ft; dashed: 584 ft. Black outline: modeled; * interpolated; "
        "** extrapolated. SWL excludes runup.",
    )
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--swl-path", type=Path, default=SWL_PATH)
    parser.add_argument("--output-dir", type=Path, default=PRESENTATION_DIR)
    args = parser.parse_args()
    for path in run(args.data_dir, args.swl_path, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
