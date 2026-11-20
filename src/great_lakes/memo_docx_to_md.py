"""Recover a memo's Markdown draft from its (hand-edited) Word document.

Inverse of `build_memo_docx`. The .docx is the source of truth for memo text once it is
edited in Word; this brings that text back into the Markdown draft so the draft can be
reviewed, diffed, and rebuilt from. Lossy by design -- it handles the constructs
`build_memo_docx` writes (header fields, `##` headings, paragraphs, bullets, numbered
items, pipe tables, figures, landscape sections, inline bold/italic/code) and nothing else.

Each embedded picture becomes the next `{{Fn}}` slot id, taken in order from the existing
draft (`figure_slots`), since the image itself carries no slot name.

Usage: python -m great_lakes.memo_docx_to_md DOCX [--draft PATH] [--out PATH]
"""

import argparse
import re
from collections.abc import Iterator
from itertools import groupby
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

_SLOT = re.compile(r"^\{\{([^}]+)\}\}$", re.MULTILINE)
_HEADER = re.compile(r"^([A-Z ]+):\t(.*)$", re.DOTALL)
_NUMBERED = re.compile(r"^(\d+)\.\t(.*)$", re.DOTALL)
_BULLET = re.compile(r"^[\u2022\uf0b7\u00b7\u25cf\u25e6\u25aa\u2013-]\t(.*)$", re.DOTALL)
_PLACEHOLDER = re.compile(r"^\[[^\]]*placeholder[^\]]*\]$", re.IGNORECASE)
_LIST_BASE_EMU = 228600  # build_memo_docx: top-level list items sit at 0.25 in
_LIST_STEP_EMU = 228600


def figure_slots(draft_text: str) -> list[str]:
    """Return the `{{Fn}}` figure slot ids in a Markdown draft, in order."""
    return _SLOT.findall(draft_text)


def _format_key(run: Run, bold_ok: bool) -> tuple[bool, bool, bool]:
    return (
        bool(run.bold) and bold_ok,
        bool(run.italic),
        (run.font.name or "").lower() == "consolas",
    )


def _inline(paragraph: Paragraph, bold_ok: bool = True) -> str:
    """Render a paragraph's runs as Markdown, merging adjacent runs of equal format."""
    parts = []
    runs = [(_format_key(run, bold_ok), run.text) for run in paragraph.runs]
    for (bold, italic, code), group in groupby(runs, key=lambda item: item[0]):
        text = "".join(item[1] for item in group)
        core = text.strip(" ")
        if not core:
            parts.append(text)
            continue
        lead, trail = text[: len(text) - len(text.lstrip(" "))], text[len(text.rstrip(" ")) :]
        if code:
            core = f"`{core}`"
        elif italic:
            core = f"*{core}*"
        if bold:
            core = f"**{core}**"
        parts.append(f"{lead}{core}{trail}")
    return "".join(parts).strip()


def _list_level(paragraph: Paragraph) -> int:
    indent = paragraph.paragraph_format.left_indent or _LIST_BASE_EMU
    return max(0, round((indent - _LIST_BASE_EMU) / _LIST_STEP_EMU))


def _table_markdown(table: Table) -> str:
    rows = [
        [_inline(cell.paragraphs[0], bold_ok=row_index > 0) for cell in row.cells]
        for row_index, row in enumerate(table.rows)
    ]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join(lines)


def _body_elements(doc: DocumentType) -> Iterator[Paragraph | Table]:
    for element in doc.element.body.iterchildren():
        if element.tag == qn("w:p"):
            yield Paragraph(element, doc)
        elif element.tag == qn("w:tbl"):
            yield Table(element, doc)


def docx_to_markdown(docx_path: Path, slots: list[str]) -> str:
    """Convert a memo .docx to Markdown draft text.

    `slots` are the figure slot ids assigned, in order, to the document's pictures.
    """
    doc = Document(str(docx_path))
    blocks: list[str] = []
    header: list[str] = []
    slot_iter = iter(slots)
    section_index = 0
    landscape = False
    seen_heading = False

    for item in _body_elements(doc):
        if isinstance(item, Table):
            blocks.append(_table_markdown(item))
            continue
        paragraph = item
        text = paragraph.text.strip()
        if paragraph._p.findall(".//" + qn("w:drawing")):
            try:
                blocks.append("{{" + next(slot_iter) + "}}")
            except StopIteration:
                raise ValueError(
                    f"{docx_path.name} has more figures than the {len(slots)} slot ids given"
                ) from None
        elif paragraph.style is not None and paragraph.style.name == "Heading 1":
            seen_heading = True
            blocks.append(f"## {text}")
        elif not seen_heading:
            if text and (match := _HEADER.match(paragraph.text)):
                header.append(f"**{match.group(1)}:** {_inline_after_tab(paragraph)}")
        elif not text:
            pass
        elif _PLACEHOLDER.match(text):
            blocks.append(text)
        elif match := _NUMBERED.match(paragraph.text.strip()):
            indent = "  " * _list_level(paragraph)
            blocks.append(f"{indent}{match.group(1)}. {_inline_after_tab(paragraph)}")
        elif _BULLET.match(paragraph.text.strip()):
            indent = "  " * _list_level(paragraph)
            blocks.append(f"{indent}- {_inline_after_tab(paragraph)}")
        else:
            blocks.append(_inline(paragraph))

        if paragraph._p.find(qn("w:pPr") + "/" + qn("w:sectPr")) is not None:
            section_index += 1
            is_landscape = doc.sections[section_index].orientation == WD_ORIENT.LANDSCAPE
            if is_landscape != landscape:
                landscape = is_landscape
                blocks.append("<!-- landscape -->" if landscape else "<!-- portrait -->")

    prefix = "\n".join(header) + "\n\n" if header else ""
    return prefix + "\n\n".join(blocks) + "\n"


def _inline_after_tab(paragraph: Paragraph) -> str:
    """Render a paragraph's runs without its leading `marker<TAB>` / `KEY:<TAB>`."""
    rendered = _inline(paragraph)
    # Drop the marker/key and the tab that follows it, whatever formatting wraps them.
    stripped = re.sub(r"^\*{0,2}[^\t]*?\*{0,2}\t", "", rendered, count=1)
    return stripped.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--draft", type=Path, required=True,
                        help="existing Markdown draft; supplies the figure slot ids")
    parser.add_argument("--out", type=Path, help="defaults to overwriting --draft")
    args = parser.parse_args()
    markdown = docx_to_markdown(args.docx, figure_slots(args.draft.read_text(encoding="utf-8")))
    out = args.out or args.draft
    out.write_text(markdown, encoding="utf-8", newline="\n")
    print(out)


if __name__ == "__main__":
    main()
