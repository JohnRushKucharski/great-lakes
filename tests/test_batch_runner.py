"""Tests for the shared batch_runner.py infrastructure (RowProcessor Strategy loop),
extracted out of batch_run_avg.py/batch_run_swl.py's near-identical duplicated code.

These tests use a minimal fake ResourceSpec/BatchConfig/RowProcessor rather than the
real avg/swl types, so they exercise run_batch's shared shape in isolation. The
existing test_batch_run_avg.py/test_batch_run_swl.py test suites continue to exercise
the real per-script behavior end to end and must keep passing unmodified.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from great_lakes import batch_runner


@dataclass(frozen=True)
class _FakeResource:
    resource_name: str
    component_name: str


@dataclass(frozen=True)
class _FakeConfig:
    output_directory: str
    overwrite: bool = False


class _FakeProcessor:
    """Minimal RowProcessor: builds one output file per row named
    <resource_name>_<component_name>.txt under config.output_directory."""

    def __init__(self, build_side_effect=None):
        self._build_side_effect = build_side_effect or {}

    def read_rows(self, resources_path: Path) -> list[dict]:
        import json
        return json.loads(resources_path.read_text())

    def parse(self, raw_row: dict) -> _FakeResource:
        if raw_row.get("resource_name") is None:
            raise batch_runner.RowValidationError(["resource_name is required."])
        return _FakeResource(raw_row["resource_name"], raw_row.get("component_name") or "c")

    def target(
        self, resource: _FakeResource, config: _FakeConfig
    ) -> tuple[Path, str]:
        return (
            Path(config.output_directory),
            f"{resource.resource_name}_{resource.component_name}",
        )

    def duplicate_message(self, output_folder: Path, resource: _FakeResource) -> str:
        return f"Duplicate output target within this batch run: {output_folder}"

    def check_overwrite(self, resource: _FakeResource, config: _FakeConfig) -> str | None:
        target_path = (
            Path(config.output_directory)
            / f"{resource.resource_name}_{resource.component_name}.txt"
        )
        if not config.overwrite and target_path.exists():
            return f"Output already exists and overwrite=False: {target_path}"
        return None

    def build(
        self, resource: _FakeResource, data_dir: Path, config: _FakeConfig
    ) -> tuple[Path, ...]:
        key = f"{resource.resource_name}_{resource.component_name}"
        if key in self._build_side_effect:
            raise self._build_side_effect[key]
        out_path = Path(config.output_directory) / f"{key}.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("ok")
        return (out_path,)


def _write_rows(tmp_path: Path, rows: list[dict]) -> Path:
    import json
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(rows))
    return path


def test_run_batch_succeeds_for_valid_rows(tmp_path):
    rows_path = _write_rows(tmp_path, [{"resource_name": "duluth", "component_name": "high"}])
    config = _FakeConfig(output_directory=str(tmp_path / "out"))
    summary = batch_runner.run_batch(rows_path, tmp_path, config, _FakeProcessor())
    assert len(summary.succeeded) == 1
    assert summary.results[0].output_paths == (Path(config.output_directory) / "duluth_high.txt",)


def test_run_batch_invalid_row_reported_as_failed(tmp_path):
    rows_path = _write_rows(tmp_path, [{"resource_name": None}])
    config = _FakeConfig(output_directory=str(tmp_path / "out"))
    summary = batch_runner.run_batch(rows_path, tmp_path, config, _FakeProcessor())
    assert len(summary.failed) == 1
    assert "resource_name is required" in summary.failed[0].message


def test_run_batch_duplicate_target_fails_second_row(tmp_path):
    rows_path = _write_rows(tmp_path, [
        {"resource_name": "duluth", "component_name": "high"},
        {"resource_name": "duluth", "component_name": "high"},
    ])
    config = _FakeConfig(output_directory=str(tmp_path / "out"))
    summary = batch_runner.run_batch(rows_path, tmp_path, config, _FakeProcessor())
    assert summary.succeeded[0].row_index == 1
    assert summary.failed[0].row_index == 2
    assert "Duplicate output target" in summary.failed[0].message


def test_run_batch_pre_existing_output_fails_when_overwrite_false(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "duluth_high.txt").write_text("stale")
    rows_path = _write_rows(tmp_path, [{"resource_name": "duluth", "component_name": "high"}])
    config = _FakeConfig(output_directory=str(out_dir), overwrite=False)
    summary = batch_runner.run_batch(rows_path, tmp_path, config, _FakeProcessor())
    assert len(summary.failed) == 1
    assert "already exists and overwrite=False" in summary.failed[0].message


def test_run_batch_continues_after_build_exception(tmp_path):
    rows_path = _write_rows(tmp_path, [
        {"resource_name": "duluth", "component_name": "high"},
        {"resource_name": "green_bay", "component_name": "low"},
    ])
    config = _FakeConfig(output_directory=str(tmp_path / "out"))
    processor = _FakeProcessor(build_side_effect={"duluth_high": RuntimeError("boom")})
    summary = batch_runner.run_batch(rows_path, tmp_path, config, processor)
    assert summary.failed[0].message == "boom"
    assert len(summary.succeeded) == 1
    assert summary.succeeded[0].resource_name == "green_bay"


def test_run_batch_reports_progress_running_then_final_status(tmp_path):
    rows_path = _write_rows(tmp_path, [{"resource_name": "duluth", "component_name": "high"}])
    config = _FakeConfig(output_directory=str(tmp_path / "out"))
    calls = []
    batch_runner.run_batch(
        rows_path, tmp_path, config, _FakeProcessor(),
        progress=lambda row_index, total, rn, cn, status: calls.append(status),
    )
    assert calls == ["running", "succeeded"]


def test_format_summary_reports_counts_and_failures():
    summary = batch_runner.BatchSummary(results=[
        batch_runner.RowResult(1, "duluth", "high", "succeeded"),
        batch_runner.RowResult(2, "green_bay", "low", "failed", "boom"),
    ])
    text = batch_runner.format_summary(summary)
    assert "1 succeeded, 1 failed out of 2 row(s)." in text
    assert "boom" in text


@pytest.mark.parametrize("value,default,expected", [
    (None, True, True),
    ("true", False, True),
    ("FALSE", True, False),
    ("1", False, True),
    ("0", True, False),
    (True, False, True),
])
def test_to_bool(value, default, expected):
    assert batch_runner._to_bool(value, default) is expected


def test_to_bool_rejects_unparseable_string():
    with pytest.raises(ValueError):
        batch_runner._to_bool("maybe", False)


def test_is_blank():
    assert batch_runner._is_blank(None)
    assert batch_runner._is_blank("   ")
    assert batch_runner._is_blank(float("nan"))
    assert not batch_runner._is_blank("x")
    assert not batch_runner._is_blank(0)


# ---- write_run_readme ---------------------------------------------------------------

_FIXED_NOW = datetime(2026, 8, 10, 12, 30, 0, tzinfo=timezone.utc)


def test_write_run_readme_documents_inputs_and_timestamp(tmp_path):
    resources_path = tmp_path / "resources.xlsx"
    resources_path.write_text("workbook")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    output_directory = tmp_path / "out"

    summary = batch_runner.BatchSummary(results=[])
    readme_path = batch_runner.write_run_readme(
        resources_path, data_dir, output_directory, summary,
        naming_scheme_text="Naming scheme: <resource>_<component>.",
        workspace_root=tmp_path, now=_FIXED_NOW,
    )

    assert readme_path == output_directory / "README.txt"
    text = readme_path.read_text()
    assert "2026-08-10T12:30:00" in text
    assert str(Path("resources.xlsx")) in text
    assert str(Path("data")) in text
    assert "Naming scheme: <resource>_<component>." in text


def test_write_run_readme_reports_failures(tmp_path):
    output_directory = tmp_path / "out"
    summary = batch_runner.BatchSummary(results=[
        batch_runner.RowResult(1, "duluth", "high", "succeeded"),
        batch_runner.RowResult(2, "green_bay", "low", "failed", "boom"),
    ])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "1 succeeded, 1 failed out of 2 row(s)." in text
    assert "boom" in text


def test_write_run_readme_written_even_when_every_row_fails(tmp_path):
    output_directory = tmp_path / "out"
    summary = batch_runner.BatchSummary(results=[
        batch_runner.RowResult(1, "duluth", "high", "failed", "bad row"),
    ])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    assert readme_path.exists()
    assert "bad row" in readme_path.read_text()


def test_write_run_readme_written_when_zero_rows(tmp_path):
    output_directory = tmp_path / "out"
    summary = batch_runner.BatchSummary(results=[])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    assert readme_path.exists()


def test_write_run_readme_lists_files_written_this_run(tmp_path):
    output_directory = tmp_path / "out"
    output_directory.mkdir()
    written_path = output_directory / "duluth_high_grid.csv"
    written_path.write_text("data")
    summary = batch_runner.BatchSummary(results=[
        batch_runner.RowResult(1, "duluth", "high", "succeeded", output_paths=(written_path,)),
    ])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert str(Path("out") / "duluth_high_grid.csv") in text


def test_write_run_readme_flags_stale_unrecognized_files(tmp_path):
    output_directory = tmp_path / "out"
    output_directory.mkdir()
    written_path = output_directory / "duluth_high_grid.csv"
    written_path.write_text("data")
    stale_path = output_directory / "hey_this_file_is_no_output.csv"
    stale_path.write_text("legacy junk")

    summary = batch_runner.BatchSummary(results=[
        batch_runner.RowResult(1, "duluth", "high", "succeeded", output_paths=(written_path,)),
    ])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "hey_this_file_is_no_output.csv" in text
    assert "not created by this run" in text
    # The recognized output file must not be flagged as stale.
    stale_section = text.split("not created by this run", 1)[1]
    assert "duluth_high_grid.csv" not in stale_section


def test_write_run_readme_no_stale_files_message_when_clean(tmp_path):
    output_directory = tmp_path / "out"
    output_directory.mkdir()
    written_path = output_directory / "duluth_high_grid.csv"
    written_path.write_text("data")
    summary = batch_runner.BatchSummary(results=[
        batch_runner.RowResult(1, "duluth", "high", "succeeded", output_paths=(written_path,)),
    ])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "(none found)" in text


def test_write_run_readme_stale_scan_is_recursive(tmp_path):
    output_directory = tmp_path / "out"
    nested = output_directory / "duluth" / "high"
    nested.mkdir(parents=True)
    stale_nested = nested / "leftover.png"
    stale_nested.write_text("legacy")
    summary = batch_runner.BatchSummary(results=[])
    readme_path = batch_runner.write_run_readme(
        tmp_path / "resources.xlsx", tmp_path / "data", output_directory, summary,
        naming_scheme_text="n/a", workspace_root=tmp_path, now=_FIXED_NOW,
    )
    text = readme_path.read_text()
    assert "leftover.png" in text
    assert "not created by this run" in text
