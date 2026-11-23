"""Generic statistics on avg (monthly lake level) data: annual maxima, high-year
persistence, and Poisson reference probabilities."""

from math import ceil, exp, factorial

import numpy as np
import pandas as pd

WINDOW_CATEGORIES = ("0", "1", "2", "3+")


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
