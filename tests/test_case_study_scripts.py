"""Smoke tests: the Long Tail Point case-study scripts run end to end on a fixture tree."""
import subprocess
import sys
import zipfile

import pandas as pd
import pytest
from ltp_fixtures import SAVE_POINT, monthly_avg, write_swl_workbook
from PIL import Image
from test_data_product_scripts import _run

from great_lakes.memo.to_docx import build_memo
from great_lakes.paths import REPO_ROOT, Layout

SCRIPTS = REPO_ROOT / "case-studies" / "long-tail-point" / "overtopping" / "scripts"
AVG_SCRIPT = REPO_ROOT / "analyses" / "avg-statistics" / "scripts" / "scenario_statistics.py"
SWL_METHODS_SCRIPT = REPO_ROOT / "data-products" / "swl" / "scripts" / "assess_method_quality.py"

OUT = "case-studies/long-tail-point/overtopping/outputs"
AVG_ROW = {"resource_name": "r", "component_name": "high", "lake": "michiganhuron",
           "magnitude_operator": ">", "magnitude_value": 180.1}
SWL_ROW = {"resource_name": "r", "lake": "michigan", "save_point_id": SAVE_POINT,
           "magnitude_operator": ">=", "magnitude_value": 180.5}


def _workbook(path, row, out_dir):
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([row]).to_excel(writer, sheet_name="resources", index=False)
        pd.DataFrame({"option": ["output_directory"], "value": [out_dir]}
                     ).to_excel(writer, sheet_name="config", index=False)


def _make_root(path):
    """Fixture repo: avg csv, complete swl workbook, the two case-study worksheets."""
    layout = Layout(path)
    layout.avg.mkdir(parents=True)
    monthly_avg().to_csv(layout.avg / "michiganhuron_avg.csv", index=False)
    layout.swl_complete.mkdir(parents=True)
    write_swl_workbook(layout.swl_complete / "michigan_swl.xlsx")
    inputs = layout.overtopping / "inputs"
    inputs.mkdir(parents=True)
    _workbook(inputs / "batch_avg.xlsx", AVG_ROW, f"{OUT}/batch_avg_output")
    _workbook(inputs / "batch_swl-longtail.xlsx", SWL_ROW, f"{OUT}/batch_swl_output")
    return path


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    return _make_root(tmp_path_factory.mktemp("case_study"))


def _outputs(root):
    return Layout(root).overtopping / "outputs"


def test_avg_scenario_statistics_script(tmp_path):
    layout = Layout(tmp_path)
    layout.avg.mkdir(parents=True)
    monthly_avg().to_csv(layout.avg / "michiganhuron_avg.csv", index=False)
    _run(AVG_SCRIPT, tmp_path)
    out = layout.avg_statistics_outputs / "scenario_statistics"
    assert (out / "README.txt").exists()
    assert list(out.glob("*.csv"))


def test_swl_method_quality_script(tmp_path):
    layout = Layout(tmp_path)
    layout.avg.mkdir(parents=True)
    monthly_avg().to_csv(layout.avg / "michiganhuron_avg.csv", index=False)
    layout.swl_complete.mkdir(parents=True)
    write_swl_workbook(layout.swl_complete / "michigan_swl.xlsx")
    _run(SWL_METHODS_SCRIPT, tmp_path, "--save-point-id", str(SAVE_POINT))
    out = layout.swl_methods_outputs / "method_quality"
    assert (out / "README.txt").exists()
    assert list(out.glob("*.csv"))


def test_make_figures_writes_the_memo_figures_and_a_run_record(root):
    _run(SCRIPTS / "make_figures.py", root, "--save-point-id", str(SAVE_POINT))
    figures = _outputs(root) / "figures"
    assert (figures / "README.txt").exists()
    assert list(figures.glob("*.png"))
    assert list(figures.glob(f"*{SAVE_POINT}_ari15*"))


