"""Split still_water_summary workbook into one file per Great Lake.

Reads `still_water_summary__22may2026.xlsm` from this directory
(data/raw/) and writes one workbook per lake
(superior_twl.xlsx, michigan_twl.xlsx, huron_twl.xlsx, ontario_twl.xlsx)
into the sibling data/clean/ directory. Each output workbook
has 5 sheets (one per scenario), with a single header row: ID, lat, lon,
followed by the numeric annual recurrence interval (ARI) values
(0.1 .. 1000).

Uses pandas (vectorized, no manual per-row loops) with the "calamine"
engine for reading (Rust-based, much faster than openpyxl for large
sheets) and "xlsxwriter" for writing. Requires the "dev" dependency
group: `uv sync --group dev`.

Run with: uv run python clean_still_water_summary.py
"""

from pathlib import Path

import pandas as pd

SOURCE_FILE = "still_water_summary__22may2026.xlsm"

# lake tag (as it appears in source sheet names) -> output filename
LAKES = {
    "sup": "superior_twl.xlsx",
    "mich": "michigan_twl.xlsx",
    "hur": "huron_twl.xlsx",
    "ont": "ontario_twl.xlsx",
}

# source scenario tag, in output sheet order -> new sheet name
#
# precip/temp deltas per tag come from the source workbook's own "summary" sheet
# (columns dT/dP), the authoritative scenario definitions -- NOT from the tag names
# themselves. lowLL ("low lake level") is dT=7, dP=0: no precip increase, max
# warming -- physically the dry/hot scenario that produces low lake levels.
# highLL ("high lake level") is dT=5, dP=20: max precip, moderate warming --
# physically the wet scenario that produces high lake levels. A previous version of
# this dict had the two suffixes swapped (lowLL -> _20_5, highLL -> _0_7), which
# silently mislabeled every known-scenario sheet's precip/temp deltas.
SCENARIOS = {
    "baseline": "baseline-_0_0",
    "modnear": "nearterm-_5_1.5",
    "modfuture_low": "moderate_low-_10_5",
    "lowLL": "extreme_low-_0_7",
    "highLL": "extreme_high-_20_5",
}

NEW_HEADER = ["ID", "lat", "lon", 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


def source_sheet_name(scenario: str, lake_tag: str) -> str:
    """Build source sheet name, e.g. "baseline (sup TWL BE)"."""
    return f"{scenario} ({lake_tag} TWL BE)"


def clean_scenario_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows without an `ID` (blank/padding rows in the raw sheet).

    Extracted as its own function so the transform can be unit-tested without
    reading the real source workbook.
    """
    return df.dropna(subset=["ID"])


def main() -> None:
    raw_dir = Path(__file__).parent
    clean_dir = raw_dir.parent / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    src_path = raw_dir / SOURCE_FILE

    # Fail fast, before doing any work, if any output would be clobbered.
    out_paths = {lake_tag: clean_dir / out_filename for lake_tag, out_filename in LAKES.items()}
    existing = [str(p) for p in out_paths.values() if p.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing output file(s): " + ", ".join(existing)
        )

    print(f"Loading source workbook: {src_path}")
    sheet_names = [
        source_sheet_name(scenario, lake_tag) for lake_tag in LAKES for scenario in SCENARIOS
    ]
    # One read call for all needed sheets; skip the 2 source header rows and
    # assign the single new header directly (no per-row Python loop).
    sheets = pd.read_excel(
        src_path,
        sheet_name=sheet_names,
        header=None,
        skiprows=2,
        names=NEW_HEADER,
        engine="calamine",
    )

    for lake_tag, out_filename in LAKES.items():
        out_path = out_paths[lake_tag]
        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
            for scenario, new_name in SCENARIOS.items():
                src_name = source_sheet_name(scenario, lake_tag)
                df = clean_scenario_frame(sheets[src_name])
                df.to_excel(writer, sheet_name=new_name, index=False)
                print(f"  {lake_tag}: {src_name!r} -> {out_filename}::{new_name!r}")
        print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
