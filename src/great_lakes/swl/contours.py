"""Contour level and colorbar helpers for response-surface plots."""

from math import ceil

from climate_canvas.data_utilities import contour_levels  # type: ignore[import-untyped]
from matplotlib.colors import Normalize


def one_sided_color_style(
    z_range: tuple[float, float], threshold: float
) -> tuple[str, Normalize, tuple[float, ...], tuple[float, ...]] | None:
    """One-sided color scale for grids lying entirely on one side of `threshold`.

    climate_canvas's default RdBu/TwoSlopeNorm needs vmin < threshold < vmax; otherwise it
    silently recenters on the data midpoint. Returns None when `threshold` is strictly
    inside `z_range` (keep the default). Otherwise returns (color_map, norm, levels,
    widths): 'Reds_r' if every cell <= threshold, 'Blues' if every cell >= threshold,
    white at `threshold` and darkest at the extreme. levels are `threshold`, the
    extreme, and 5 evenly spaced points between (bold at `threshold`).
    """
    z_min, z_max = z_range
    if z_min < threshold < z_max:
        return None
    if z_max <= threshold:
        extreme, color_map = z_min, "Reds_r"
    elif z_min >= threshold:
        extreme, color_map = z_max, "Blues"
    else:
        return None
    mids = [threshold + i * (extreme - threshold) / 6 for i in range(1, 6)]
    ascending = sorted([extreme, threshold] + mids)
    widths = tuple(2.0 if lvl == threshold else 1.0 for lvl in ascending)
    return (
        color_map,
        Normalize(vmin=min(threshold, extreme), vmax=max(threshold, extreme)),
        tuple(ascending),
        widths,
    )


def rounded_levels(
    z_range: tuple[float, float], threshold: float, decimals: int = 2
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """climate_canvas's default contour levels/widths, rounded to `decimals` places."""
    levels, widths = contour_levels(z_range, threshold)
    return tuple(round(level, decimals) for level in levels), widths


def symmetric_delta_levels(
    z_range: tuple[float, float], small_step: float = 0.1, big_step: float = 0.25,
    half_count: int = 5,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Contour levels/widths for an elevation-delta plot: a symmetric ladder centered on 0.

    Uses `small_step` if the data fits within `half_count` steps of it, else `big_step`;
    if even that is too narrow, the level count grows (spacing stays `big_step`).
    """
    max_abs = max(abs(z_range[0]), abs(z_range[1]))
    if max_abs <= half_count * small_step:
        step, n = small_step, half_count
    else:
        step, n = big_step, max(half_count, ceil(max_abs / big_step))
    levels = tuple(round(i * step, 10) for i in range(-n, n + 1))
    widths = tuple(2.0 if level == 0.0 else 1.0 for level in levels)
    return levels, widths


def colorbar_ticks_within_range(
    levels: tuple[float, ...], z_range: tuple[float, float]
) -> tuple[float, ...]:
    """Keep only `levels` within `z_range`, for plot_response_surface(color_map_ticks=...).

    An out-of-range tick blanks matplotlib's colorbar entirely (the "blank elevation-delta
    colorbar" defect). Contour levels need no such filtering.
    """
    z_min, z_max = z_range
    return tuple(lvl for lvl in levels if z_min <= lvl <= z_max)
