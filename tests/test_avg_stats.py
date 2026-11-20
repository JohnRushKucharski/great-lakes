"""Tests for generic avg (monthly lake level) statistics."""

import pandas as pd
import pytest

from great_lakes import avg_stats


def test_annual_maxima_groups_monthly_levels_by_calendar_year():
    monthly = pd.DataFrame(
        {
            "time": ["1970-01-01", "1970-02-01", "1971-01-01", "2999-12-01"],
            "_0_0": [1.0, 3.0, 2.0, 6.0],
            "_5_1.5": [4.0, 2.0, 5.0, 7.0],
        }
    )

    annual = avg_stats.annual_maxima(monthly)

    assert annual.index.tolist() == [1970, 1971, 2999]
    assert annual["_0_0"].tolist() == [3.0, 2.0, 6.0]
    assert annual["_5_1.5"].tolist() == [4.0, 5.0, 7.0]


def test_high_year_flags_marks_exactly_top_fraction():
    values = pd.Series(range(1, 16))

    flags = avg_stats.high_year_flags(values, fraction=1 / 5)

    assert flags.sum() == 3
    assert values[flags].tolist() == [13, 14, 15]


def test_high_year_flags_rejects_bad_fraction():
    with pytest.raises(ValueError):
        avg_stats.high_year_flags(pd.Series([1, 2]), fraction=0.0)


def test_rolling_window_category_shares_include_overlapping_windows():
    flags = pd.Series([True, False, True, False, False])

    shares = avg_stats.rolling_window_category_shares(flags, window_years=3)

    assert shares["0"] == 0.0
    assert shares["1"] == pytest.approx(2 / 3)
    assert shares["2"] == pytest.approx(1 / 3)
    assert shares["3+"] == 0.0


def test_poisson_window_shares_for_lambda_one_match_approved_examples():
    shares = avg_stats.poisson_window_category_shares(rate=1.0)

    assert shares["0"] == pytest.approx(0.3679, abs=0.0001)
    assert shares["1"] == pytest.approx(0.3679, abs=0.0001)
    assert shares["2"] == pytest.approx(0.1839, abs=0.0001)
    assert shares["3+"] == pytest.approx(0.0803, abs=0.0001)
    assert sum(shares.values()) == pytest.approx(1.0)


def test_poisson_probability_at_least_matches_approved_examples():
    assert avg_stats.poisson_probability_at_least(1) == pytest.approx(0.6321, abs=0.0001)
    assert avg_stats.poisson_probability_at_least(3) == pytest.approx(0.0803, abs=0.0001)
    assert avg_stats.poisson_probability_at_least(4) == pytest.approx(0.0190, abs=0.0001)
