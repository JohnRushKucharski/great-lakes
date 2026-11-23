"""Lake names, avg/swl file names and paths, lake centroids, and save-point selection."""

from functools import lru_cache
from math import cos, radians
from pathlib import Path

import pandas as pd

# lake code -> swl xlsx filename (same name in data/swl/clean/ and data/swl/complete/).
# Only 4 lakes have swl data; michigan and huron are separate files here, unlike avg's
# combined "michiganhuron" (stclair and erie have no swl data).
LAKE_SWL_FILENAMES = {
    "superior": "superior_swl.xlsx",
    "michigan": "michigan_swl.xlsx",
    "huron": "huron_swl.xlsx",
    "ontario": "ontario_swl.xlsx",
}

# swl-lake code -> avg-lake key. Michigan and Huron are one hydraulically-connected lake
# sharing a single avg record (docs/adr/0001-row-shift-extrapolation-for-out-of-hull-
# scenarios.md: extrapolation shifts a swl sheet by a delta in average lake level).
SWL_LAKE_TO_AVG_LAKE = {
    "superior": "superior",
    "michigan": "michiganhuron",
    "huron": "michiganhuron",
    "ontario": "ontario",
}

# avg-lake key -> avg csv filename (only lakes that have swl data).
LAKE_AVG_FILENAMES = {
    "superior": "superior_avg.csv",
    "michiganhuron": "michiganhuron_avg.csv",
    "ontario": "ontario_avg.csv",
}

# lake -> (lat, lon) of the lake centroid, in degrees.
LAKE_CENTROIDS: dict[str, tuple[float, float]] = {
    "superior": (47.72, -86.94),
    "michigan": (44.01, -86.76),
    "huron": (44.94, -82.22),
    "erie": (42.25, -81.15),
    "ontario": (43.63, -77.62),
}


def resolve_lake_swl_path(lake: str, data_dir: Path) -> Path:
    """Resolve a lake code to its swl xlsx path under data_dir."""
    return data_dir / LAKE_SWL_FILENAMES[lake]


def resolve_lake_avg_path(lake: str, data_dir: Path) -> Path:
    """Resolve a swl-lake code (e.g. "michigan") to its avg csv path.

    Michigan and huron share one avg csv despite having separate swl workbooks.
    """
    return data_dir / LAKE_AVG_FILENAMES[SWL_LAKE_TO_AVG_LAKE[lake]]


@lru_cache(maxsize=None)
def read_avg_scenario_means(lake: str, data_dir: Path) -> dict[str, float]:
    """Mean level per scenario ({"_0_0": 183.3, ...}) of a lake's avg csv.

    The mean spans the whole synthetic record (~12,360 monthly rows, 1970-2999), i.e.
    AVG(l, s) in ADR 0001's row-shift math. Cached per (lake, data_dir).
    """
    frame = pd.read_csv(resolve_lake_avg_path(lake, data_dir))
    return {column: float(frame[column].mean()) for column in frame.columns if column != "time"}


def lake_centroid_save_point_id(lake: str, sheets: dict[str, pd.DataFrame]) -> int:
    """ID of the save point nearest the lake's centroid (LAKE_CENTROIDS).

    Longitude differences are scaled by cos(latitude) so distances are comparable on the
    ground. Uses the first sheet's save points (identical across a workbook's sheets).
    For data-product cleaning and figures; resource analyses select save points by
    their own ID/lat/lon instead.
    """
    centroid_lat, centroid_lon = LAKE_CENTROIDS[lake]
    frame = next(iter(sheets.values()))
    lon_scale = cos(radians(centroid_lat))
    lat_diff = frame["lat"] - centroid_lat
    lon_diff = (frame["lon"] - centroid_lon) * lon_scale
    dist = (lat_diff**2 + lon_diff**2) ** 0.5
    return int(frame.loc[dist.idxmin(), "ID"])  # type: ignore[arg-type]
