"""Package the results dashboard and the files it links into one shareable zip."""

import json
import re
import zipfile
from pathlib import Path

START_HERE = """\
Long Tail Point results dashboard
=================================

1. Unzip this folder, keeping its structure.
2. Open dashboard.html in a web browser (double-click it).

dashboard.html reads manifest.js and the figures and tables in the subfolders, so keep
all of them together. No internet connection or installation is needed.
"""


def linked_files(manifest_js: Path) -> list[str]:
    """Return the relative file paths the manifest links to (missing-file markers skipped)."""
    text = manifest_js.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, re.DOTALL)
    if match is None:
        raise ValueError(f"{manifest_js} is not a `window.MANIFEST = {{...}};` file")
    payload = json.loads(match.group(1))
    paths: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") != "missing" and isinstance(node.get("path"), str):
                paths.add(node["path"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return sorted(paths)


def package_dashboard(folder: Path, zip_path: Path) -> Path:
    """Zip `dashboard.html`, `manifest.js`, the linked outputs and START_HERE.txt.

    Raises before writing anything if a linked file is missing or is an input workbook.
    """
    links = linked_files(folder / "manifest.js")
    workbooks = [rel for rel in links if rel.lower().endswith((".xlsx", ".xlsm"))]
    if workbooks:
        raise ValueError(f"refusing to package input workbook(s): {', '.join(workbooks)}")
    missing = [rel for rel in links if not (folder / rel).is_file()]
    if missing:
        raise FileNotFoundError(f"linked files missing from {folder}: {', '.join(missing)}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(folder / "dashboard.html", "dashboard.html")
        z.write(folder / "manifest.js", "manifest.js")
        for rel in links:
            z.write(folder / rel, rel)
        z.writestr("START_HERE.txt", START_HERE)
    return zip_path
