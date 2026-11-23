"""Small synthetic avg and swl data shaped like the Long Tail Point inputs."""
from pathlib import Path

import numpy as np
import pandas as pd

from great_lakes.swl.complete import ALL_SCENARIO_SUFFIXES

SAVE_POINT = 4999
ARIS = (0.1, 1, 10, 100, 1000)


def _delta(suffix: str) -> tuple[float, float]:
    _, precip, temp = suffix.split("_")
    return float(precip), float(temp)


def monthly_avg(years: int = 20, seed: int = 0) -> pd.DataFrame:
    """Monthly avg (m) with one column per scenario, planar in (precip, temp) plus noise."""
    rng = np.random.default_rng(seed)
    n = years * 12
    data: dict[str, object] = {"time": pd.date_range("1970-01-01", periods=n, freq="MS")}
    for suffix in ALL_SCENARIO_SUFFIXES:
        precip, temp = _delta(suffix)
        data[suffix] = 180.0 + 0.02 * precip - 0.1 * temp + rng.normal(0, 0.3, n)
    return pd.DataFrame(data)


def scenario_sheets() -> dict[str, pd.DataFrame]:
    """{suffix: frame} with columns ID, lat, lon, then one column per ARI (m, IGLD85)."""
    sheets = {}
    for suffix in ALL_SCENARIO_SUFFIXES:
        precip, temp = _delta(suffix)
        base = 180.5 + 0.02 * precip - 0.1 * temp
        rows = [[SAVE_POINT + i, 44.0 + i, -86.0, *(base + 0.2 * k + 0.01 * i
                                                      for k in range(len(ARIS)))]
                for i in range(2)]
        sheets[suffix] = pd.DataFrame(rows, columns=["ID", "lat", "lon", *ARIS])
    return sheets


def write_swl_workbook(path: Path) -> None:
    with pd.ExcelWriter(path) as writer:
        for suffix, frame in scenario_sheets().items():
            frame.to_excel(writer, sheet_name=f"michigan-{suffix}", index=False)
