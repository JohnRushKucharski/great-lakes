"""Split the avg source workbook into one CSV per lake.

Reads `lake_levels_all_scenarios_9jul2026.xlsx` from data/raw/ and writes one CSV per
lake (superior_avg.csv, michiganhuron_avg.csv, stclair_avg.csv, erie_avg.csv,
ontario_avg.csv) into data/avg/. Each CSV has a "time" column (YYYY-MM-DD, matching
hydropattern's default pd.read_csv(parse_dates=[0]) behavior) followed by the 17
scenario columns (_0_0 .. _20_7) unchanged. The "month" column is dropped.

Run via `workflows/analysis/data-products/avg/scripts/clean.py`.
"""

from pathlib import Path

import pandas as pd

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


def clean_workbook(raw_dir: Path, out_dir: Path, overwrite: bool = False) -> list[Path]:
    """Read the source workbook in raw_dir and write one csv per lake to out_dir.

    Refuses (writes nothing) if any output exists, unless overwrite. Returns the paths
    written.
    """
    src_path = raw_dir / SOURCE_FILE
    out_paths = {sheet: out_dir / filename for sheet, filename in LAKES.items()}
    existing = [str(p) for p in out_paths.values() if p.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing output file(s): " + ", ".join(existing)
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    sheets = pd.read_excel(src_path, sheet_name=list(LAKES), engine="calamine")
    for sheet_name, out_path in out_paths.items():
        clean_lake_frame(sheets[sheet_name]).to_csv(out_path, index=False)
    return list(out_paths.values())
