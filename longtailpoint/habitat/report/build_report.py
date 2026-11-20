"""Build the Dead Horse Bay habitat resilience memo (.docx) from `report_draft.md`.

The draft is the source of truth for text. Figure slots `{{F1}}`..`{{F9}}` (no F2: merged into
F1; F4 also has F4B/F4C, Jenny's maps) become the PNG
`figures/<id>.png` when it exists, otherwise a grey placeholder line. Styling comes from
`great_lakes.memo.to_docx` (same look as `longtailpoint\\MEMORANDUM.docx`).

Usage: python longtailpoint\\habitat\\report\\build_report.py [--out PATH]
"""

import argparse
import re
import tempfile
from pathlib import Path

from great_lakes.memo.to_docx import build_memo

REPORT_DIR = Path(__file__).resolve().parent
DRAFT = REPORT_DIR / "report_draft.md"
FIGURES_DIR = REPORT_DIR / "figures"
OUT = REPORT_DIR / "LTP_habitat_resilience_memo.docx"

FIGURES = {
    "F1": "Lake movement (mean level change by scenario)",
    "F3": "Elevation Ladder: planting and structure elevations vs future lake levels",
    "F4": "Marsh-zone share by scenario",
    "F4B": "Survey-point water depth, 3C dry (Jenny's map)",
    "F4C": "Survey-point water depth, 3C wet (Jenny's map)",
    "F5": "Woody debris structure scorecard",
    "F6": "Musky and pondweed reliability by bottom elevation",
    "F7": "Hydrograph: baseline vs 3C dry and 3C wet",
    "F8": "Low- and high-water cycle surfaces",
    "F9": "Robustness chart",
}

_SLOT = re.compile(r"^\{\{(F\d+[A-Z]?)\}\}$", re.MULTILINE)


def resolve_figures(text: str, figures_dir: Path = FIGURES_DIR) -> str:
    """Replace `{{Fn}}` slots with an image link (PNG present) or a placeholder line."""

    def replace(match: re.Match[str]) -> str:
        fig_id = match.group(1)
        title = FIGURES[fig_id]
        png = figures_dir / f"{fig_id}.png"
        if png.is_file():
            return f"![{fig_id}]({png.as_posix()})"
        return f"[Figure {fig_id} placeholder: {title}]"

    return _SLOT.sub(replace, text)


def build_report(
    draft: Path = DRAFT, out_path: Path = OUT, figures_dir: Path = FIGURES_DIR
) -> Path:
    """Render the draft with figure slots resolved to a Word memo."""
    resolved = resolve_figures(draft.read_text(encoding="utf-8"), figures_dir)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_draft = Path(tmp) / "draft.md"
        tmp_draft.write_text(resolved, encoding="utf-8")
        return build_memo(tmp_draft, out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    print(build_report(out_path=parser.parse_args().out))
