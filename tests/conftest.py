"""Shared pytest configuration for the great_lakes test suite.

Force matplotlib's non-interactive Agg backend before any test imports pyplot --
required in headless/CI environments (and this Windows session, whose Tcl/Tk
install is broken) since climate_canvas.plots_utilities.plot_response_surface
renders and saves a real figure.
"""
import matplotlib

matplotlib.use("Agg")
