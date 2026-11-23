"""Smoke tests: each analyses/ script runs end to end on a fixture tree (--root)."""
import subprocess
import sys

import pandas as pd
import pytest
from test_avg_ari import _write_tiny_avg_csv
from test_data_product_scripts import PRODUCTS, _run, _write_raw_avg, _write_raw_swl

from great_lakes.cleaning import avg as clean_avg
from great_lakes.cleaning import swl as clean_swl
from great_lakes.paths import REPO_ROOT, Layout

ANALYSES = REPO_ROOT / "analyses"


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    """Fixture repo with avg and complete swl data products and both shipped templates."""
    root = tmp_path_factory.mktemp("analyses")
    layout = Layout(root)
    layout.raw.mkdir(parents=True)
    _write_raw_avg(layout.raw / clean_avg.SOURCE_FILE)
    _write_raw_swl(layout.raw / clean_swl.SOURCE_FILE)
    _run(PRODUCTS / "avg" / "scripts" / "clean.py", root)
    _run(PRODUCTS / "swl" / "scripts" / "clean.py", root)
    _run(PRODUCTS / "swl" / "scripts" / "complete.py", root)
    return root


def test_avg_statistics_plot_ari_surfaces(tmp_path):
    layout = Layout(tmp_path)
    layout.avg.mkdir(parents=True)
    _write_tiny_avg_csv(layout.avg / "superior_avg.csv")
    script = ANALYSES / "avg-statistics" / "scripts" / "plot_ari_surfaces.py"
    _run(script, tmp_path, "--lake", "superior", "--ari", "2")
    outputs = layout.avg_statistics_outputs
    assert (outputs / "README.txt").exists()
    assert any((outputs / "ari" / "clustered" / "high").glob("superior_*.png"))


# A row each avg and swl assess runs successfully on the fixture data (levels near 180).
ROWS = {
    "avg": {"resource_name": "r", "component_name": "high", "lake": "superior",
            "magnitude_operator": ">", "magnitude_value": 180.1},
    "swl": {"resource_name": "r", "lake": "superior", "save_point_id": 1,
            "magnitude_operator": ">=", "magnitude_value": 180.5},
}


def _workbook(path, kind, out_dir, row=None):
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([row or ROWS[kind]]).to_excel(writer, sheet_name="resources", index=False)
        pd.DataFrame({"option": ["output_directory"], "value": [str(out_dir)]}
                     ).to_excel(writer, sheet_name="config", index=False)
    return path


@pytest.mark.parametrize("kind", ["avg", "swl"])
def test_assess_resources_runs_a_workbook(root, tmp_path, kind):
    out = tmp_path / "out"
    script = ANALYSES / f"assess-{kind}-resources" / "scripts" / "assess.py"
    _run(script, root, "--resources", str(_workbook(tmp_path / "w.xlsx", kind, out)))
    assert (out / "README.txt").exists()
    assert list(out.rglob("*.csv"))


def test_assess_resources_output_dir_overrides_the_workbook(root, tmp_path):
    override = tmp_path / "override"
    workbook = _workbook(tmp_path / "w.xlsx", "swl", tmp_path / "ignored")
    script = ANALYSES / "assess-swl-resources" / "scripts" / "assess.py"
    _run(script, root, "--resources", str(workbook), "--output-dir", str(override))
    assert list(override.rglob("*.csv"))
    assert not (tmp_path / "ignored").exists()


@pytest.mark.parametrize("kind", ["avg", "swl"])
def test_assess_resources_builds_template_and_runs_it_by_default(root, kind):
    layout = Layout(root)
    scripts = ANALYSES / f"assess-{kind}-resources" / "scripts"
    _run(scripts / "build_template.py", root)
    assert layout.assess_template(kind).exists()

    # The template's example rows need real data, so only the run record is checked.
    subprocess.run([sys.executable, str(scripts / "assess.py"), "--root", str(root)],
                   capture_output=True, text=True, check=False)
    assert (layout.assess_outputs(kind) / "README.txt").exists()


def test_assess_resources_exits_1_when_a_row_fails(root, tmp_path):
    bad = {**ROWS["swl"], "lake": "nowhere"}
    workbook = _workbook(tmp_path / "w.xlsx", "swl", tmp_path / "out", row=bad)
    script = ANALYSES / "assess-swl-resources" / "scripts" / "assess.py"
    _run(script, root, "--resources", str(workbook), expect=1)
