"""Tests for packaging the results dashboard as a self-contained zip."""
import json
import zipfile

import pytest

from great_lakes import dashboard_package as pkg


def _dashboard(tmp_path, linked=("batch_swl_output/a_plot.png", "batch_swl_output/a_grid.csv")):
    folder = tmp_path / "outputs"
    (folder / "batch_swl_output").mkdir(parents=True)
    for rel in linked:
        (folder / rel).write_text("x")
    (folder / "dashboard.html").write_text("<html></html>")
    manifest = {"entries": [{"files": {
        "plot": {"type": "image", "path": linked[0]},
        "grid": {"type": "grid", "data": {}, "path": linked[1]},
        "equivalent_elevation_plot": None,
        "elevation_delta_plot": {"type": "missing", "message": "File not found: x"},
    }}]}
    (folder / "manifest.js").write_text(f"window.MANIFEST = {json.dumps(manifest)};\n")
    (folder / "batch_swl-longtail.xlsx").write_text("input workbook")
    return folder


def test_linked_files_lists_every_path_in_the_manifest(tmp_path):
    folder = _dashboard(tmp_path)
    assert sorted(pkg.linked_files(folder / "manifest.js")) == [
        "batch_swl_output/a_grid.csv", "batch_swl_output/a_plot.png"]


def test_package_contains_dashboard_manifest_linked_files_and_start_here(tmp_path):
    folder = _dashboard(tmp_path)
    zip_path = pkg.package_dashboard(folder, tmp_path / "out" / "dash.zip")
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        assert names == {"dashboard.html", "manifest.js", "START_HERE.txt",
                         "batch_swl_output/a_plot.png", "batch_swl_output/a_grid.csv"}
        assert "dashboard.html" in z.read("START_HERE.txt").decode()


def test_package_never_includes_input_workbooks(tmp_path):
    folder = _dashboard(tmp_path, linked=("batch_swl_output/a_plot.png", "in.xlsx"))
    with pytest.raises(ValueError, match="workbook"):
        pkg.package_dashboard(folder, tmp_path / "dash.zip")


def test_package_fails_listing_missing_linked_files(tmp_path):
    folder = _dashboard(tmp_path)
    (folder / "batch_swl_output" / "a_plot.png").unlink()
    with pytest.raises(FileNotFoundError, match="a_plot.png"):
        pkg.package_dashboard(folder, tmp_path / "dash.zip")
    assert not (tmp_path / "dash.zip").exists()
