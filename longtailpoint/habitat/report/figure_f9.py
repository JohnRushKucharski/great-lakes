"""F9 robustness chart: robustness tier by floor elevation, per habitat component and aim.

One diverging scale centred on baseline. A floor reliable at baseline is placed by how far
it holds up: baseline only < baseline + one 1.5 C scenario < both 1.5 C < both 1.5 C + part of
3 C < "3C" (both 1.5 C + all four 3 C scenarios; the robust set). A floor that fails baseline
is "never reliable" (no robust-set scenario works) or works only in lower-lake scenarios
(1.5C/0, 3C/0) or only in higher-lake scenarios (3C/15); 3C/5, 3C/10 and 1.5C/5 count as
neutral, and a tie goes to lower. Reliability cuts match F6. Musky and pondweed are separate
aims: each aim tier is its weakest component (musky = juvenile + spawning, with recruitment
shown separately; pondweed = growing season + winter survival). The overlap panel is a bonus
where the aims coincide, not a requirement.

Usage: python figure_f9.py [--out figures/F9.png]
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

REPORT_DIR = Path(__file__).resolve().parent
MUSKY_CSV = REPORT_DIR / "musky_reliability.csv"
POND_CSV = REPORT_DIR / "pondweed_reliability.csv"
OUT = REPORT_DIR / "figures" / "F9.png"

FLOORS_FT = tuple(float(f) for f in range(571, 580))
# Ordered worst -> best; (name, short cell label, color, hatch).
TIER_STYLES = (
    ("never reliable", "never", "#b2182b", ""),
    ("lower lake only", "lower", "#f4a582", ""),
    ("higher lake only", "higher", "#f4a582", "///"),
    ("baseline only", "base", "#f7f7f7", ""),
    ("baseline + one 1.5C", "+1\n1.5C", "#d9f0d3", ""),
    ("1.5C", "1.5C", "#a6dba0", ""),
    ("1.5C + part of 3C", "1.5C\n+3C", "#5aae61", ""),
    ("3C", "3C", "#1b7837", ""),
)
TIERS = tuple(t[0] for t in TIER_STYLES)
BASELINE = "_0_0"
BOTH_15C = ("_0_1.5", "_5_1.5")
ALL_3C = ("_0_3", "_5_3", "_10_3", "_15_3")
LOWER_LAKE = ("_0_1.5", "_0_3")
HIGHER_LAKE = ("_15_3",)
MUSKY_ROWS = [("juvenile_habitat", "Juvenile"), ("spawning_zones", "Spawning")]
MUSKY_EXTRA = ("recruitment_zones", "Recruitment (separate)")
POND_ROWS = [("growing_season_habitat", "Growing season"), ("winter_survival", "Winter survival")]
COMPONENTS = [key for key, _ in (*MUSKY_ROWS, MUSKY_EXTRA, *POND_ROWS)]


def _reliable(component: str, pct: float) -> bool:
    """Same cuts as F6: 75% of years; recruitment 8% of 5-year windows."""
    return pct >= (8.0 if component == "recruitment_zones" else 75.0)


def floor_tier(component: str, pcts: dict[str, float]) -> str | None:
    """Tier of one floor/component; None if the baseline value is missing (not run)."""
    if np.isnan(pcts.get(BASELINE, np.nan)):
        return None
    ok = {s for s, v in pcts.items() if not np.isnan(v) and _reliable(component, v)}
    if BASELINE not in ok:
        lower = len(ok & set(LOWER_LAKE))
        higher = len(ok & set(HIGHER_LAKE))
        if not ok & {*BOTH_15C, *ALL_3C}:
            return "never reliable"
        return "higher lake only" if higher > lower else "lower lake only"
    n_15c = len(ok & set(BOTH_15C))
    n_3c = len(ok & set(ALL_3C))
    if n_15c == 2:
        return "3C" if n_3c == len(ALL_3C) else "1.5C + part of 3C" if n_3c else "1.5C"
    return "baseline + one 1.5C" if n_15c == 1 else "baseline only"


def aim_tier(tiers: list[str | None]) -> str | None:
    """Weakest component tier; None if any component was not run at this floor."""
    if any(t is None for t in tiers):
        return None
    return min(tiers, key=TIERS.index)  # type: ignore[type-var]


def tier_table(results: pd.DataFrame) -> pd.DataFrame:
    """Tiers with rows = component, columns = floor (None where not run)."""
    table = pd.DataFrame(None, index=COMPONENTS, columns=list(FLOORS_FT), dtype=object)
    for (component, floor), group in results.groupby(["Component", "Floor (ft IGLD85)"]):
        if component in table.index and floor in table.columns:
            table.at[component, floor] = floor_tier(
                str(component), dict(zip(group["Scenario"], group["Percentage"], strict=True))
            )
    return table


def _aim_row(table: pd.DataFrame, components: list[str]) -> list[str | None]:
    return [aim_tier([_tier_or_none(table.at[c, f]) for c in components]) for f in FLOORS_FT]


def _tier_or_none(value: object) -> str | None:
    """pandas stores 'not run' as NaN; map back to None."""
    return value if isinstance(value, str) else None


def _draw(ax: plt.Axes, rows: list[tuple[str, list[str | None]]], title: str) -> None:
    for i, (_, tiers) in enumerate(rows):
        for j, tier in enumerate(tiers):
            if tier is None:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fc="#e0e0e0", ec="white", lw=1))
                continue
            _, label, color, hatch = TIER_STYLES[TIERS.index(tier)]
            ax.add_patch(plt.Rectangle((j, i), 1, 1, fc=color, ec="white", lw=1, hatch=hatch))
            ax.text(j + 0.5, i + 0.5, label, ha="center", va="center", fontsize=8,
                    color="white" if tier in ("never reliable", "3C") else "black",
                    bbox={"fc": color, "ec": "none", "pad": 0.5} if hatch else None)
    ax.set_xlim(0, len(FLOORS_FT))
    ax.set_ylim(len(rows), 0)
    ax.set_title(title, fontsize=11)
    ax.set_xticks(np.arange(len(FLOORS_FT)) + 0.5, [f"{f:.0f}" for f in FLOORS_FT], fontsize=9)
    ax.set_yticks(np.arange(len(rows)) + 0.5, [label for label, _ in rows], fontsize=9)
    ax.set_xlabel("Bottom elevation (ft, IGLD85)", fontsize=9)


def build_figure(results: pd.DataFrame) -> plt.Figure:
    table = tier_table(results)
    musky = [c for c, _ in MUSKY_ROWS]
    pond = [c for c, _ in POND_ROWS]
    musky_aim = _aim_row(table, musky)
    pond_aim = _aim_row(table, pond)
    both = [aim_tier([m, p]) for m, p in zip(musky_aim, pond_aim, strict=True)]

    def comp(key: str, label: str) -> tuple[str, list[str | None]]:
        return label, [_tier_or_none(v) for v in table.loc[key]]

    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5), gridspec_kw={"height_ratios": [4, 3]})
    _draw(axes[0, 0], [*(comp(k, v) for k, v in MUSKY_ROWS), ("Musky aim", musky_aim),
                       comp(*MUSKY_EXTRA)], "Musky (juvenile + spawning)")
    _draw(axes[0, 1], [*(comp(k, v) for k, v in POND_ROWS), ("Pondweed aim", pond_aim)],
          "Pondweed (growing + winter)")
    _draw(axes[1, 0], [("Musky aim", musky_aim), ("Pondweed aim", pond_aim),
                       ("Both aims (bonus)", both)], "Overlap (bonus, not required)")
    handles = [
        Patch(fc=c, ec="grey", hatch=h,
              label=name if short == name else f"{name}  [{short.replace(chr(10), ' ')}]")
        for name, short, c, h in TIER_STYLES
    ]
    handles.append(Patch(fc="#e0e0e0", ec="grey", label="not run"))
    legend_ax = axes[1, 1]
    legend_ax.axis("off")
    legend_ax.legend(handles=handles, loc="center", fontsize=8.5, frameon=False,
                     title="Worst  \u2192  best (diverging around baseline);\n"
                           "[cell label]", title_fontsize=8.5)
    fig.suptitle("Robustness by bottom elevation: how far each bottom elevation holds up "
                 "across the scenarios", fontsize=11)
    fig.tight_layout()
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    results = pd.concat([pd.read_csv(MUSKY_CSV), pd.read_csv(POND_CSV)])
    fig = build_figure(results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
