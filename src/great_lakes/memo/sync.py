"""Compare a Markdown memo draft with one recovered from its edited Word document."""

import difflib
import re

_HEADING = re.compile(r"^## .*$", re.MULTILINE)
_FIGURE = re.compile(r"^(?:\{\{[^}]+\}\}|!\[[^\]]*\]\([^)]*\))$", re.MULTILINE)


def diff_text(old: str, new: str, old_name: str, new_name: str) -> str:
    """Unified diff of two drafts; empty string when identical."""
    lines = difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True), old_name, new_name
    )
    return "".join(lines)


def structure_differences(old: str, new: str) -> list[str]:
    """Flag headings or figure counts that differ, as a sign the recovery went wrong."""
    flags = []
    old_headings, new_headings = _HEADING.findall(old), _HEADING.findall(new)
    for heading in new_headings:
        if heading not in old_headings:
            flags.append(f"heading added or renamed: {heading}")
    for heading in old_headings:
        if heading not in new_headings:
            flags.append(f"heading missing: {heading}")
    old_figures, new_figures = len(_FIGURE.findall(old)), len(_FIGURE.findall(new))
    if old_figures != new_figures:
        flags.append(f"figure count differs: draft {old_figures}, recovered {new_figures}")
    return flags
