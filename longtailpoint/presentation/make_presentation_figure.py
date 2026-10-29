"""Regenerate a marked presentation copy of a threshold-ARI elevation surface.

Usage: python make_presentation_figure.py <save_point_id> <ari> <out_stem>
       [elevation_offset_ft]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from great_lakes.longtailpoint_report import write_presentation_figure  # noqa: E402

BASELINE_DIR = Path(__file__).resolve().parent.parent / "batch_swl_output" / "baseline"


def read_grid_csv(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read a scenario-grid CSV into precipitation, temperature, and elevation arrays."""
    frame = pd.read_csv(path, index_col=0)
    xs = frame.columns.astype(float).to_numpy()
    ys = frame.index.astype(float).to_numpy()
    return xs, ys, frame.to_numpy()


def build_presentation_figure(
    save_point_id: str,
    ari: float,
    out_stem: str,
    out_dir: Path,
    elevation_offset_ft: float = 0.0,
) -> Path:
    """Render the full 17-scenario surface with model-status and design-threshold overlays."""
    grid_path = BASELINE_DIR / f"savepoint{save_point_id}_ari{ari:g}_elevation_grid.csv"
    xs, ys, zs = read_grid_csv(grid_path)
    values = {
        f"_{precip:g}_{temp:g}": float(zs[y_index, x_index])
        for y_index, temp in enumerate(ys)
        for x_index, precip in enumerate(xs)
        if np.isfinite(zs[y_index, x_index])
    }
    out_path = out_dir / f"{out_stem}.png"
    return write_presentation_figure(
        values,
        out_path,
        out_path.with_suffix(".csv"),
        int(save_point_id),
        ari,
        elevation_offset_ft,
    )


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        raise SystemExit(
            f"Usage: {sys.argv[0]} <save_point_id> <ari> <out_stem> [elevation_offset_ft]"
        )
    save_point_id, ari, out_stem = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    offset = float(sys.argv[4]) if len(sys.argv) == 5 else 0.0
    result = build_presentation_figure(
        save_point_id,
        ari,
        out_stem,
        Path(__file__).resolve().parent,
        elevation_offset_ft=offset,
    )
    print(f"Wrote {result} and {result.with_suffix('.csv')}")
