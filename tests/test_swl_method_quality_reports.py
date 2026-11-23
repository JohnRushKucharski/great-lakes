"""Tests for the swl method-quality report (avg regression and leave-one-out checks)."""
import pandas as pd
import pytest
from ltp_fixtures import SAVE_POINT, monthly_avg, write_swl_workbook

from great_lakes import swl_method_quality as quality


@pytest.fixture
def inputs(tmp_path):
    csv = tmp_path / "michiganhuron_avg.csv"
    monthly_avg().to_csv(csv, index=False)
    write_swl_workbook(tmp_path / "michigan_swl.xlsx")
    return csv, tmp_path / "michigan_swl.xlsx"


def test_run_writes_regression_residuals_loo_and_plot(inputs, tmp_path):
    csv, swl = inputs
    out = tmp_path / "out"
    paths = quality.run(csv, swl, out, save_point_id=SAVE_POINT, ari=10.0)
    assert [p.name for p in paths] == list(quality.OUTPUT_NAMES)
    assert all(p.exists() for p in paths)

    predictions = pd.read_csv(out / "B1_regression_predictions.csv")
    assert set(predictions["status"]) == {"interpolated", "extrapolated"}
    assert len(predictions) == 12 * 5  # 12 estimated scenarios x 5 ARI columns (+ ARI 10 present)
    residuals = pd.read_csv(out / "B1_known_residuals.csv")
    assert len(residuals) == 5 * 5
    # Fixture swl is planar in (precip, temp): row shift and interpolation are near exact.
    assert pd.read_csv(out / "LOO_interpolation.csv")["abs_error_ft"].max() < 1e-6


def test_run_is_reproducible(inputs, tmp_path):
    csv, swl = inputs
    for name in ("a", "b"):
        quality.run(csv, swl, tmp_path / name, save_point_id=SAVE_POINT, ari=10.0)
    for name in quality.OUTPUT_NAMES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
