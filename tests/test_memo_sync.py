"""Tests for syncing a Markdown memo draft from the final Word document."""
from PIL import Image

from great_lakes.memo import from_docx, sync
from great_lakes.memo.to_docx import build_memo

OLD = """\
**TO:** Team

## 1. Intro

Text.

![Figure 2](../outputs/figures/F2.png)

## 2. Results

More.
"""


def test_figure_slots_accepts_markdown_image_lines_as_slots():
    assert from_docx.figure_slots(OLD) == ["![Figure 2](../outputs/figures/F2.png)"]


def test_figure_slots_still_returns_ids_for_brace_slots():
    assert from_docx.figure_slots("{{F1}}\n\ntext\n\n{{F4B}}\n") == ["F1", "F4B"]


def test_image_line_slots_round_trip_verbatim(tmp_path):
    Image.new("RGB", (40, 30), "white").save(tmp_path / "F2.png")
    draft = tmp_path / "draft.md"
    draft.write_text(OLD.replace("../outputs/figures/", ""), encoding="utf-8")
    docx_path = build_memo(draft, tmp_path / "m.docx")
    slots = from_docx.figure_slots(draft.read_text(encoding="utf-8"))
    markdown = from_docx.docx_to_markdown(docx_path, slots)
    assert "![Figure 2](F2.png)" in markdown
    assert "{{" not in markdown


def test_structure_differences_flags_changed_headings_and_figure_counts():
    new = OLD.replace("## 2. Results", "## 2. Findings") + "\n![Extra](x.png)\n"
    flags = sync.structure_differences(OLD, new)
    assert any("heading" in flag and "Findings" in flag for flag in flags)
    assert any("figure" in flag for flag in flags)


def test_structure_differences_is_empty_for_identical_structure():
    assert sync.structure_differences(OLD, OLD.replace("Text.", "Edited text.")) == []


def test_diff_text_is_empty_when_identical_and_unified_otherwise():
    assert sync.diff_text(OLD, OLD, "a", "b") == ""
    diff = sync.diff_text(OLD, OLD.replace("Text.", "Edited."), "old", "new")
    assert "--- old" in diff and "+Edited." in diff
