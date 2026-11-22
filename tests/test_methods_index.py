"""docs/methods-index.md must list every file in a `methods/` folder and have no dead links."""

import re
from pathlib import Path

from great_lakes.paths import REPO_ROOT

INDEX = REPO_ROOT / "docs" / "methods-index.md"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ROOTS = ("data-products", "analyses", "case-studies")
SKIP_PARTS = {"outputs", "__pycache__", ".ipynb_checkpoints"}
STATUSES = ("final", "draft, incomplete")


def _methods_files() -> list[Path]:
    return sorted(
        p
        for root in ROOTS
        for folder in (REPO_ROOT / root).rglob("methods")
        if folder.is_dir() and not SKIP_PARTS & set(folder.relative_to(REPO_ROOT).parts)
        for p in folder.rglob("*")
        if p.is_file() and not SKIP_PARTS & set(p.relative_to(REPO_ROOT).parts)
    )


def _links() -> list[str]:
    targets = LINK.findall(INDEX.read_text(encoding="utf-8"))
    return [t.split("#")[0] for t in targets if not t.startswith(("http", "#"))]


def test_every_methods_file_is_indexed():
    indexed = {(INDEX.parent / t).resolve() for t in _links()}
    missing = [
        str(p.relative_to(REPO_ROOT)) for p in _methods_files() if p.resolve() not in indexed
    ]
    assert not missing, f"not listed in docs/methods-index.md: {missing}"


def test_index_links_resolve():
    dead = [t for t in _links() if not (INDEX.parent / t).exists()]
    assert not dead, f"dead links in docs/methods-index.md: {dead}"


def test_index_rows_have_a_known_status():
    lines = INDEX.read_text(encoding="utf-8").splitlines()
    rows = [ln for ln in lines if "](" in ln and ln.lstrip().startswith("|")]
    bad = [ln for ln in rows if ln.strip().strip("|").split("|")[-1].strip() not in STATUSES]
    assert rows and not bad, f"rows without a status ({STATUSES}): {bad}"
