"""Musky habitat runs across floor elevations 573-579 ft (juvenile, spawning, recruitment).

Same criteria as the reviewed `methods/musky_habitat.ipynb` notebook, run headless. Per scenario:
share of complete years meeting each stage (recruitment: share of rolling 5-year windows
with >= 3 recruitment years). Floors are ft IGLD85; lake levels are m IGLD85 (units
converted here only, no datum change).

Needs hydropattern >= 0.3 (e.g. PYTHONPATH=..\\hydropattern).
Usage: uv run python case-studies/long-tail-point/habitat/scripts/musky_runs.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import typer
from hydropattern.parsers import duration_parser, magnitude_parser, timing_parser
from hydropattern.patterns import Component
from hydropattern.scenario_grid import parse_scenario_name
from hydropattern.scenarios import evaluate_scenarios
from hydropattern.timeseries import Timeseries
from pondweed_runs import annual_verdicts

from great_lakes import habitat
from great_lakes.paths import REPO_ROOT, Layout

LEVELS_CSV = habitat.levels_csv(Layout())
FLOORS_FT = tuple(float(f) for f in range(573, 580))
FT_TO_M = 0.3048
EPS = 1e-9  # float tolerance only; levels have 0.01 m resolution

JUVENILE_MIN_DEPTH_M = 0.3  # strictly deeper than
SPAWNING_DEPTH_M = (0.3, 1.5)
RECRUITMENT_DEPTH_M = (0.3, 0.6)
JUVENILE_MONTHS = (5, 6, 7, 8)
EARLY_MONTHS = (5, 6)
JUVENILE_DOY = (121, 243)  # May 1 - Aug 31 on hydropattern's 365-day calendar
EARLY_DOY = (121, 181)  # May 1 - Jun 30
WINDOW_YEARS, WINDOW_REQUIRED = 5, 3

REQUIRED_MONTHS = {
    "juvenile_habitat": JUVENILE_MONTHS,
    "spawning_zones": EARLY_MONTHS,
    "recruitment_zones": EARLY_MONTHS,
}


def window_verdicts(
    annual: pd.Series, window: int = WINDOW_YEARS, required: int = WINDOW_REQUIRED
) -> pd.Series:
    """Rolling windows of consecutive years: 1 if >= `required` successes; partial ones skipped."""
    if len(annual) < window or not np.all(np.diff(annual.index) == 1):
        raise ValueError("Rolling windows need consecutive complete years covering a full window.")
    verdicts = {}
    for start in range(len(annual) - window + 1):
        chunk = annual.iloc[start : start + window]
        successes, unknown = int(chunk.eq(1).sum()), int(chunk.isna().sum())
        verdicts[int(chunk.index[0])] = (
            1.0 if successes >= required else 0.0 if successes + unknown < required else np.nan
        )
    return pd.Series(verdicts, name=annual.name, dtype=float).rename_axis("Window start year")


def _components(floor_ft: float) -> dict[str, Component]:
    floor_m = round(floor_ft * FT_TO_M, 4)

    def level(depth_m: float) -> float:
        return round(floor_m + depth_m, 4)

    def component(name: str, doy: tuple[int, int], magnitude: list, months: int) -> Component:
        return Component(
            name=name,
            characteristics=[
                timing_parser(list(doy), order=1)._replace(name="season"),
                magnitude_parser(magnitude, order=2)._replace(name="depth"),
                duration_parser([">=", months], order=3)._replace(name="season_duration"),
            ],
            is_success_pattern=True,
        )

    return {
        "juvenile_habitat": component(
            "juvenile_habitat",
            JUVENILE_DOY,
            [">", level(JUVENILE_MIN_DEPTH_M) + EPS],
            len(JUVENILE_MONTHS),
        ),
        "spawning_zones": component(
            "spawning_zones",
            EARLY_DOY,
            [level(SPAWNING_DEPTH_M[0]) - EPS, level(SPAWNING_DEPTH_M[1]) + EPS],
            len(EARLY_MONTHS),
        ),
        "recruitment_zones": component(
            "recruitment_zones",
            EARLY_DOY,
            [level(RECRUITMENT_DEPTH_M[0]) - EPS, level(RECRUITMENT_DEPTH_M[1]) + EPS],
            len(EARLY_MONTHS),
        ),
    }


def run_floor(floor_ft: float, levels_csv: Path = LEVELS_CSV) -> pd.DataFrame:
    """Per-scenario musky results for one floor (ft IGLD85), indexed (Component, Scenario)."""
    ts = Timeseries.from_csv(str(levels_csv), first_dowy=1, date_format="%Y-%m-%d")
    scenarios = list(ts.data.columns[:-1])
    if not np.isfinite(ts.data[scenarios].to_numpy(dtype=float)).all():
        raise ValueError("Missing or infinite lake levels cannot be evaluated.")
    components = _components(floor_ft)
    evaluated = evaluate_scenarios(ts, list(components.values()))
    rows = []
    for key, months in REQUIRED_MONTHS.items():
        for name, result in evaluated.by_component(key).items():
            annual = annual_verdicts(result.df[key], months)
            scored = window_verdicts(annual) if key == "recruitment_zones" else annual
            total, unknown = len(scored), int(scored.isna().sum())
            successes = int(scored.eq(1).sum())
            precip, temp = parse_scenario_name(name)
            rows.append(
                {
                    "Component": key,
                    "Scenario": name,
                    "Precipitation delta (%)": precip,
                    "Temperature delta (deg C)": temp,
                    "Evaluated units": total,
                    "Qualifying": successes,
                    "Failed": int(scored.eq(0).sum()),
                    "Unknown": unknown,
                    "Percentage": 100 * successes / total if unknown == 0 else np.nan,
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
    out = habitat.reliability_dir(layout) / "musky_reliability.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    run_all(levels_csv=habitat.levels_csv(layout)).to_csv(out, index=False)
    habitat.refresh_reliability_readme(layout)
    typer.echo(f"Wrote {out}")


if __name__ == "__main__":
    typer.run(main)
