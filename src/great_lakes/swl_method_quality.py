"""Statistics for judging swl estimation methods (regression on avg, etc.)."""

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import t  # type: ignore[import-untyped]


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
