"""Smoke tests: the Long Tail Point habitat scripts run end to end on a fixture tree."""
import importlib.util
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from ltp_fixtures import monthly_avg
from PIL import Image
from test_data_product_scripts import _run

from great_lakes import habitat
from great_lakes.memo.to_docx import build_memo
from great_lakes.paths import REPO_ROOT, Layout

SCRIPTS = REPO_ROOT / "case-studies" / "long-tail-point" / "habitat" / "scripts"
FIGURE_SCRIPTS = {
    "figure_lake_movement": ["F1"],
    "figure_elevation_ladder": ["F3"],
    "figure_marsh_zones": ["F4", "F4B", "F4C"],
    "figure_wd_scorecard": ["F5"],
    "figure_reliability": ["F6"],
    "figure_hydrograph": ["F7"],
    "figure_cycle_surfaces": ["F8"],
    "figure_robustness": ["F9"],
}
MUSKY = ("juvenile_habitat", "spawning_zones", "recruitment_zones")
POND = ("growing_season_habitat", "winter_survival")


def _reliability(components, floors, scenarios) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = [
        {"Component": c, "Scenario": s, "Percentage": rng.uniform(0, 100), "Floor (ft IGLD85)": f}
        for c in components for s in scenarios for f in floors
    ]
    return pd.DataFrame(rows)


def _make_root(path):
    """Fixture repo: avg csv, survey points, Jenny's maps, reliability tables, a memo draft."""
    layout = Layout(path)
    layout.avg.mkdir(parents=True)
    avg = monthly_avg(years=40)
    avg.to_csv(habitat.levels_csv(layout), index=False)
    inputs = layout.habitat / "inputs"
    inputs.mkdir(parents=True)
    bottoms = np.linspace(571.0, 580.0, 40)
    with pd.ExcelWriter(habitat.survey_xlsx(layout)) as writer:
        pd.DataFrame({"Estimated Bottom elevation (ft)": bottoms}).to_excel(
            writer, sheet_name="depth_analysis", index=False)
    maps = habitat.jenny_maps_dir(layout)
    maps.mkdir()
    for name in ("F4B", "F4C"):
        Image.new("RGB", (30, 20), "white").save(maps / f"{name}.png")
    scenarios = list(avg.columns[1:])
    out = habitat.reliability_dir(layout)
    out.mkdir(parents=True)
    _reliability(MUSKY, range(573, 580), scenarios).to_csv(
        out / "musky_reliability.csv", index=False)
    _reliability(POND, range(571, 578), scenarios).to_csv(
        out / "pondweed_reliability.csv", index=False)
    (inputs / "memo_draft.md").write_text(
        "**TO:** Team\n\n## 1. Intro\n\nText.\n\n{{F1}}\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    return _make_root(tmp_path_factory.mktemp("habitat"))


@pytest.mark.parametrize("script", FIGURE_SCRIPTS)
def test_figure_scripts_write_their_figures_and_a_run_record(root, script):
    _run(SCRIPTS / f"{script}.py", root)
    figures = habitat.figures_dir(Layout(root))
    for fig_id in FIGURE_SCRIPTS[script]:
        assert (figures / f"{fig_id}.png").exists()
    record = (figures / "README.txt").read_text(encoding="utf-8")
    assert all(f"{fig_id}.png" in record for fig_id in FIGURE_SCRIPTS[script])


def test_build_memo_draft_writes_to_outputs_never_deliverables(root):
    _run(SCRIPTS / "figure_lake_movement.py", root)
    _run(SCRIPTS / "build_memo_draft.py", root)
    assert list((Layout(root).habitat / "outputs").glob("*.docx"))
    assert not (Layout(root).habitat / "deliverables").exists()


def test_sync_draft_from_docx_reports_and_promotes_only_when_asked(tmp_path):
    root = _make_root(tmp_path / "sync")
    layout = Layout(root)
    draft = layout.habitat / "inputs" / "memo_draft.md"
    original = draft.read_text(encoding="utf-8")
    plain = tmp_path / "plain.md"
    plain.write_text("**TO:** Team\n\n## 1. Intro\n\nText.\n", encoding="utf-8")
    deliverables = layout.habitat / "deliverables"
    deliverables.mkdir()
    docx = build_memo(plain, deliverables / "memo.docx")
    script = SCRIPTS / "sync_draft_from_docx.py"

    result = _run(script, root, "--docx", str(docx))
    assert "structure" in result.stdout.lower()
    assert (layout.habitat / "outputs" / "memo_draft_from_docx.md").exists()
    assert draft.read_text(encoding="utf-8") == original

    _run(script, root, "--docx", str(docx), "--promote")
    backup = layout.habitat / "outputs" / "memo_draft_before_sync.md"
    assert backup.read_text(encoding="utf-8") == original
    assert "Intro" in draft.read_text(encoding="utf-8")


def test_reliability_runs_write_their_tables(tmp_path):
    pytest.importorskip("hydropattern.scenarios")
    root = _make_root(tmp_path / "runs")
    folder = habitat.reliability_dir(Layout(root))
    for name in folder.glob("*.csv"):
        name.unlink()
    _run(SCRIPTS / "pondweed_runs.py", root)
    _run(SCRIPTS / "musky_runs.py", root)
    assert (folder / "pondweed_reliability.csv").exists()
    assert (folder / "musky_reliability.csv").exists()
    record = (folder / "README.txt").read_text(encoding="utf-8")
    assert "musky_reliability.csv" in record and "pondweed_reliability.csv" in record


def test_scripts_do_not_require_arguments():
    names = [*FIGURE_SCRIPTS, "build_memo_draft", "sync_draft_from_docx"]
    if importlib.util.find_spec("hydropattern.scenarios"):
        names += ["musky_runs", "pondweed_runs"]
    for name in names:
        done = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), "--help"],
                              capture_output=True, text=True, check=False)
        assert done.returncode == 0, name
