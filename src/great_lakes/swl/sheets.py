"""Read `<lake>_swl.xlsx` workbooks and build scenario grids from their sheets."""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from great_lakes import units

# Sheet columns that are not ARI (Average Return Interval) values.
NON_ARI_COLUMNS = frozenset({"ID", "lat", "lon"})


def parse_scenario_sheet_name(sheet_name: str) -> str | None:
    """Parse a sheet name `<label>-_<precip>_<temp>` into its `_<precip>_<temp>` suffix.

    Splits on the first `-` only (labels may contain underscores). Returns None if the
    name has no `-`, a blank label, or a blank suffix.
    """
    if "-" not in sheet_name:
        return None
    label, _, suffix = sheet_name.partition("-")
    if not label or not suffix:
        return None
    return suffix


def build_scenario_ari_grid(
    coords: dict[str, tuple[float, float]],
    sheets: dict[str, pd.DataFrame],
    save_point_id: int,
    ari: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build the (precip x, temp y, water-level-in-feet z) grid for one save point/ARI.

    `coords` ({suffix: (precip, temp)}) sets which scenarios the grid spans; sheets whose
    suffix is not in `coords` are ignored. z is shaped (len(temps), len(precips)), NaN
    where a coordinate has no sheet or no row for `save_point_id`. Values are converted
    from meters to feet (datum unchanged).
    """
    precips = sorted({p for p, _ in coords.values()})
    temps = sorted({t for _, t in coords.values()})

    z = np.full((len(temps), len(precips)), np.nan)
    for sheet_name, df in sheets.items():
        suffix = parse_scenario_sheet_name(sheet_name)
        if suffix not in coords:
            continue
        precip, temp = coords[suffix]
        row = df.loc[df["ID"] == save_point_id, ari]
        if row.empty:
            continue
        z[temps.index(temp), precips.index(precip)] = units.convert_units(
            float(row.iloc[0]), "m", "ft"
        )

    return np.array(precips, dtype=float), np.array(temps, dtype=float), z


@lru_cache(maxsize=None)
def load_lake_sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Read every sheet of a `<lake>_swl.xlsx` workbook into {sheet_name: DataFrame}.

    Cached per path: workbooks are large (~20k save-point rows) and read repeatedly.
    """
    return pd.read_excel(path, sheet_name=None, engine="calamine")
