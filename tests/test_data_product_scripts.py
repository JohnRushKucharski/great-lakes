"""Smoke tests: each data-product script runs end to end on a small fixture tree (--root)."""
import datetime
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from great_lakes import lakes
from great_lakes.cleaning import avg as clean_avg
from great_lakes.cleaning import swl as clean_swl
from great_lakes.paths import REPO_ROOT, Layout
from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES

PRODUCTS = REPO_ROOT / "data-products"
TAG_TO_LAKE = {"sup": "superior", "mich": "michigan", "hur": "huron", "ont": "ontario"}
KNOWN_DELTAS = {"baseline": (0, 0), "modnear": (5, 1.5), "modfuture_low": (10, 5),
                "lowLL": (0, 7), "highLL": (20, 5)}


def _level(precip: float, temp: float) -> float:
    """Planar in (precip, temp), so interpolation and extrapolation reproduce it exactly."""
    return 180.0 + 0.01 * precip + 0.02 * temp


def _write_raw_avg(path: Path) -> None:
    index = [datetime.datetime(1970, 1, 1), datetime.datetime(1970, 2, 1)]
    frame = pd.DataFrame({"month": [1, 2]}, index=index)
    for suffix in ALL_SCENARIO_SUFFIXES:
        _, precip, temp = suffix.split("_")
        frame[suffix] = [_level(float(precip), float(temp))] * 2
    with pd.ExcelWriter(path) as writer:
        for sheet in clean_avg.LAKES:
            frame.to_excel(writer, sheet_name=sheet)


def _write_raw_swl(path: Path) -> None:
    n_aris = len(clean_swl.NEW_HEADER) - 3
    with pd.ExcelWriter(path) as writer:
        for tag, lake in TAG_TO_LAKE.items():
            lat, lon = lakes.LAKE_CENTROIDS.get(lake, (45.0, -85.0))
            for scenario, (precip, temp) in KNOWN_DELTAS.items():
                levels = [_level(precip, temp) + 0.1 * i for i in range(n_aris)]
                rows = [["hdr"] * 16, ["hdr"] * 16,
                        [1, lat, lon, *levels], [2, lat + 0.5, lon, *levels]]
                pd.DataFrame(rows).to_excel(
                    writer, sheet_name=clean_swl.source_sheet_name(scenario, tag),
                    index=False, header=False)


def _run(script: Path, root: Path, *args: str, expect: int = 0):
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(root), *args],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == expect, result.stdout + result.stderr
    return result


@pytest.fixture
def root(tmp_path):
    layout = Layout(tmp_path)
    layout.raw.mkdir(parents=True)
    _write_raw_avg(layout.raw / clean_avg.SOURCE_FILE)
    _write_raw_swl(layout.raw / clean_swl.SOURCE_FILE)
    return tmp_path


def test_avg_scripts_clean_then_plot_figures(root):
    layout = Layout(root)
    _run(PRODUCTS / "avg" / "scripts" / "clean.py", root)
    assert len(list(layout.avg.glob("*_avg.csv"))) == 5

    _run(PRODUCTS / "avg" / "scripts" / "plot_figures.py", root)
    assert (layout.avg_bulk_figures / "README.txt").exists()
    names = sorted(p.name for p in layout.avg_figures.glob("*.png"))
    assert names == ["erie.png", "michiganhuron.png", "ontario.png", "stclair.png",
                     "superior.png"]


def test_clean_script_refuses_to_overwrite_without_flag(root):
    script = PRODUCTS / "avg" / "scripts" / "clean.py"
    _run(script, root)
    again = _run(script, root, expect=1)
    assert "--overwrite" in again.stdout + again.stderr
    _run(script, root, "--overwrite")


def test_swl_scripts_clean_complete_figures_gates_and_methods(root):
    layout = Layout(root)
    scripts = PRODUCTS / "swl" / "scripts"
    _run(PRODUCTS / "avg" / "scripts" / "clean.py", root)
    _run(scripts / "clean.py", root)
    _run(scripts / "complete.py", root)
    for filename in lakes.LAKE_SWL_FILENAMES.values():
        assert (layout.swl_complete / filename).exists()
    assert (layout.swl_filled / "README.txt").exists()

    _run(scripts / "plot_figures.py", root, "--summary-only")
    assert (layout.swl_bulk_figures / "README.txt").exists()
    assert any(layout.swl_complete_figures.glob("*.png"))
    _run(scripts / "compare_fill_to_climate_canvas.py", root)
    assert (layout.swl_fill_gate_outputs / "README.txt").exists()
    _run(scripts / "check_ari_curves.py", root)
    assert (layout.swl_ari_gate_outputs / "README.txt").exists()
    _run(PRODUCTS / "swl" / "methods" / "summarize_precip_temp_effects.py", root)
    assert (layout.swl_methods_outputs / "README.txt").exists()
