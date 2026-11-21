"""Pondweed (submergent marker) habitat runs across floor elevations 571-577 ft.

Same criteria as the reviewed `methods/pondweed_habitat.ipynb` notebook, run headless for a
sweep of floors. Per scenario: share of complete years that meet winter survival (depth
>= 0.5 m all year) and the growing season (depth 1-3 m May-Aug, monthly rise <= 0.15 m).
Floors are ft IGLD85; lake levels are m IGLD85 (units converted here only, no datum change).

Needs hydropattern >= 0.3 (e.g. PYTHONPATH=..\\hydropattern).
Usage: uv run python case-studies/long-tail-point/habitat/scripts/pondweed_runs.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import typer
from hydropattern.parsers import magnitude_parser, timing_parser
from hydropattern.patterns import Characteristic, CharacteristicType, Component
from hydropattern.scenario_grid import parse_scenario_name
from hydropattern.scenarios import evaluate_scenarios
from hydropattern.timeseries import Timeseries

from great_lakes import habitat
from great_lakes.paths import REPO_ROOT, Layout

LEVELS_CSV = habitat.levels_csv(Layout())
FLOORS_FT = (571.0, 572.0, 573.0, 574.0, 575.0, 576.0, 577.0)
FT_TO_M = 0.3048
GROWING_MONTHS = (5, 6, 7, 8)
GROWING_DOY = (121, 243)  # May 1 - Aug 31 on hydropattern's 365-day calendar
MAX_RISE_M = 0.15


def complete_year_labels(dates: pd.DatetimeIndex) -> list[int]:
    """Calendar years with all 12 months, after checking the index is consecutive monthly."""
    if dates.hasnans or not dates.is_unique or not dates.is_monotonic_increasing:
        raise ValueError("Monthly timestamps must be valid, unique, and increasing.")
    steps = np.diff(dates.year * 12 + dates.month)
    if len(dates) < 2 or not (dates.day == 1).all() or not np.all(steps == 1):
        raise ValueError("Expected consecutive monthly observations on the first of each month.")
    counts = pd.Series(dates.year).value_counts().sort_index()
    return counts.index[counts.eq(12)].tolist()


def annual_verdicts(outcomes: pd.Series, required_months: tuple[int, ...]) -> pd.Series:
    """Per complete year: 0 if any required month failed, 1 if all passed, else NaN."""
    complete = complete_year_labels(outcomes.index)
    verdicts = {}
    for label, year in outcomes.groupby(outcomes.index.year):
        if label not in complete:
            continue
        required = year.loc[year.index.month.isin(required_months)]
        verdicts[int(label)] = (
            0.0 if required.eq(0).any() else 1.0 if required.eq(1).all() else np.nan
        )
    return pd.Series(verdicts, name=outcomes.name, dtype=float).rename_axis("Water year")


def _annual_summary(annual: pd.Series) -> dict[str, float | int]:
    total = len(annual)
    qualifying = int(annual.eq(1).sum())
    unknown = int(annual.isna().sum())
    return {
        "Complete years": total,
        "Qualifying years": qualifying,
        "Failed years": int(annual.eq(0).sum()),
        "Unknown years": unknown,
        "Percentage": 100 * qualifying / total if unknown == 0 else np.nan,
    }


def _seasonal_rises(levels: pd.Series) -> pd.Series:
    seasonal = levels.where(levels.index.month.isin(GROWING_MONTHS))
    return seasonal.groupby(levels.index.year).diff()


def _rise_outcomes(frame: pd.DataFrame, output: object = None) -> np.ndarray:
    # Rises are NaN for May (not compared with April); NaN passes by design.
    rises = _seasonal_rises(frame.iloc[:, 0])
    passes = rises.isna() | rises.le(MAX_RISE_M) | np.isclose(rises, MAX_RISE_M, rtol=0, atol=1e-12)
    return passes.astype(float).to_numpy(dtype=float)


def _components(floor_ft: float) -> tuple[Component, Component]:
    floor_m = round(floor_ft * FT_TO_M, 4)
    winter = Component(
        name="winter_survival",
        characteristics=[
            magnitude_parser([">=", floor_m + 0.5], order=1)._replace(name="minimum_depth")
        ],
        is_success_pattern=True,
    )
    growing = Component(
        name="growing_season_habitat",
        characteristics=[
            timing_parser(list(GROWING_DOY), order=1)._replace(name="growing_season"),
            magnitude_parser([floor_m + 1.0, floor_m + 3.0], order=2)._replace(name="magnitude"),
            Characteristic(
                name="monthly_rise", fx=_rise_outcomes, type=CharacteristicType.RATE_OF_CHANGE
            ),
        ],
        is_success_pattern=True,
    )
    return winter, growing


def run_floor(floor_ft: float, levels_csv: Path = LEVELS_CSV) -> pd.DataFrame:
    """Per-scenario pondweed results for one floor (ft IGLD85), indexed (Component, Scenario)."""
    ts = Timeseries.from_csv(str(levels_csv), first_dowy=1, date_format="%Y-%m-%d")
    scenarios = list(ts.data.columns[:-1])
    if not np.isfinite(ts.data[scenarios].to_numpy(dtype=float)).all():
        raise ValueError("Missing or infinite lake levels cannot be evaluated.")
    winter, growing = _components(floor_ft)
    required = {winter.name: tuple(range(1, 13)), growing.name: GROWING_MONTHS}
    evaluated = evaluate_scenarios(ts, [winter, growing])
    rows = []
    for component in (winter, growing):
        for name, result in evaluated.by_component(component.name).items():
            annual = annual_verdicts(result.df[component.name], required[component.name])
            precip, temp = parse_scenario_name(name)
            rows.append(
                {
                    "Component": component.name,
                    "Scenario": name,
                    "Precipitation delta (%)": precip,
                    "Temperature delta (deg C)": temp,
                    **_annual_summary(annual),
                }
            )
    return pd.DataFrame(rows).set_index(["Component", "Scenario"])


def run_all(
    floors_ft: tuple[float, ...] = FLOORS_FT, levels_csv: Path = LEVELS_CSV
) -> pd.DataFrame:
    """Stack results for every floor with a `Floor (ft IGLD85)` column."""
    frames = [run_floor(f, levels_csv).assign(**{"Floor (ft IGLD85)": f}) for f in floors_ft]
    return pd.concat(frames).reset_index()


def main(root: Path = typer.Option(REPO_ROOT, help="Repository root.")) -> None:
    layout = Layout(root)
    out = habitat.reliability_dir(layout) / "pondweed_reliability.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    run_all(levels_csv=habitat.levels_csv(layout)).to_csv(out, index=False)
    habitat.refresh_reliability_readme(layout)
    typer.echo(f"Wrote {out}")


if __name__ == "__main__":
    typer.run(main)
