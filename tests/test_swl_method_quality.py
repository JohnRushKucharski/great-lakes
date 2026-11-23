"""Tests for swl estimation-method quality statistics."""

import pytest

from great_lakes import swl_method_quality


def test_regression_prediction_reports_line_and_residual_spread():
    result = swl_method_quality.regression_prediction(
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [1.0, 3.0, 4.0, 7.0, 8.0],
        target_x=2.0,
    )

    assert result.slope == pytest.approx(1.8)
    assert result.prediction == pytest.approx(4.6)
    assert result.residual_sd > 0
    assert result.lower_95 < result.prediction < result.upper_95


def test_regression_prediction_requires_three_points():
    with pytest.raises(ValueError):
        swl_method_quality.regression_prediction([0.0, 1.0], [1.0, 2.0], target_x=0.5)
