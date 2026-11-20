"""F4 marsh-zone share by scenario (heatmap) + Jenny's own 3C dry / 3C wet depth maps.

Share of the 288 survey points inside each Jenny marsh-zone depth range, per scenario
(baseline + robust set, ordered dry -> wet by mean lake level). Zones overlap, so columns do
not sum to 100%. Unrooted floating (any depth) is omitted, as in F3. The two depth maps
(F4B 3C/0, F4C 3C/15) are copied unchanged from Jenny's memo, not redrawn.

Usage: python figure_f4.py [--out figures/F4.png]
"""

import argparse
import sys
import zipfile
from collections.abc import Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figure_f3 import (  # type: ignore[import-not-found]  # noqa: E402
    LEVELS_CSV,
    M_TO_FT,
    SURVEY_XLSX,
    ZONE_DEPTHS_FT,
)

OUT = Path(__file__).resolve().parent / "figures" / "F4.png"
ZONES = tuple(ZONE_DEPTHS_FT)

HEATMAP_SCENARIOS = {
    "_0_0": "Baseline",
    "_0_1.5": "1.5C/0",
    "_5_1.5": "1.5C/5",
    "_0_3": "3C/0",
    "_5_3": "3C/5",
    "_10_3": "3C/10",
    "_15_3": "3C/15",
}
JENNY_DOCX = SURVEY_XLSX.parent / "longtail_habitat_summary_28oct2026.docx"
# Jenny's own survey-point depth maps (her memo Figs 7 and 8), copied unchanged.
JENNY_MAPS = {"F4B": "word/media/image8.png", "F4C": "word/media/image9.png"}


def zone_shares(bottoms_ft: np.ndarray, level_ft: float) -> pd.Series:
    """Fraction of survey points in each marsh-zone depth range (inclusive) at level_ft."""
    depths = level_ft - np.asarray(bottoms_ft, dtype=float)
    eps = 1e-6  # floating-point noise only; boundary points count as inside
    return pd.Series(
        {z: float(((depths >= lo - eps) & (depths <= hi + eps)).mean()) for z, (lo, hi) in
         ZONE_DEPTHS_FT.items()}
    )


def order_by_level(levels_ft: Mapping[str, float]) -> list[str]:
    """Scenario codes sorted from lowest to highest mean level (dry -> wet)."""
    return sorted(levels_ft, key=lambda s: levels_ft[s])


def mean_levels_ft(levels_m: pd.DataFrame) -> dict[str, float]:
    """Mean monthly level (ft) per scenario column; input in m, no datum change."""
    return {s: float(levels_m[s].mean() * M_TO_FT) for s in levels_m.columns}


def save_point_elevations(path: Path = SURVEY_XLSX) -> np.ndarray:
    """Bottom elevations (ft IGLD85) of the Dead Horse Bay survey points, from depth_analysis."""
    sheet = pd.read_excel(path, sheet_name="depth_analysis")
    return sheet["Estimated Bottom elevation (ft)"].dropna().to_numpy(dtype=float)


def copy_jenny_maps(out_dir: Path, docx: Path = JENNY_DOCX) -> list[Path]:
    """Copy Jenny's depth-map images unchanged from her memo to out_dir as F4B/F4C.png."""
    written = []
    with zipfile.ZipFile(docx) as z:
        for fig_id, member in JENNY_MAPS.items():
            target = out_dir / f"{fig_id}.png"
            target.write_bytes(z.read(member))
            written.append(target)
    return written


def build_figure(levels_m: pd.DataFrame, bottoms_ft: np.ndarray) -> plt.Figure:
    levels = mean_levels_ft(levels_m)
    scenarios = order_by_level({s: levels[s] for s in HEATMAP_SCENARIOS})
    shares = pd.DataFrame({s: zone_shares(bottoms_ft, levels[s]) for s in scenarios})
    fig, ax = plt.subplots(figsize=(8, 4.2))
    values = shares.to_numpy(dtype=float) * 100
    ax.imshow(values, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j]:.0f}", ha="center", va="center", fontsize=8,
                    color="white" if values[i, j] > 60 else "black")
    ax.set_xticks(range(len(scenarios)), [
        f"{HEATMAP_SCENARIOS[s]}\n{levels[s]:.1f} ft" for s in scenarios], fontsize=8)
    ax.set_yticks(range(len(ZONES)), [
        f"{z} ({lo:g}-{hi:g} ft)" for z, (lo, hi) in ZONE_DEPTHS_FT.items()], fontsize=8)
    ax.set_title("Survey points in each marsh zone (% of 288), by scenario", fontsize=10)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    levels = pd.read_csv(LEVELS_CSV, index_col="time")
    fig = build_figure(levels, save_point_elevations())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"Wrote {args.out}")
    if JENNY_DOCX.is_file():
        for path in copy_jenny_maps(args.out.parent):
            print(f"Copied {path}")


if __name__ == "__main__":
    main()
