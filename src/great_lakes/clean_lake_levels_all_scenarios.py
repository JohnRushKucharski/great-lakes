"""Split lake_levels_all_scenarios workbook into one CSV per lake.

Reads `lake_levels_all_scenarios_9jul2026.xlsx` from data/raw/ and writes one CSV per
lake (superior_avg.csv, michiganhuron_avg.csv, stclair_avg.csv, erie_avg.csv,
ontario_avg.csv) into data/clean/. Each output CSV has a "time" column (YYYY-MM-DD,
matching hydropattern's default pd.read_csv(parse_dates=[0]) behavior) followed by the
17 scenario columns (_0_0 .. _20_7) unchanged. The "month" column is dropped.

Uses pandas (vectorized, no manual per-row loops) with the "calamine"
engine for reading (Rust-based, much faster than openpyxl for large
sheets). Requires the "dev" dependency group: `uv sync --group dev`.

Run with: uv run python -m great_lakes.clean_lake_levels_all_scenarios
"""

from pathlib import Path

import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "lake_levels_all_scenarios_9jul2026.xlsx"

# sheet name -> output filename
LAKES = {
    "Superior": "superior_avg.csv",
    "MichiganHuron": "michiganhuron_avg.csv",
    "StClair": "stclair_avg.csv",
    "Erie": "erie_avg.csv",
    "Ontario": "ontario_avg.csv",
}

DATE_COLUMN = "Unnamed: 0"


def clean_lake_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop `month`, rename the date column to `time`, and format dates as strings.

    Dates span 1970-2999, beyond pandas' nanosecond datetime64 range, so the existing
    python datetime objects are formatted directly rather than round-tripped through
    pd.to_datetime (which would overflow). Extracted as its own function so the
    transform can be unit-tested without reading the real source workbook.
    """
    df = df.drop(columns=["month"]).rename(columns={DATE_COLUMN: "time"})
    df["time"] = df["time"].apply(lambda d: d.strftime("%Y-%m-%d"))
    return df


def main() -> None:
    raw_dir = WORKSPACE_ROOT / "data" / "raw"
    clean_dir = WORKSPACE_ROOT / "data" / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    src_path = raw_dir / SOURCE_FILE

    # Fail fast, before doing any work, if any output would be clobbered.
    out_paths = {sheet: clean_dir / out_filename for sheet, out_filename in LAKES.items()}
    existing = [str(p) for p in out_paths.values() if p.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing output file(s): " + ", ".join(existing)
        )

    print(f"Loading source workbook: {src_path}")
    sheets = pd.read_excel(
        src_path,
        sheet_name=list(LAKES),
        engine="calamine",
    )

    for sheet_name, out_filename in LAKES.items():
        df = clean_lake_frame(sheets[sheet_name])
        # Dates span 1970-2999, beyond pandas' nanosecond datetime64 range, so
        # format the existing python datetime objects directly rather than
        # round-tripping through pd.to_datetime (which would overflow).
        out_path = out_paths[sheet_name]
        df.to_csv(out_path, index=False)
        print(f"  {sheet_name!r} -> {out_path}")


if __name__ == "__main__":
    main()
