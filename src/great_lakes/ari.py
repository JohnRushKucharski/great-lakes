"""Shared constants for the great_lakes.analysis response-surface plotting scripts
(plot_known_scenarios.py, plot_filled_and_extrapolated.py, plot_levels.py) -- the ARI
(Average Return Interval) values present in every swl workbook, and a filename/title
formatting helper for them.
"""

# All 13 ARI columns present in the SWL xlsx workbooks (data/clean, data/filled,
# data/extrapolated) -- see the "ID"/lat/lon + these columns in any sheet.
SWL_ARIS: tuple[float, ...] = (0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0,
                                100.0, 200.0, 500.0, 1000.0)


def format_ari(ari: float) -> str:
    """Format an ARI value for use in a filename/title, e.g. 0.1 -> "0.1",
    1.0 -> "1", 1000.0 -> "1000" (no superfluous ".0" on whole numbers).
    """
    return f"{ari:g}"