def test_run_assessments_runs_both_worksheets(root):
    _run(SCRIPTS / "run_assessments.py", root)
    assert (_outputs(root) / "batch_avg_output" / "README.txt").exists()
    assert (_outputs(root) / "batch_swl_output" / "README.txt").exists()


def test_run_assessments_exits_1_when_a_worksheet_row_fails(tmp_path):
    bad = _make_root(tmp_path / "bad")
    inputs = Layout(bad).overtopping / "inputs"
    _workbook(inputs / "batch_swl-longtail.xlsx", {**SWL_ROW, "lake": "nowhere"}, f"{OUT}/x")
    _run(SCRIPTS / "run_assessments.py", bad, expect=1)
    # The other worksheet still ran.
    assert (_outputs(bad) / "batch_avg_output" / "README.txt").exists()


def test_dashboard_is_built_then_packaged(tmp_path):
    root = _make_root(tmp_path / "dash")
    _run(SCRIPTS / "run_assessments.py", root)
    _run(SCRIPTS / "build_dashboard.py", root)
    outputs = _outputs(root)
    assert (outputs / "dashboard.html").exists()
    assert (outputs / "manifest.js").exists()
    manifest = (outputs / "manifest.js").read_text(encoding="utf-8")
    assert '"analysis_type": "swl"' in manifest
    assert '"analysis_type": "avg"' not in manifest
    _run(SCRIPTS / "build_dashboard.py", root, "--include-avg")
    assert '"analysis_type": "avg"' in (outputs / "manifest.js").read_text(encoding="utf-8")
    _run(SCRIPTS / "build_dashboard.py", root)
    _run(SCRIPTS / "package_dashboard.py", root)
    with zipfile.ZipFile(outputs / "long-tail-point-dashboard.zip") as z:
        names = z.namelist()
    assert {"dashboard.html", "manifest.js", "START_HERE.txt"} <= set(names)
    assert not any(name.endswith(".xlsx") for name in names)


def _draft(root):
    layout = Layout(root)
    (_outputs(root) / "figures").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (60, 40), "white").save(_outputs(root) / "figures" / "F2.png")
    draft = layout.overtopping / "inputs" / "memo_draft.md"
    draft.write_text(
        "**TO:** Team\n\n## 1. Intro\n\nText.\n\n![Figure 2](../outputs/figures/F2.png)\n",
        encoding="utf-8")
    return draft


def test_build_memo_docx_writes_to_outputs_never_deliverables(root):
    _draft(root)
    _run(SCRIPTS / "build_memo_docx.py", root)
    assert list(_outputs(root).glob("*.docx"))
    assert not (Layout(root).overtopping / "deliverables").exists()


def test_sync_draft_from_docx_reports_and_promotes_only_when_asked(root):
    draft = _draft(root)
    original = draft.read_text(encoding="utf-8")
    deliverables = Layout(root).overtopping / "deliverables"
    deliverables.mkdir(exist_ok=True)
    docx = build_memo(draft, deliverables / "memo.docx")
    edited = docx  # no hand edits: recovered text should match the draft structure
    result = _run(SCRIPTS / "sync_draft_from_docx.py", root, "--docx", str(edited))
    assert "structure" in result.stdout.lower()
    recovered = _outputs(root) / "memo_draft_from_docx.md"
    assert recovered.exists()
    assert draft.read_text(encoding="utf-8") == original

    _run(SCRIPTS / "sync_draft_from_docx.py", root, "--docx", str(edited), "--promote")
    assert (_outputs(root) / "memo_draft_before_sync.md").read_text(encoding="utf-8") == original
    assert "Intro" in draft.read_text(encoding="utf-8")


def test_scripts_do_not_require_arguments():
    for name in ("make_figures", "run_assessments", "build_dashboard", "package_dashboard",
                 "build_memo_docx", "sync_draft_from_docx"):
        done = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), "--help"],
                              capture_output=True, text=True, check=False)
        assert done.returncode == 0, name
