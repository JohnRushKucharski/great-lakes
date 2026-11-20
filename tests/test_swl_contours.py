"""Tests for great_lakes.swl.contours: contour level and colorbar helpers."""
import pytest
from matplotlib.colors import Normalize

from great_lakes.swl import contours


def test_one_sided_color_style_threshold_inside_range_returns_none():
    assert contours.one_sided_color_style((10.0, 20.0), 15.0) is None


def test_one_sided_color_style_threshold_equal_to_range_edge_is_one_sided():
    assert contours.one_sided_color_style((10.0, 20.0), 10.0) is not None


def test_one_sided_color_style_all_below_threshold_uses_reds_r():
    style = contours.one_sided_color_style((5.0, 9.0), 10.0)
    color_map, norm, levels, widths = style
    assert color_map == "Reds_r"
    assert isinstance(norm, Normalize)
    assert norm.vmin == pytest.approx(5.0)
    assert norm.vmax == pytest.approx(10.0)
    assert levels[0] == pytest.approx(5.0)
    assert levels[-1] == pytest.approx(10.0)
    assert len(levels) == 7  # extreme + 5 mids + threshold
    assert widths[levels.index(10.0)] == 2.0


def test_one_sided_color_style_all_above_threshold_uses_blues():
    style = contours.one_sided_color_style((11.0, 15.0), 10.0)
    color_map, norm, levels, widths = style
    assert color_map == "Blues"
    assert norm.vmin == pytest.approx(10.0)
    assert norm.vmax == pytest.approx(15.0)
    assert levels[0] == pytest.approx(10.0)
    assert levels[-1] == pytest.approx(15.0)


def test_rounded_levels_rounds_default_contour_levels_to_two_decimals():
    levels, widths = contours.rounded_levels((0.0, 6.0), 3.0)
    assert levels == tuple(round(lvl, 2) for lvl in levels)
    assert len(levels) == 11
    assert 3.0 in levels
    assert widths[levels.index(3.0)] == 2.0


def test_rounded_levels_custom_decimals():
    levels, _ = contours.rounded_levels((0.0, 1.0 / 3), 0.5, decimals=1)
    assert all(round(lvl, 1) == lvl for lvl in levels)


def test_symmetric_delta_levels_small_range_uses_tenth_ft_steps():
    levels, widths = contours.symmetric_delta_levels((-0.3, 0.4))
    assert levels == pytest.approx([-0.5, -0.4, -0.3, -0.2, -0.1, 0.0,
                                     0.1, 0.2, 0.3, 0.4, 0.5])
    assert widths[levels.index(0.0)] == 2.0


def test_symmetric_delta_levels_medium_range_uses_quarter_ft_steps():
    levels, widths = contours.symmetric_delta_levels((-0.9, 1.1))
    assert levels == pytest.approx([-1.25, -1.0, -0.75, -0.5, -0.25, 0.0,
                                     0.25, 0.5, 0.75, 1.0, 1.25])
    assert widths[levels.index(0.0)] == 2.0


def test_symmetric_delta_levels_large_range_escalates_level_count_keeping_quarter_step():
    levels, widths = contours.symmetric_delta_levels((-1.8, 1.3))
    assert levels[0] == pytest.approx(-2.0)
    assert levels[-1] == pytest.approx(2.0)
    step = round(levels[1] - levels[0], 10)
    assert step == pytest.approx(0.25)
    assert 0.0 in levels
    assert widths[levels.index(0.0)] == 2.0
    assert len(levels) > 11


def test_symmetric_delta_levels_always_centered_on_zero():
    levels, _ = contours.symmetric_delta_levels((-0.05, 0.45))
    assert 0.0 in levels
    mid = len(levels) // 2
    assert levels[mid] == pytest.approx(0.0)


def test_colorbar_ticks_within_range_filters_out_of_range_levels():
    levels = (-7.0, -6.91, -3.0, 0.0, 2.24, 7.0)
    result = contours.colorbar_ticks_within_range(levels, (-6.91, 2.24))
    assert result == (-6.91, -3.0, 0.0, 2.24)


def test_colorbar_ticks_within_range_keeps_all_when_already_in_range():
    levels = (-1.0, 0.0, 1.0)
    result = contours.colorbar_ticks_within_range(levels, (-2.0, 2.0))
    assert result == levels
