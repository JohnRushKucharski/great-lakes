"""Recover the habitat memo draft from the hand-edited final .docx and show how it differs.

Writes outputs/memo_draft_from_docx.md and prints a diff against inputs/memo_draft.md plus
any structure differences (headings, figure count). The draft is replaced only with
`--promote`, after backing it up to outputs/memo_draft_before_sync.md.
"""
import shutil
from pathlib import Path
from typing import Optional

import typer

from great_lakes.memo import from_docx, sync
from great_lakes.paths import REPO_ROOT, Layout


def main(
    root: Path = typer.Option(REPO_ROOT, help="Repository root."),
    docx: Optional[Path] = typer.Option(
        None, help="Final memo. Default: the one .docx in deliverables/."),
    promote: bool = typer.Option(
        False, help="Replace inputs/memo_draft.md with the recovered draft (backs it up first)."),
) -> None:
    layout = Layout(root)
    draft = layout.habitat / "inputs" / "memo_draft.md"
    outputs = layout.habitat / "outputs"
    if docx is None:
        candidates = sorted((layout.habitat / "deliverables").glob("*.docx"))
        if len(candidates) != 1:
            raise typer.BadParameter(f"pass --docx; found {len(candidates)} in deliverables/")
        docx = candidates[0]
    old = draft.read_text(encoding="utf-8")
    recovered = from_docx.docx_to_markdown(docx, from_docx.figure_slots(old))
    outputs.mkdir(parents=True, exist_ok=True)
    recovered_path = outputs / "memo_draft_from_docx.md"
    recovered_path.write_text(recovered, encoding="utf-8", newline="\n")

    diff = sync.diff_text(old, recovered, draft.name, recovered_path.name)
    typer.echo(diff or "No text changes.")
    flags = sync.structure_differences(old, recovered)
    typer.echo("Structure differences: " + ("none" if not flags else ""))
    for flag in flags:
        typer.echo(f"  - {flag}")
    if promote:
        shutil.copyfile(draft, outputs / "memo_draft_before_sync.md")
        shutil.copyfile(recovered_path, draft)
        typer.echo(f"Promoted to {draft} (backup: {outputs / 'memo_draft_before_sync.md'})")
    else:
        typer.echo(f"Recovered draft: {recovered_path} (use --promote to adopt it)")


if __name__ == "__main__":
    typer.run(main)
