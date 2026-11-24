"""Split the swl source workbook into one workbook per Great Lake.

Reads `still_water_summary__22may2026.xlsm` from data/raw/ and writes one workbook per
lake (superior_swl.xlsx, michigan_swl.xlsx, huron_swl.xlsx, ontario_swl.xlsx) into
data/swl/clean/. Each has 5 sheets (the known scenarios), with a single header row: ID,
lat, lon, then the ARI values (0.1 .. 1000). Values are meters, IGLD85, as in the source.
Save points with no water level at any ARI (3 in michigan, with implausible coordinates)
are dropped, so they never reach the complete data or figures.

Run via `workflows/analysis/data-products/swl/scripts/clean.py`.
"""

from pathlib import Path

import pandas as pd

SOURCE_FILE = "still_water_summary__22may2026.xlsm"

# lake tag (as it appears in source sheet names) -> output filename
LAKES = {
    "sup": "superior_swl.xlsx",
    "mich": "michigan_swl.xlsx",
    "hur": "huron_swl.xlsx",
    "ont": "ontario_swl.xlsx",
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
    """Build source sheet name, e.g. "baseline (sup TWL BE)" (raw data keeps the old "TWL" name)."""
    return f"{scenario} ({lake_tag} TWL BE)"


def clean_scenario_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows without an `ID` (blank padding rows) and save points with no water level
    at any ARI (the source has a few, with implausible coordinates).

    Extracted as its own function so the transform can be unit-tested without
    reading the real source workbook.
    """
    df = df.dropna(subset=["ID"])
    ari_columns = [c for c in df.columns if c not in ("ID", "lat", "lon")]
    if not ari_columns:
        return df
    return df[df[ari_columns].notna().any(axis=1)]


def check_same_save_points(lake_tag: str, frames: dict[str, pd.DataFrame]) -> None:
    """Raise if a lake's scenario sheets do not list the same save-point IDs."""
    reference = next(iter(frames.values()))["ID"].tolist()
    for name, frame in frames.items():
        if frame["ID"].tolist() != reference:
            raise ValueError(f"Lake {lake_tag!r}: sheet {name!r} has different save points.")


def clean_workbook(raw_dir: Path, out_dir: Path, overwrite: bool = False) -> list[Path]:
    """Read the source workbook in raw_dir and write one workbook per lake to out_dir.

    Refuses (writes nothing) if any output exists, unless overwrite. Returns the paths
    written.
    """
    src_path = raw_dir / SOURCE_FILE
    out_paths = {tag: out_dir / filename for tag, filename in LAKES.items()}
    existing = [str(p) for p in out_paths.values() if p.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing output file(s): " + ", ".join(existing)
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    sheet_names = [
        source_sheet_name(scenario, lake_tag) for lake_tag in LAKES for scenario in SCENARIOS
    ]
    # Skip the 2 source header rows and assign the single new header directly.
    sheets = pd.read_excel(
        src_path, sheet_name=sheet_names, header=None, skiprows=2, names=NEW_HEADER,
        engine="calamine",
    )
    for lake_tag, out_path in out_paths.items():
        frames = {
            new_name: clean_scenario_frame(sheets[source_sheet_name(scenario, lake_tag)])
            for scenario, new_name in SCENARIOS.items()
        }
        check_same_save_points(lake_tag, frames)
        dropped = len(sheets[source_sheet_name("baseline", lake_tag)].dropna(subset=["ID"])) - len(
            frames["baseline-_0_0"])
        if dropped:
            print(f"{lake_tag}: dropped {dropped} save point(s) with no water levels.")
        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
            for new_name, df in frames.items():
                df.to_excel(writer, sheet_name=new_name, index=False)
    return list(out_paths.values())
