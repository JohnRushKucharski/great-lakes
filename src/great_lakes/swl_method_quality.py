"""Statistics for judging swl estimation methods (regression on avg, leave-one-out checks)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t  # type: ignore[import-untyped]

from great_lakes import units
from great_lakes.scenario_grid import (
    KNOWN_SUFFIXES,
    ari_columns,
    load_scenario_sheets,
    scenario_coordinates,
    scenario_level_ft,
    scenario_means,
    scenario_status,
)
from great_lakes.swl import complete as swl_complete

SAVE_POINT_ID = 4999
PRIMARY_ARI = 15.0
OUTPUT_NAMES = (
    "B1_known_residuals.csv",
    "B1_regression_predictions.csv",
    "B1_swl_avg_regression.png",
    "LOO_interpolation.csv",
    "LOO_row_shift.csv",
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


def run(
    avg_csv: Path,
    swl_path: Path,
    output_dir: Path,
    save_point_id: int = SAVE_POINT_ID,
    ari: float = PRIMARY_ARI,
) -> list[Path]:
    """Regression of swl on avg (from the 5 modeled scenarios) and leave-one-out checks.

    Uses one save point; `ari` is the ARI shown in the regression plot (it is always
    included among the tabulated ARIs).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    means = scenario_means(pd.read_csv(avg_csv))
    sheets = load_scenario_sheets(swl_path)
    write_regression_and_loo(means, sheets, output_dir, save_point_id, ari)
    return [output_dir / name for name in OUTPUT_NAMES]


def write_regression_and_loo(
    means: dict[str, float],
    sheets: dict[str, pd.DataFrame],
    output_dir: Path,
    save_point_id: int = SAVE_POINT_ID,
    primary_ari: float = PRIMARY_ARI,
) -> None:
    """B1 regression tables and plot, then the two leave-one-out tables."""
    known = sorted(KNOWN_SUFFIXES, key=swl_complete.ALL_SCENARIO_SUFFIXES.index)
    targets = [
        suffix for suffix in swl_complete.ALL_SCENARIO_SUFFIXES if suffix not in KNOWN_SUFFIXES
    ]
    x_m = [means[suffix] for suffix in known]
    x_ft = [units.m_igld85_to_ft_NAVD88(value) for value in x_m]
    ari_values = sorted({ari for ari, _ in ari_columns(sheets[known[0]])} | {primary_ari})
    predictions: list[dict[str, object]] = []
    residual_rows: list[dict[str, object]] = []
    model_data: dict[float, tuple[list[float], list[float]]] = {}
    for ari in ari_values:
        y_ft = [scenario_level_ft(sheets[suffix], save_point_id, ari) for suffix in known]
        model = regression_prediction(x_ft, y_ft, x_ft[0])
        model_data[ari] = (x_ft, y_ft)
        for suffix, observed in zip(known, y_ft):
            residual_rows.append(
                {
                    "scenario": suffix,
                    "temp_delta_c": scenario_coordinates(suffix)[1],
                    "ari_years": ari,
                    "observed_swl_ft_NAVD88": observed,
                    "slope": model.slope,
                    "intercept_ft_NAVD88": model.intercept,
                    "residual_ft": observed - (model.intercept + model.slope *
                                               units.m_igld85_to_ft_NAVD88(means[suffix])),
                }
            )
        for suffix in targets:
            target_x = units.m_igld85_to_ft_NAVD88(means[suffix])
            estimate = regression_prediction(x_ft, y_ft, target_x)
            predictions.append(
                {
                    "scenario": suffix,
                    "status": scenario_status(suffix),
                    "temp_delta_c": scenario_coordinates(suffix)[1],
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
    _write_b1_plot(predictions_frame, model_data[primary_ari], primary_ari, output_dir)
    _write_loo_row_shift(means, sheets, ari_values, save_point_id, output_dir)
    _write_loo_interpolation(sheets, ari_values, save_point_id, output_dir)


def _write_b1_plot(
    predictions: pd.DataFrame,
    known_data: tuple[list[float], list[float]],
    primary_ari: float,
    output_dir: Path,
) -> None:
    x_known, y_known = known_data
    x_targets = predictions.loc[predictions["ari_years"] == primary_ari]
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
    ax.set_ylabel(f"{primary_ari:g}-year ARI storm water level (ft, NAVD88)")
    ax.set_title("SWL vs AVG: 5 modeled scenarios; target estimates are illustrative")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "B1_swl_avg_regression.png", dpi=180)
    plt.close(fig)


def _write_loo_row_shift(
    means: dict[str, float],
    sheets: dict[str, pd.DataFrame],
    ari_values: Sequence[float],
    save_point_id: int,
    output_dir: Path,
) -> None:
    rows = []
    for anchor, target in (("_10_5", "_20_5"), ("_20_5", "_10_5")):
        for ari in ari_values:
            anchor_level = scenario_level_ft(sheets[anchor], save_point_id, ari)
            observed = scenario_level_ft(sheets[target], save_point_id, ari)
            delta_ft = units.m_delta_to_ft(means[target] - means[anchor])
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
    save_point_id: int,
    output_dir: Path,
) -> None:
    rows = []
    for target in ("_5_1.5", "_10_5"):
        remaining = [
            suffix for suffix in swl_complete.ALL_SCENARIO_SUFFIXES
            if suffix in KNOWN_SUFFIXES and suffix != target
        ]
        coordinates = {suffix: scenario_coordinates(suffix) for suffix in remaining}
        weights = swl_complete.build_barycentric_weights(coordinates, [target])[target]
        vertices, coefficients = weights
        for ari in ari_values:
            observed = scenario_level_ft(sheets[target], save_point_id, ari)
            predicted = sum(
                weight * scenario_level_ft(sheets[vertex], save_point_id, ari)
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
