"""Tests for great_lakes.swl.gates: the fill-vs-climate_canvas and ARI-curve gates."""
from pathlib import Path

import pandas as pd
import pytest

from great_lakes.ari import SWL_ARIS
from great_lakes.swl import gates as cfc

# 5 known scenarios + 1 in-hull filled scenario, enough to exercise the comparison
# at ARI=1 for a single lake.
_KNOWN_SHEETS = {
    "baseline-_0_0": (0.0, 0.0),
    "nearterm-_5_1.5": (5.0, 1.5),
    "moderate_low-_10_5": (10.0, 5.0),
    "extreme_low-_20_5": (20.0, 5.0),
    "extreme_high-_0_7": (0.0, 7.0),
}


def _sheet(value: float) -> pd.DataFrame:
    rows = {"ID": [1], "lat": [44.0], "lon": [-87.0]}
    for ari in SWL_ARIS:
        rows[ari] = [value]
    return pd.DataFrame(rows)


def _write_workbook(path: Path, sheets: dict) -> None:
    with pd.ExcelWriter(path) as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)


@pytest.fixture
def clean_dir(tmp_path):
    d = tmp_path / "data" / "clean"
    d.mkdir(parents=True)
    sheets = {name: _sheet(100.0 + i) for i, name in enumerate(_KNOWN_SHEETS)}
    _write_workbook(d / "superior_swl.xlsx", sheets)
    return d


@pytest.fixture
def filled_dir(tmp_path):
    d = tmp_path / "data" / "filled"
    d.mkdir(parents=True)
    sheets = {"filled-_5_3": _sheet(103.5)}  # one in-hull target scenario
    _write_workbook(d / "superior_swl.xlsx", sheets)
    return d


@pytest.fixture
def small_scope(monkeypatch):
    monkeypatch.setattr(cfc, "LAKES", ("superior",))
    monkeypatch.setattr(cfc, "ARIS", (1.0,))


def test_run_produces_one_row_per_in_hull_target_scenario(clean_dir, filled_dir, small_scope):
    df = cfc.run(clean_dir, filled_dir)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["lake"] == "superior"
    assert row["scenario"] == "_5_3"
    assert row["ari"] == 1.0
    assert "fillin_swl_ft" in row
    assert "climate_canvas_ft" in row
    assert "diff_ft" in row


def test_check_max_diff_passes_within_tolerance_and_fails_beyond():
    ok = pd.DataFrame({"diff_ft": [0.01, -0.049]})
    assert cfc.check_max_diff(ok) == pytest.approx(0.049)
    with pytest.raises(cfc.GateFailure, match="0.0600"):
        cfc.check_max_diff(pd.DataFrame({"diff_ft": [0.01, -0.06]}))


def test_check_max_diff_fails_when_nothing_was_compared():
    with pytest.raises(cfc.GateFailure, match="nothing"):
        cfc.check_max_diff(pd.DataFrame({"diff_ft": []}))


def test_run_gate_writes_csv_and_readme_then_passes(
    clean_dir, filled_dir, small_scope, tmp_path, monkeypatch
):
    monkeypatch.setattr(cfc, "TOLERANCE_FT", 100.0)  # fixture's filled value is arbitrary
    output_dir = tmp_path / "out"
    comparison = cfc.run_gate(clean_dir, filled_dir, output_dir, workspace_root=tmp_path)
    assert len(comparison) == 1
    assert (output_dir / "filled_vs_climate_canvas_comparison.csv").exists()
    text = (output_dir / "README.txt").read_text()
    assert "superior_swl.xlsx" in text
    assert "filled_vs_climate_canvas_comparison.csv" in text


def test_run_gate_writes_outputs_even_when_it_fails(
    clean_dir, filled_dir, small_scope, tmp_path, monkeypatch
):
    monkeypatch.setattr(cfc, "TOLERANCE_FT", 0.0)
    output_dir = tmp_path / "out"
    with pytest.raises(cfc.GateFailure):
        cfc.run_gate(clean_dir, filled_dir, output_dir, workspace_root=tmp_path)
    assert (output_dir / "filled_vs_climate_canvas_comparison.csv").exists()


# ---- ARI-curve gate ----------------------------------------------------------------

def _curve_sheet(values: list[float], ids=(1,)) -> pd.DataFrame:
    frame = {"ID": list(ids), "lat": [44.0] * len(ids), "lon": [-87.0] * len(ids)}
    for ari, value in zip(SWL_ARIS, values):
        frame[ari] = [value] * len(ids)
    return pd.DataFrame(frame)


def test_find_ari_curve_violations_accepts_non_decreasing_curves():
    rising = [float(i) for i in range(len(SWL_ARIS))]
    assert cfc.find_ari_curve_violations({"a-_0_0": _curve_sheet(rising)}).empty


def test_find_ari_curve_violations_flags_decreasing_and_nan_values():
    values = [float(i) for i in range(len(SWL_ARIS))]
    values[5] = values[4] - 1.0
    values[7] = float("nan")
    found = cfc.find_ari_curve_violations({"a-_0_0": _curve_sheet(values)})
    assert set(found["problem"]) == {"decreasing", "missing"}
    assert set(found["sheet"]) == {"a-_0_0"}


def test_run_ari_gate_passes_clean_workbooks_and_fails_bad_ones(tmp_path):
    good = [float(i) for i in range(len(SWL_ARIS))]
    bad = good[:3] + [0.0] + good[4:]
    workbook = tmp_path / "superior_swl.xlsx"
    _write_workbook(workbook, {"a-_0_0": _curve_sheet(good)})
    out_dir = tmp_path / "out"
    cfc.run_ari_gate(tmp_path, out_dir, tmp_path, lake_names=("superior",))
    assert (out_dir / "README.txt").exists()
    assert not (out_dir / "ari_curve_violations.csv").exists()

    _write_workbook(workbook, {"a-_0_0": _curve_sheet(bad)})
    with pytest.raises(cfc.GateFailure, match="superior"):
        cfc.run_ari_gate(tmp_path, out_dir, tmp_path, lake_names=("superior",))
    assert (out_dir / "ari_curve_violations.csv").exists()
    assert "ari_curve_violations.csv" in (out_dir / "README.txt").read_text()
