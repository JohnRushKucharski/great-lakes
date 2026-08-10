"""Analyze the known-vs-known TWL directionality for precip and temp deltas.

Each `<lake>_twl.xlsx` workbook has only 5 **known** (not filled/extrapolated)
scenarios. Of those 5, exactly one same-axis pair exists for each climate driver:

- **precip effect** (fixed temp_delta=5): `_10_5` -> `_20_5`
- **temp effect** (fixed precip_delta=0): `_0_0` -> `_0_7`

This script computes, for *every* save point and *every* ARI column in each of the 4
Great Lakes twl workbooks (no sampling), the percent change in TWL along each of
those two known-known pairs. It writes:

- a long-format CSV of the full per-save-point/per-ARI results (one row per
  lake/ID/ari), and
- an Excel workbook of summary tables (by lake x ARI, by ARI across lakes, and
  overall), to make the sign/magnitude pattern easy to see without opening the raw
  CSV.
"""

from pathlib import Path

import pandas as pd

from great_lakes import common_twl
from great_lakes.fillin_twl import known_scenario_coords

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "extrapolated"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "analysis"

# The only two same-axis known-vs-known pairs available (see module docstring).
PRECIP_PAIR = ("_10_5", "_20_5")  # fixed temp_delta=5, precip_delta 10 -> 20
TEMP_PAIR = ("_0_0", "_0_7")  # fixed precip_delta=0, temp_delta 0 -> 7


def sheet_name_for_suffix(
    suffix: str, known_coords: dict[str, tuple[float, float]], sheet_names: list[str]
) -> str:
    """Find the known sheet name whose bare suffix matches `suffix` exactly."""
    if suffix not in known_coords:
        raise ValueError(f"{suffix!r} is not a known scenario in this workbook.")
    for name in sheet_names:
        if common_twl.parse_scenario_sheet_name(name) == suffix:
            return name
    raise ValueError(f"No sheet found for suffix {suffix!r}.")


def analyze_lake(lake: str, data_dir: Path) -> pd.DataFrame:
    """Compute per-save-point/per-ARI precip and temp directionality for one lake.

    Returns a long-format DataFrame with one row per (ID, ari), columns:
    lake, ID, lat, lon, ari, twl_p10_dt5, twl_p20_dt5, precip_delta, precip_pct,
    twl_dt0_p0, twl_dt7_p0, temp_delta, temp_pct.
    """
    path = common_twl.resolve_lake_twl_path(lake, data_dir)
    sheets = common_twl.load_lake_sheets(path)
    sheet_names = list(sheets.keys())
    coords = known_scenario_coords(sheet_names)

    p10_name = sheet_name_for_suffix(PRECIP_PAIR[0], coords, sheet_names)
    p20_name = sheet_name_for_suffix(PRECIP_PAIR[1], coords, sheet_names)
    t0_name = sheet_name_for_suffix(TEMP_PAIR[0], coords, sheet_names)
    t7_name = sheet_name_for_suffix(TEMP_PAIR[1], coords, sheet_names)

    df_p10 = sheets[p10_name].set_index("ID")
    df_p20 = sheets[p20_name].set_index("ID")
    df_t0 = sheets[t0_name].set_index("ID")
    df_t7 = sheets[t7_name].set_index("ID")

    ari_columns = [c for c in df_p10.columns if c not in common_twl.NON_ARI_COLUMNS]

    rows = []
    for ari in ari_columns:
        precip_p10 = df_p10[ari]
        precip_p20 = df_p20[ari]
        temp_p0 = df_t0[ari]
        temp_p7 = df_t7[ari]

        chunk = pd.DataFrame({
            "lake": lake,
            "ID": df_p10.index,
            "lat": df_p10["lat"].to_numpy(),
            "lon": df_p10["lon"].to_numpy(),
            "ari": ari,
            "twl_p10_dt5": precip_p10.to_numpy(),
            "twl_p20_dt5": precip_p20.to_numpy(),
            "precip_delta": (precip_p20 - precip_p10).to_numpy(),
            "precip_pct": ((precip_p20 / precip_p10 - 1) * 100).to_numpy(),
            "twl_dt0_p0": temp_p0.to_numpy(),
            "twl_dt7_p0": temp_p7.to_numpy(),
            "temp_delta": (temp_p7 - temp_p0).to_numpy(),
            "temp_pct": ((temp_p7 / temp_p0 - 1) * 100).to_numpy(),
        })
        rows.append(chunk)

    return pd.concat(rows, ignore_index=True)


def summarize(results: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build summary tables from the full long-format results.

    Returns {"by_lake_and_ari": ..., "by_ari": ..., "overall": ...}, each a DataFrame
    of descriptive stats (mean/median/std/min/max) plus the share of rows where the
    sign matches "TWL falls as precip rises" / "TWL rises as temp rises" for
    precip_pct / temp_pct respectively.
    """
    def _agg(group: pd.DataFrame) -> pd.Series:
        n = len(group)
        return pd.Series({
            "n_save_points": n,
            "precip_pct_mean": group["precip_pct"].mean(),
            "precip_pct_median": group["precip_pct"].median(),
            "precip_pct_std": group["precip_pct"].std(),
            "precip_pct_min": group["precip_pct"].min(),
            "precip_pct_max": group["precip_pct"].max(),
            "pct_negative_precip": (group["precip_pct"] < 0).mean() * 100,
            "temp_pct_mean": group["temp_pct"].mean(),
            "temp_pct_median": group["temp_pct"].median(),
            "temp_pct_std": group["temp_pct"].std(),
            "temp_pct_min": group["temp_pct"].min(),
            "temp_pct_max": group["temp_pct"].max(),
            "pct_positive_temp": (group["temp_pct"] > 0).mean() * 100,
        })

    by_lake_and_ari = (
        results.groupby(["lake", "ari"], sort=True)
        .apply(_agg, include_groups=False)  # type: ignore[call-overload]
        .reset_index()
    )
    by_ari = (
        results.groupby("ari", sort=True)
        .apply(_agg, include_groups=False)  # type: ignore[call-overload]
        .reset_index()
    )
    overall = _agg(results).to_frame().T

    return {
        "by_lake_and_ari": by_lake_and_ari,
        "by_ari": by_ari,
        "overall": overall,
    }


def main(data_dir: Path = DATA_DIR, output_dir: Path = OUTPUT_DIR) -> None:
    lakes = list(common_twl.LAKE_TWL_FILENAMES)
    all_results = pd.concat(
        [analyze_lake(lake, data_dir) for lake in lakes], ignore_index=True
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "known_scenario_directionality.csv"
    all_results.to_csv(csv_path, index=False)

    summaries = summarize(all_results)
    xlsx_path = output_dir / "known_scenario_directionality_summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
        summaries["overall"].to_excel(writer, sheet_name="overall", index=False)
        summaries["by_ari"].to_excel(writer, sheet_name="by_ari", index=False)
        summaries["by_lake_and_ari"].to_excel(writer, sheet_name="by_lake_and_ari", index=False)

    n_rows = len(all_results)
    n_save_points = all_results.groupby("lake")["ID"].nunique().sum()
    n_aris = all_results["ari"].nunique()
    print(f"Analyzed {n_save_points} save points x {n_aris} ARIs across {len(lakes)} "
          f"lakes ({n_rows} total rows).")
    print(f"Raw results: {csv_path}")
    print(f"Summary tables: {xlsx_path}")
    print(summaries["overall"].to_string(index=False))


if __name__ == "__main__":
    main()
