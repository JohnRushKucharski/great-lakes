"""One-call README.txt run record for the data-product scripts (see batch.run_readme)."""
from pathlib import Path
from typing import Sequence

from great_lakes.batch import run_readme


def record_run(
    output_dir: Path,
    title: str,
    inputs: Sequence[tuple[str, Path]],
    naming_scheme_text: str,
    written: Sequence[Path],
    workspace_root: Path,
) -> Path:
    """Write `output_dir/README.txt` listing the inputs and every file this run wrote."""
    return run_readme.write_readme(
        output_directory=output_dir,
        title=title,
        inputs=inputs,
        results_text=f"Wrote {len(written)} file(s).",
        naming_scheme_text=naming_scheme_text,
        written_paths=written,
        workspace_root=workspace_root,
    )
