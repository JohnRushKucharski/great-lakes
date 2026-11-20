"""Tests for the Long Tail Point memo .docx builder."""

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from PIL import Image

from great_lakes import build_memo_docx

DRAFT = """**TO:** Project Team
**SUBJECT:** Dune elevations

## 1. Purpose

Plain **bold** and *italic* and `code`.

![Figure 2](fig.png)

**Figure 2.** Caption text.

1. First
2. Second

| A | B |
|---|---|
| 1 | 2 |

---

## Appendix A. Extra

[Figure A-1 placeholder: screenshot]

1. Restart
"""


def _build(tmp_path):
    Image.new("RGB", (1000, 700), "white").save(tmp_path / "fig.png")
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT, encoding="utf-8")
    out = tmp_path / "memo.docx"
    build_memo_docx.build_memo(draft, out)
    return Document(str(out))


def test_parse_inline_splits_bold_italic_and_code():
    runs = build_memo_docx.parse_inline("a **b** *c* `d`")
    assert [(r.text.strip(), r.bold, r.italic, r.code) for r in runs if r.text.strip()] == [
        ("a", False, False, False),
        ("b", True, False, False),
        ("c", False, True, False),
        ("d", False, False, True),
    ]


def test_memo_uses_11pt_normal_text_and_one_inch_margins(tmp_path):
    doc = _build(tmp_path)
    assert doc.styles["Normal"].font.size == Pt(11)
    section = doc.sections[0]
    assert section.left_margin == section.right_margin == Inches(1)
    assert section.top_margin == section.bottom_margin == Inches(1)


def test_header_fields_render_before_first_section(tmp_path):
    texts = [p.text for p in _build(tmp_path).paragraphs]
    assert texts.index("TO:\tProject Team") < texts.index("1. Purpose")
    assert "SUBJECT:\tDune elevations" in texts


def test_figures_are_centered_and_fit_text_width(tmp_path):
    doc = _build(tmp_path)
    shapes = doc.inline_shapes
    assert len(shapes) == 1
    assert shapes[0].width <= Inches(6.5)
    holder = next(p for p in doc.paragraphs if p._p.xpath(".//pic:pic"))
    assert holder.alignment == WD_ALIGN_PARAGRAPH.CENTER
    placeholder = next(p for p in doc.paragraphs if "Figure A-1 placeholder" in p.text)
    assert placeholder.alignment == WD_ALIGN_PARAGRAPH.CENTER


def test_numbered_lists_restart_and_tables_render(tmp_path):
    doc = _build(tmp_path)
    texts = [p.text for p in doc.paragraphs]
    assert "1.\tFirst" in texts and "2.\tSecond" in texts and "1.\tRestart" in texts
    assert len(doc.tables) == 1
    assert doc.tables[0].cell(1, 1).text == "2"


def test_appendix_starts_on_new_page(tmp_path):
    doc = _build(tmp_path)
    appendix = next(p for p in doc.paragraphs if p.text == "Appendix A. Extra")
    assert appendix.paragraph_format.page_break_before


def test_landscape_block_gets_own_wide_page_and_larger_figure(tmp_path):
    Image.new("RGB", (2000, 1000), "white").save(tmp_path / "wide.png")
    draft = tmp_path / "draft.md"
    draft.write_text(
        "**TO:** Team\n\n## 1. A\n\nBefore.\n\n<!-- landscape -->\n\n![w](wide.png)\n\n"
        "**Figure 1.** Wide.\n\n<!-- portrait -->\n\nAfter.\n",
        encoding="utf-8",
    )
    out = tmp_path / "memo.docx"
    build_memo_docx.build_memo(draft, out)
    doc = Document(str(out))
    assert [s.orientation for s in doc.sections] == [
        WD_ORIENT.PORTRAIT, WD_ORIENT.LANDSCAPE, WD_ORIENT.PORTRAIT,
    ]
    assert doc.sections[1].page_width == Inches(11)
    assert doc.sections[1].page_height == Inches(8.5)
    assert doc.sections[2].page_width == Inches(8.5)
    assert Inches(6.5) < doc.inline_shapes[0].width <= Inches(9)
    assert not any("landscape" in p.text for p in doc.paragraphs)
