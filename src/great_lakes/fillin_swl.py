"""Fill in missing SWL scenarios for Great Lakes save points.

Each `data/clean/<lake>_swl.xlsx` workbook (see batch_run_swl.py / common_swl.py) has 5
of 17 possible precip/temp climate scenarios -- the **known scenarios** -- per save
point. This script estimates the water-level-vs-ARI curve for the remaining 12
**target scenarios**, via two methods depending on where they fall relative to the
known scenarios' (precip_delta, temp_delta) convex hull:

- **in-hull** (7 scenarios): Delaunay-linear (barycentric) interpolation -- the same
  technique climate_canvas uses for its own response-surface `--fillin` option.
- **out-of-hull** (5 scenarios): row-shift extrapolation, using each lake's average
  lake level (`<avg-lake>_avg.csv`) to shift a same-warming-row known-or-filled
  scenario's sheet by a single scalar -- see
  docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md for the math and
  the underlying physical assumption.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
import typer
from hydropattern.scenario_grid import parse_scenario_name  # type: ignore[import-untyped]
from scipy.spatial import (  # type: ignore[import-untyped]  # pylint: disable=no-name-in-module
    Delaunay,
)

from great_lakes import common_swl

parse_scenario_sheet_name = common_swl.parse_scenario_sheet_name

# All 17 precip/temp scenarios represented in the Great Lakes avg-level data (see
# data/clean/*_avg.csv column headers). Not a full rectangular grid -- some
# precip/temp combinations are missing entirely.
ALL_SCENARIO_SUFFIXES: tuple[str, ...] = (
    "_0_0", "_0_1.5", "_0_3", "_0_5", "_0_7",
    "_5_1.5", "_5_3", "_5_5", "_5_7",
    "_10_3", "_10_5", "_10_7",
    "_15_3", "_15_5", "_15_7",
    "_20_5", "_20_7",
)


def known_scenario_coords(sheet_names: Sequence[str]) -> dict[str, tuple[float, float]]:
    """Map each known-scenario sheet name to its (precip_delta, temp_delta) suffix.

    Sheets that don't match the `<label>-_<precip>_<temp>` naming convention are
    skipped. Returns {bare_suffix: (precip_delta, temp_delta)}, e.g.
    {"_0_0": (0.0, 0.0), "_5_1.5": (5.0, 1.5), ...}.
    """
    coords: dict[str, tuple[float, float]] = {}
    for name in sheet_names:
        suffix = parse_scenario_sheet_name(name)
        if suffix is None:
            continue
        parsed = parse_scenario_name(suffix)
        if parsed is None:
            continue
        coords[suffix] = parsed
    return coords


@dataclass
class TargetClassification:
    """The target (missing) scenarios, split by convex-hull membership.

    in_hull scenarios fall inside the convex hull of the known scenarios'
    (precip_delta, temp_delta) coordinates, so a Delaunay-linear fit can estimate
    them. out_of_hull scenarios fall outside it, so Delaunay-linear interpolation
    cannot (it never extrapolates) -- estimating those is a separate effort.
    """
    in_hull: list[str]
    out_of_hull: list[str]


def classify_target_scenarios(known_coords: dict[str, tuple[float, float]]
                              ) -> TargetClassification:
    """Split the target (non-known) scenarios into in-hull vs out-of-hull.

    known_coords is the {suffix: (precip_delta, temp_delta)} mapping produced by
    known_scenario_coords(). Builds a Delaunay triangulation over those known
    coordinates once, then checks each of the 17 scenarios in ALL_SCENARIO_SUFFIXES
    that isn't already a known scenario against that triangulation.
    """
    known_points = np.array(list(known_coords.values()))
    tri = Delaunay(known_points)
    in_hull: list[str] = []
    out_of_hull: list[str] = []
    for suffix in ALL_SCENARIO_SUFFIXES:
        if suffix in known_coords:
            continue
        point = np.array(parse_scenario_name(suffix))
        if tri.find_simplex(point) >= 0:
            in_hull.append(suffix)
        else:
            out_of_hull.append(suffix)
    return TargetClassification(in_hull=in_hull, out_of_hull=out_of_hull)


def build_barycentric_weights(known_coords: dict[str, tuple[float, float]],
                               target_suffixes: Sequence[str]
                              ) -> dict[str, tuple[tuple[str, str, str], np.ndarray]]:
    """Precompute each target scenario's enclosing triangle + barycentric weights.

    Builds the Delaunay triangulation over the known scenarios' (precip, temp)
    coordinates once, then for each target scenario suffix looks up which 3 known
    scenarios bound its enclosing triangle and the barycentric weights for those 3
    vertices (weights sum to 1). This lets the actual per-save-point/per-ARI fill be a
    plain weighted sum of 3 known values, computed once per target scenario rather than
    re-triangulating per cell.

    Raises ValueError if a target suffix's coordinates fall outside the known
    scenarios' convex hull (Delaunay-linear interpolation cannot extrapolate there --
    callers should only pass in-hull target suffixes, e.g. from
    classify_target_scenarios().in_hull).

    Returns {target_suffix: ((known_a, known_b, known_c), weights)} where weights is a
    length-3 array aligned with (known_a, known_b, known_c).
    """
    labels = list(known_coords.keys())
    points = np.array([known_coords[label] for label in labels])
    tri = Delaunay(points)
    weights: dict[str, tuple[tuple[str, str, str], np.ndarray]] = {}
    for suffix in target_suffixes:
        xy = np.array(parse_scenario_name(suffix))
        simplex_index = tri.find_simplex(xy)
        if simplex_index < 0:
            raise ValueError(
                f"{suffix!r} is not inside the known scenarios' convex hull; it cannot "
                "be filled via Delaunay-linear interpolation."
            )
        vertex_indices = tri.simplices[simplex_index]
        transform = tri.transform[simplex_index]
        bary_partial = transform[:2].dot(xy - transform[2])
        bary = np.array([bary_partial[0], bary_partial[1], 1.0 - bary_partial.sum()])
        vertex_labels = (labels[vertex_indices[0]], labels[vertex_indices[1]],
                         labels[vertex_indices[2]])
        weights[suffix] = (vertex_labels, bary)
    return weights


def fill_scenarios(known_frames: dict[str, pd.DataFrame],
                    weights: dict[str, tuple[tuple[str, str, str], np.ndarray]]
                   ) -> dict[str, pd.DataFrame]:
    """Compute filled DataFrames for each target scenario from a weighted sum of knowns.

    known_frames: {known_suffix: save-point DataFrame}, one DataFrame per known
    scenario, each with `ID`/`lat`/`lon` columns (see common_swl.NON_ARI_COLUMNS) plus
    one column per ARI. Rows must be aligned across all known frames (same save points,
    same order).

    weights: as returned by build_barycentric_weights() -- {target_suffix:
    ((known_a, known_b, known_c), weights)}.

    Returns {"filled-" + target_suffix: DataFrame}, one DataFrame per target scenario,
    with the same ID/lat/lon columns (copied from the first of the target's 3 known
    vertex frames) and each ARI column set to the barycentric-weighted sum of the 3
    known frames' values for that ARI, rounded to 2 decimals to match known-scenario
    precision. NaN known values propagate naturally through the weighted sum.
    """
    filled: dict[str, pd.DataFrame] = {}
    for suffix, (vertex_labels, vertex_weights) in weights.items():
        vertex_frames = [known_frames[label] for label in vertex_labels]
        ari_columns = [c for c in vertex_frames[0].columns if c not in common_swl.NON_ARI_COLUMNS]

        non_ari_columns = [c for c in vertex_frames[0].columns if c in common_swl.NON_ARI_COLUMNS]
        result = vertex_frames[0][non_ari_columns].copy()
        for column in ari_columns:
            weighted_sum = sum(
                frame[column] * weight for frame, weight in zip(vertex_frames, vertex_weights)
            )
            result[column] = weighted_sum.round(2)
        filled[f"filled-{suffix}"] = result
    return filled


def select_anchor_scenario(target_suffix: str, resolved_suffixes: Iterable[str]) -> str:
    """Pick the anchor scenario for an out-of-hull target, for row-shift extrapolation.

    The anchor is whichever scenario in resolved_suffixes (known or already
    Delaunay-filled) shares target_suffix's temp_delta (same "warming row") and is
    nearest to it by precip_delta distance -- see
    docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md.

    Raises ValueError if no resolved scenario shares target_suffix's warming row.
    """
    target_precip, target_temp = parse_scenario_name(target_suffix)  # type: ignore[misc]
    same_row = [suffix for suffix in resolved_suffixes
                if parse_scenario_name(suffix)[1] == target_temp]  # type: ignore[index]
    if not same_row:
        raise ValueError(
            f"{target_suffix!r} has no known or filled scenario on its warming row "
            f"(temp_delta={target_temp}); row-shift extrapolation needs at least one "
            "resolved anchor on the same row."
        )
    def _precip_distance(suffix: str) -> float:
        return abs(parse_scenario_name(suffix)[0] - target_precip)  # type: ignore[index]

    return min(same_row, key=_precip_distance)


def extrapolate_scenarios(resolved_frames: dict[str, pd.DataFrame],
                           avg_means: dict[str, float],
                           target_suffixes: Sequence[str]) -> dict[str, pd.DataFrame]:
    """Compute extrapolated DataFrames for out-of-hull targets via row-shift extrapolation.

    resolved_frames: {suffix: save-point DataFrame}, one DataFrame per known-or-filled
    scenario (bare suffix keys, not sheet names), each with `ID`/`lat`/`lon` columns
    plus one column per ARI.

    avg_means: {suffix: average lake level}, as returned by
    common_swl.read_avg_scenario_means() -- must cover every suffix in resolved_frames
    plus every suffix in target_suffixes.

    For each target suffix, picks its anchor via select_anchor_scenario() (over
    resolved_frames.keys()), then shifts every ARI column of the anchor's frame by the
    single scalar avg_means[target] - avg_means[anchor] (see
    docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md for the math),
    rounded to 2 decimals to match known-scenario precision.

    Returns {"extrapolated-" + target_suffix: DataFrame}.
    """
    extrapolated: dict[str, pd.DataFrame] = {}
    for suffix in target_suffixes:
        anchor = select_anchor_scenario(suffix, resolved_frames.keys())
        anchor_frame = resolved_frames[anchor]
        delta = avg_means[suffix] - avg_means[anchor]

        ari_columns = [c for c in anchor_frame.columns if c not in common_swl.NON_ARI_COLUMNS]
        non_ari_columns = [c for c in anchor_frame.columns if c in common_swl.NON_ARI_COLUMNS]
        result = anchor_frame[non_ari_columns].copy()
        for column in ari_columns:
            result[column] = (anchor_frame[column] + delta).round(2)
        extrapolated[f"extrapolated-{suffix}"] = result
    return extrapolated


def resolve_default_output_dir(data_dir: Path, extrapolate: bool) -> Path:
    """Default output_dir when the CLI's output_dir argument is omitted.

    A sibling of data_dir (normally data/clean): data/extrapolated when extrapolate is
    True (17 sheets per lake -- Stage 2 row-shift extrapolation ran), or data/filled
    when False (12 sheets per lake -- Stage 2 skipped). Keeps the two possible output
    shapes from silently overwriting each other under the same directory name.
    """
    return data_dir.parent / ("extrapolated" if extrapolate else "filled")


def write_filled_workbook(known_sheets: dict[str, pd.DataFrame],
                           filled_frames: dict[str, pd.DataFrame],
                           output_path: Path, overwrite: bool = False,
                           extrapolated_frames: dict[str, pd.DataFrame] | None = None) -> None:
    """Write a self-contained `<lake>_swl.xlsx` with known + filled + extrapolated sheets.

    known_sheets: {sheet_name: DataFrame} straight from common_swl.load_lake_sheets()
    (full sheet names, e.g. "baseline-_0_0"), copied through as-is.
    filled_frames: {"filled-<suffix>": DataFrame} as returned by fill_scenarios().
    extrapolated_frames: {"extrapolated-<suffix>": DataFrame} as returned by
    extrapolate_scenarios(), or None (default) to omit extrapolated sheets entirely.

    Refuses to overwrite an existing file at output_path unless overwrite=True (raises
    FileExistsError, writes nothing) -- there is no numeric-suffix fallback.

    Uses the xlsxwriter engine: at ~15-16MB / ~3.3M cells per lake, it writes
    noticeably faster than the default openpyxl engine.
    """
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"{output_path} already exists; pass overwrite=True to replace it."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_sheets = {**known_sheets, **filled_frames, **(extrapolated_frames or {})}
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        for sheet_name, df in all_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)


app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def main(
    data_dir: Path = typer.Argument(
        ..., help="Directory holding the clean <lake>_swl.xlsx workbooks and "
                   "<avg-lake>_avg.csv files."),
    output_dir: Optional[Path] = typer.Argument(
        None, help="Directory to write the filled <lake>_swl.xlsx workbooks to. "
                    "Defaults to a sibling of data_dir: data/extrapolated when "
                    "--extrapolate (the default), or data/filled with --no-extrapolate."),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace existing output files instead of refusing to run."),
    extrapolate: bool = typer.Option(
        True, "--extrapolate/--no-extrapolate",
        help="Also estimate the 5 out-of-hull scenarios via row-shift extrapolation "
             "(see docs/adr/0001-row-shift-extrapolation-for-out-of-hull-scenarios.md). "
             "On by default."),
) -> None:
    """Fill in the 12 target scenarios for all 4 Great Lakes swl workbooks.

    Reads each <lake>_swl.xlsx under data_dir, Delaunay-linear-interpolates the 7
    in-hull target scenarios, then (unless --no-extrapolate is passed) row-shift-
    extrapolates the remaining 5 out-of-hull target scenarios using each lake's
    <avg-lake>_avg.csv average lake levels, and writes a self-contained workbook --
    17 sheets by default (5 known + 7 filled + 5 extrapolated), or 12 sheets with
    --no-extrapolate (5 known + 7 filled only) -- to output_dir.

    Refuses to run (raises, writes nothing) if any output file already exists and
    --overwrite was not passed -- checked up front for all 4 lakes before writing
    anything, so a run either fully succeeds or makes no changes.
    """
    if output_dir is None:
        output_dir = resolve_default_output_dir(data_dir, extrapolate)

    lakes = list(common_swl.LAKE_SWL_FILENAMES)

    if not overwrite:
        existing = [
            output_path for lake in lakes
            if (output_path := common_swl.resolve_lake_swl_path(lake, output_dir)).exists()
        ]
        if existing:
            existing_list = ", ".join(str(p) for p in existing)
            raise typer.BadParameter(
                f"Output file(s) already exist and --overwrite was not passed: {existing_list}"
            )

    lake_sheets = {
        lake: pd.read_excel(common_swl.resolve_lake_swl_path(lake, data_dir), sheet_name=None)
        for lake in lakes
    }
    total_rows = sum(len(next(iter(sheets.values()))) for sheets in lake_sheets.values())

    with typer.progressbar(length=total_rows, label="Filling SWL scenarios") as progress:
        for lake in lakes:
            sheets = lake_sheets[lake]
            known_coords = known_scenario_coords(list(sheets.keys()))
            classification = classify_target_scenarios(known_coords)
            weights = build_barycentric_weights(known_coords, classification.in_hull)

            known_frames_by_suffix = {
                suffix: df
                for sheet_name, df in sheets.items()
                if (suffix := common_swl.parse_scenario_sheet_name(sheet_name)) in known_coords
            }
            filled_frames = fill_scenarios(known_frames_by_suffix, weights)

            extrapolated_frames: dict[str, pd.DataFrame] = {}
            if extrapolate:
                resolved_frames = {
                    **known_frames_by_suffix,
                    **{suffix.removeprefix("filled-"): df for suffix, df in filled_frames.items()},
                }
                avg_means = common_swl.read_avg_scenario_means(lake, data_dir)
                extrapolated_frames = extrapolate_scenarios(
                    resolved_frames, avg_means, classification.out_of_hull
                )

            output_path = common_swl.resolve_lake_swl_path(lake, output_dir)
            write_filled_workbook(sheets, filled_frames, output_path, overwrite=overwrite,
                                   extrapolated_frames=extrapolated_frames)

            progress.update(len(next(iter(sheets.values()))))


if __name__ == "__main__":
    app()
