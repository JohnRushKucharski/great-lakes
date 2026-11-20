"""Build the overtopping memo .docx from inputs/memo_draft.md into outputs/ (not deliverables/)."""
from pathlib import Path

import typer

from great_lakes.memo.to_docx import build_memo
from great_lakes.paths import REPO_ROOT, Layout


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    out = build_memo(
        layout.overtopping / "inputs" / "memo_draft.md",
        layout.overtopping / "outputs" / "longtailpoint_memo_draft.docx")
    typer.echo(f"Wrote {out}")


if __name__ == "__main__":
    typer.run(main)
