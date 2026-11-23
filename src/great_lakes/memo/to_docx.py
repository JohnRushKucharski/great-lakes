"""Build a memo (.docx) from its Markdown draft.

The Markdown draft is the source of truth. Supported Markdown:
memo header lines (`**KEY:** value`) before the first `##` heading, `##` headings
(`Appendix ...` starts a new page), paragraphs, `- ` bullets (two-space indent nests),
`1. ` numbered items, pipe tables, `![alt](path)` figures, standalone `[... placeholder ...]`
lines, and inline `**bold**`, `*italic*`, and `` `code` ``.

Library only; the case-study `build_memo_docx.py` scripts are the entry points.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.text.paragraph import Paragraph
from PIL import Image

FONT = "Calibri"
MAX_FIGURE_WIDTH = Inches(6.0)
MAX_FIGURE_HEIGHT = Inches(4.6)
MAX_LANDSCAPE_FIGURE_WIDTH = Inches(9.0)
MAX_LANDSCAPE_FIGURE_HEIGHT = Inches(5.2)

_HEADER = re.compile(r"^\*\*([A-Z ]+):\*\*\s*(.*)$")
_ORIENTATION = re.compile(r"^<!--\s*(landscape|portrait)\s*-->$")
_IMAGE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)$")
_PLACEHOLDER = re.compile(r"^\[[^\]]*placeholder[^\]]*\]$", re.IGNORECASE)
_NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET = re.compile(r"^( *)- (.*)$")
_INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*\s][^*]*?\*|`[^`]+`)")


@dataclass(frozen=True)
class Run:
    """A span of inline text with its formatting."""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False


def parse_inline(text: str) -> list[Run]:
    """Split Markdown inline formatting into runs."""
    runs = []
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            runs.append(Run(part[2:-2], bold=True))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            runs.append(Run(part[1:-1], code=True))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            runs.append(Run(part[1:-1], italic=True))
        else:
            runs.append(Run(part))
    return runs


def _add_runs(paragraph: Paragraph, text: str, size: Pt | None = None) -> None:
    for item in parse_inline(text):
        run = paragraph.add_run(item.text)
        run.bold = item.bold or None
        run.italic = item.italic or None
        if item.code:
            run.font.name = "Consolas"
            run.font.size = Pt(10)
        elif size is not None:
            run.font.size = size


def _set_styles(doc: DocumentType) -> None:
    for section in doc.sections:
        section.page_width, section.page_height = Inches(8.5), Inches(11)
        for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(section, side, Inches(1))
    normal = doc.styles["Normal"]
    normal.font.name = FONT  # type: ignore[attr-defined]
    normal.font.size = Pt(11)  # type: ignore[attr-defined]
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)  # type: ignore[union-attr]
    normal.paragraph_format.space_before = Pt(0)  # type: ignore[attr-defined]
    normal.paragraph_format.space_after = Pt(6)  # type: ignore[attr-defined]
    normal.paragraph_format.line_spacing = 1.0  # type: ignore[attr-defined]
    heading = doc.styles["Heading 1"]
    heading.font.name = FONT  # type: ignore[attr-defined]
    heading.font.size = Pt(12)  # type: ignore[attr-defined]
    heading.font.bold = True  # type: ignore[attr-defined]
    heading.font.color.rgb = RGBColor(0, 0, 0)  # type: ignore[attr-defined]
    heading.paragraph_format.space_before = Pt(12)  # type: ignore[attr-defined]
    heading.paragraph_format.space_after = Pt(4)  # type: ignore[attr-defined]


def _add_page_number_footer(doc: DocumentType) -> None:
    paragraph = doc.sections[0].footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            element = OxmlElement("w:fldChar")
            element.set(qn("w:fldCharType"), tag)
        else:
            element = OxmlElement("w:instrText")
            element.set(qn("xml:space"), "preserve")
            element.text = text
        run._r.append(element)


def _bottom_border(paragraph: Paragraph) -> None:
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("val", "single"), ("sz", "8"), ("space", "4"), ("color", "000000")):
        bottom.set(qn(f"w:{key}"), value)
    borders.append(bottom)
    paragraph._p.get_or_add_pPr().append(borders)


def _add_header(doc: DocumentType, fields: list[tuple[str, str]]) -> None:
    title = doc.add_paragraph()
    title.add_run("MEMORANDUM").bold = True
    title.runs[0].font.size = Pt(14)
    title.paragraph_format.space_after = Pt(12)
    paragraph = title
    for key, value in fields:
        paragraph = doc.add_paragraph()
        fmt = paragraph.paragraph_format
        fmt.tab_stops.add_tab_stop(Inches(1.4))
        fmt.left_indent, fmt.first_line_indent = Inches(1.4), Inches(-1.4)
        fmt.space_after = Pt(3)
        paragraph.add_run(f"{key}:").bold = True
        paragraph.add_run("\t")
        _add_runs(paragraph, value)
    paragraph.paragraph_format.space_after = Pt(6)
    _bottom_border(paragraph)


def _figure_size(path: Path, landscape: bool = False) -> tuple[int, int]:
    max_width = MAX_LANDSCAPE_FIGURE_WIDTH if landscape else MAX_FIGURE_WIDTH
    max_height = MAX_LANDSCAPE_FIGURE_HEIGHT if landscape else MAX_FIGURE_HEIGHT
    with Image.open(path) as image:
        width_px, height_px = image.size
    width = int(max_width)
    height = int(width * height_px / width_px)
    if height > max_height:
        height = int(max_height)
        width = int(height * width_px / height_px)
    return width, height


def _add_figure(doc: DocumentType, path: Path, landscape: bool = False) -> None:
    width, height = _figure_size(path, landscape)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.add_run().add_picture(str(path), width=width, height=height)


def _add_placeholder(doc: DocumentType, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = paragraph.paragraph_format
    fmt.keep_with_next = True
    fmt.space_before, fmt.space_after = Pt(36), Pt(36)
    run = paragraph.add_run(text)
    run.italic = True
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def _add_table(doc: DocumentType, lines: list[str]) -> None:
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in lines
        if not re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())
    ]
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = doc.styles["Table Grid"]
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            cell = table.cell(row_index, col_index)
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(0)
            _add_runs(paragraph, value, size=Pt(10))
            if row_index == 0:
                for run in paragraph.runs:
                    run.bold = True
                shading = OxmlElement("w:shd")
                shading.set(qn("w:val"), "clear")
                shading.set(qn("w:fill"), "D9D9D9")
                cell._tc.get_or_add_tcPr().append(shading)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def _add_list_item(doc: DocumentType, marker: str, text: str, level: int) -> None:
    paragraph = doc.add_paragraph()
    fmt = paragraph.paragraph_format
    indent = Inches(0.25 + 0.25 * level)
    fmt.left_indent, fmt.first_line_indent = indent, Inches(-0.25)
    fmt.tab_stops.add_tab_stop(indent)
    fmt.space_after = Pt(3)
    paragraph.add_run(f"{marker}\t")
    _add_runs(paragraph, text)


def _add_paragraph(doc: DocumentType, lines: list[str]) -> None:
    paragraph = doc.add_paragraph()
    is_caption = re.match(r"^\*\*(Figure|Table) ", lines[0]) is not None
    for index, line in enumerate(lines):
        if index:
            paragraph.add_run().add_break()
        _add_runs(paragraph, line, size=Pt(10) if is_caption else None)
    if is_caption:
        paragraph.paragraph_format.space_after = Pt(10)
        if lines[0].startswith("**Table"):
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.space_after = Pt(4)


def _start_section(doc: DocumentType, landscape: bool) -> None:
    """Start a new page section, Letter size, in the requested orientation, 1 inch margins."""
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    long_side, short_side = Inches(11), Inches(8.5)
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = (
        (long_side, short_side) if landscape else (short_side, long_side)
    )


def build_memo(draft_path: Path, out_path: Path) -> Path:
    """Render the Markdown memo draft to a Letter-size, 11 pt Word document.

    `<!-- landscape -->` / `<!-- portrait -->` lines start a new page in that orientation.
    """
    lines = draft_path.read_text(encoding="utf-8").splitlines()
    doc = Document()
    _set_styles(doc)
    _add_page_number_footer(doc)

    first_heading = next(i for i, line in enumerate(lines) if line.startswith("## "))
    fields = [m.groups() for line in lines[:first_heading] if (m := _HEADER.match(line))]
    _add_header(doc, [(key, value) for key, value in fields])

    index = first_heading
    landscape = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped == "---":
            index += 1
        elif orientation := _ORIENTATION.match(stripped):
            landscape = orientation.group(1) == "landscape"
            _start_section(doc, landscape)
            index += 1
        elif line.startswith("## "):
            heading = doc.add_heading(line[3:].strip(), level=1)
            heading.paragraph_format.page_break_before = line[3:].startswith("Appendix")
            index += 1
        elif image := _IMAGE.match(stripped):
            _add_figure(doc, (draft_path.parent / image.group(1)).resolve(), landscape)
            index += 1
        elif _PLACEHOLDER.match(stripped):
            _add_placeholder(doc, stripped)
            index += 1
        elif stripped.startswith("|"):
            block = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index])
                index += 1
            _add_table(doc, block)
        elif numbered := _NUMBERED.match(stripped):
            _add_list_item(doc, f"{numbered.group(1)}.", numbered.group(2), 0)
            index += 1
        elif bullet := _BULLET.match(line):
            _add_list_item(doc, "\u2022", bullet.group(2), len(bullet.group(1)) // 2)
            index += 1
        else:
            block = []
            while index < len(lines) and lines[index].strip() and not _is_block_start(
                lines[index]
            ):
                block.append(lines[index].strip())
                index += 1
            _add_paragraph(doc, block)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def _is_block_start(line: str) -> bool:
    stripped = line.strip()
    return bool(
        line.startswith("## ")
        or stripped == "---"
        or _ORIENTATION.match(stripped)
        or stripped.startswith("|")
        or _IMAGE.match(stripped)
        or _PLACEHOLDER.match(stripped)
        or _NUMBERED.match(stripped)
        or _BULLET.match(line)
    )

