"""Build the Dead Horse Bay habitat resilience memo draft (.docx) from `inputs/memo_draft.md`.

The draft is the source of truth for text. Figure slots `{{F1}}`..`{{F9}}` (no F2: merged into
F1; F4 also has F4B/F4C, Jenny's maps) become the PNG
`outputs/figures/<id>.png` when it exists, otherwise a grey placeholder line. Styling comes from
`great_lakes.memo.to_docx`. The draft docx goes to `outputs/`; the hand-edited final memo lives
in `deliverables/` and is never overwritten.

Usage: uv run python case-studies/long-tail-point/habitat/scripts/build_memo_draft.py
"""

import re
import tempfile
from pathlib import Path

import typer

from great_lakes import habitat
from great_lakes.memo.to_docx import build_memo
from great_lakes.paths import REPO_ROOT, Layout

_LAYOUT = Layout()
DRAFT = _LAYOUT.habitat / "inputs" / "memo_draft.md"
FIGURES_DIR = habitat.figures_dir(_LAYOUT)
OUT = _LAYOUT.habitat / "outputs" / "LTP_habitat_resilience_memo_draft.docx"

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


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    out = build_report(
        layout.habitat / "inputs" / "memo_draft.md",
        layout.habitat / "outputs" / OUT.name,
        habitat.figures_dir(layout),
    )
    typer.echo(f"Wrote {out}")


if __name__ == "__main__":
    typer.run(main)
