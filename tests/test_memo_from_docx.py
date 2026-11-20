"""Tests for great_lakes.memo.from_docx (inverse of memo.to_docx)."""

from pathlib import Path

import pytest
from docx import Document
from PIL import Image

from great_lakes.memo.from_docx import docx_to_markdown, figure_slots
from great_lakes.memo.to_docx import build_memo

DRAFT = """\
**TO:** Project team
**SUBJECT:** A subject

## 1. Intro

A paragraph with **bold**, *italic*, and `code`.

- First bullet

  - Nested bullet

1. First step

2. Second step

| A | B |
|---|---|
| 1 | 2 |

**Table 1.** Caption text.

{{F1}}

**Figure 1.** Another caption.

<!-- landscape -->

## Appendix. Wide

{{F2}}
"""


@pytest.fixture
def built(tmp_path: Path) -> Path:
    """Build a docx from DRAFT, with `{{Fn}}` slots resolved to real PNGs."""
    for name in ("F1", "F2"):
        Image.new("RGB", (40, 20), "white").save(tmp_path / f"{name}.png")
    resolved = DRAFT.replace("{{F1}}", "![](F1.png)").replace("{{F2}}", "![](F2.png)")
    draft = tmp_path / "draft.md"
    draft.write_text(resolved, encoding="utf-8")
    return build_memo(draft, tmp_path / "memo.docx")


def test_figure_slots_reads_slot_ids_in_order() -> None:
    assert figure_slots(DRAFT) == ["F1", "F2"]


def test_round_trip_reproduces_draft(built: Path) -> None:
    assert docx_to_markdown(built, ["F1", "F2"]) == DRAFT


def test_word_style_bullets_and_split_runs(tmp_path: Path) -> None:
    """Word-edited docs use symbol bullets and split a bold span into adjacent runs."""
    doc = Document()
    doc.add_heading("1. Intro", level=1)
    bullet = doc.add_paragraph()
    bullet.add_run("\uf0b7\t")
    bullet.add_run("Bold ").bold = True
    bullet.add_run("split").bold = True
    bullet.add_run(" trailing ").bold = True
    bullet.add_run("text")
    path = tmp_path / "word.docx"
    doc.save(str(path))
    assert docx_to_markdown(path, []).endswith("- **Bold split trailing** text\n")


def test_too_few_slots_raises(built: Path) -> None:
    with pytest.raises(ValueError, match="figure"):
        docx_to_markdown(built, ["F1"])
