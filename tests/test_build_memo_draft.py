"""Tests for the Dead Horse Bay habitat memo scaffold builder."""

import importlib.util
import re
from pathlib import Path

from docx import Document
from PIL import Image

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "case-studies/long-tail-point/habitat/scripts/build_memo_draft.py"
)
spec = importlib.util.spec_from_file_location("build_report", SCRIPT)
assert spec is not None and spec.loader is not None
build_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_report)


def test_resolve_figures_uses_png_when_present_else_placeholder(tmp_path):
    (tmp_path / "F3.png").write_bytes(b"")
    text = "{{F3}}\n\n{{F4}}\n"

    out = build_report.resolve_figures(text, tmp_path)

    assert f"![F3]({(tmp_path / 'F3.png').as_posix()})" in out
    assert "[Figure F4 placeholder:" in out
    assert "{{" not in out


def test_resolve_figures_handles_lettered_slots(tmp_path):
    (tmp_path / "F4B.png").write_bytes(b"")

    out = build_report.resolve_figures("{{F4B}}\n\n{{F4C}}\n", tmp_path)

    assert f"![F4B]({(tmp_path / 'F4B.png').as_posix()})" in out
    assert "[Figure F4C placeholder:" in out


def test_resolve_figures_rejects_unknown_slot(tmp_path):
    import pytest

    with pytest.raises(KeyError):
        build_report.resolve_figures("{{F99}}", tmp_path)


def test_draft_has_every_slot_once_and_all_sections():
    draft = build_report.DRAFT.read_text(encoding="utf-8")

    for fig_id in build_report.FIGURES:
        assert draft.count("{{" + fig_id + "}}") == 1
    headings = re.findall(r"^## (.*)$", draft, flags=re.MULTILINE)
    assert [h.split(".")[0] for h in headings] == ["1", "2", "3", "4", "5", "6", "Appendix"]
    assert "This memo assesses how resilient the planned habitat restoration" in draft
    assert "**DATE:** 9 November 2026" in draft


def test_build_report_writes_docx_with_placeholders_and_real_figure(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    Image.new("RGB", (400, 300), "white").save(figures / "F1.png")
    out = tmp_path / "memo.docx"

    build_report.build_report(out_path=out, figures_dir=figures)

    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "9 November 2026" in text
    assert text.count("placeholder") == 9
    assert len(doc.inline_shapes) == 1
