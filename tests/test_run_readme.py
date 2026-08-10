"""Tests for great_lakes.run_readme's generic reproducibility-record writer.

This is the generic core extracted out of batch_runner.write_run_readme (which now
wraps it -- see test_batch_runner.py's write_run_readme tests, unmodified, for that
backward-compat contract). The analysis scripts (great_lakes.analysis.*) call this
generic writer directly, since they have no resources workbook or per-row
succeeded/failed summary -- just a flat list of input files and written outputs.
"""
from datetime import datetime, timezone
from pathlib import Path

from great_lakes import run_readme

_FIXED_NOW = datetime(2026, 8, 10, 12, 30, 0, tzinfo=timezone.utc)


def test_write_readme_documents_title_timestamp_and_inputs(tmp_path):
    input_path = tmp_path / "clean" / "superior_avg.csv"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("data")
    output_directory = tmp_path / "out"

    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[("data file", input_path)],
        results_text="Wrote 2 files.",
        naming_scheme_text="n/a",
        written_paths=[],
        workspace_root=tmp_path,
        now=_FIXED_NOW,
    )

    assert readme_path == output_directory / "README.txt"
    text = readme_path.read_text()
    assert "Analysis run report" in text
    assert "2026-08-10T12:30:00" in text
    assert str(Path("clean") / "superior_avg.csv") in text
    assert "data file" in text
    assert "Wrote 2 files." in text
    assert "n/a" in text


def test_write_readme_lists_files_written_this_run(tmp_path):
    output_directory = tmp_path / "out"
    output_directory.mkdir()
    written_path = output_directory / "superior_mean.png"
    written_path.write_text("png")

    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[],
        results_text="Wrote 1 file.",
        naming_scheme_text="n/a",
        written_paths=[written_path],
        workspace_root=tmp_path,
        now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert str(Path("out") / "superior_mean.png") in text


def test_write_readme_flags_stale_unrecognized_files(tmp_path):
    output_directory = tmp_path / "out"
    output_directory.mkdir()
    written_path = output_directory / "superior_mean.png"
    written_path.write_text("png")
    stale_path = output_directory / "leftover_from_old_run.png"
    stale_path.write_text("legacy")

    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[],
        results_text="Wrote 1 file.",
        naming_scheme_text="n/a",
        written_paths=[written_path],
        workspace_root=tmp_path,
        now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "leftover_from_old_run.png" in text
    assert "not created by this run" in text
    stale_section = text.split("not created by this run", 1)[1]
    assert "superior_mean.png" not in stale_section


def test_write_readme_no_stale_files_message_when_clean(tmp_path):
    output_directory = tmp_path / "out"
    output_directory.mkdir()
    written_path = output_directory / "superior_mean.png"
    written_path.write_text("png")

    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[],
        results_text="Wrote 1 file.",
        naming_scheme_text="n/a",
        written_paths=[written_path],
        workspace_root=tmp_path,
        now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "(none found)" in text


def test_write_readme_no_files_written_message_when_empty(tmp_path):
    output_directory = tmp_path / "out"

    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[],
        results_text="Wrote 0 files.",
        naming_scheme_text="n/a",
        written_paths=[],
        workspace_root=tmp_path,
        now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "(none)" in text


def test_write_readme_stale_scan_is_recursive(tmp_path):
    output_directory = tmp_path / "out"
    nested = output_directory / "ari" / "clustered" / "high"
    nested.mkdir(parents=True)
    stale_nested = nested / "leftover.png"
    stale_nested.write_text("legacy")

    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[],
        results_text="Wrote 0 files.",
        naming_scheme_text="n/a",
        written_paths=[],
        workspace_root=tmp_path,
        now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "leftover.png" in text
    assert "not created by this run" in text


def test_write_readme_defaults_now_to_utc_now(tmp_path):
    output_directory = tmp_path / "out"
    before = datetime.now(timezone.utc)
    readme_path = run_readme.write_readme(
        output_directory=output_directory,
        title="Analysis run report",
        inputs=[],
        results_text="n/a",
        naming_scheme_text="n/a",
        written_paths=[],
        workspace_root=tmp_path,
    )
    after = datetime.now(timezone.utc)
    text = readme_path.read_text()
    timestamp_line = next(line for line in text.splitlines() if line.startswith("Run timestamp"))
    ts = datetime.fromisoformat(timestamp_line.split(": ", 1)[1])
    assert before <= ts <= after
