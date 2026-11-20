"""Long Tail Point overtopping case study: design-elevation coverage and the ARI surface figure.

The memo figure set also uses `avg_scenario_stats` (F2, F3, T2) and `swl_method_quality`
(B1, LOO); `run` writes all of them.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from great_lakes import avg_scenario_stats, swl_method_quality
from great_lakes.scenario_grid import (
    WARMING_SCENARIOS,
    draw_scenario_grid,
    load_scenario_sheets,
    save_grid_csv,
    scenario_level_ft,
)
from great_lakes.swl import complete as swl_complete

SAVE_POINT_ID = swl_method_quality.SAVE_POINT_ID
PRIMARY_ARI = swl_method_quality.PRIMARY_ARI
RUNUP_ALLOWANCES_FT = (0.0, 2.0, 2.5, 3.0)
DESIGN_ELEVATIONS_FT = (584.0, 586.0)
REPORT_OUTPUT_NAMES = (
    "4999_ari15_elevation.csv",
    "4999_ari15_elevation.png",
    "4999_ari15_p2d00runup.csv",
    "4999_ari15_p2d00runup.png",
    "B1_known_residuals.csv",
    "B1_regression_predictions.csv",
    "B1_swl_avg_regression.png",
    "F2_scenario_avg_change.csv",
    "F2_scenario_avg_change.png",
    "F3_annual_high_years.csv",
    "F3_avg_persistence.png",
    "F3_persistence_summary.csv",
    "LOO_interpolation.csv",
    "LOO_row_shift.csv",
    "T1_design_coverage.csv",
    "T2_poisson_examples.csv",
)


def run(
    avg_csv: Path,
    swl_path: Path,
    output_dir: Path,
    save_point_id: int = SAVE_POINT_ID,
    ari: float = PRIMARY_ARI,
) -> list[Path]:
    """Write the memo figures and tables from the avg csv and the complete swl workbook."""
    output_dir.mkdir(parents=True, exist_ok=True)
    avg_scenario_stats.run(avg_csv, output_dir)
    swl_method_quality.run(avg_csv, swl_path, output_dir, save_point_id, ari)
    thresholds = write_design_coverage(
        load_scenario_sheets(swl_path), output_dir, save_point_id, ari)
    write_presentation_figures(thresholds, output_dir, save_point_id, ari)
    return [output_dir / name for name in REPORT_OUTPUT_NAMES]


def write_design_coverage(
    sheets: dict[str, pd.DataFrame],
    output_dir: Path,
    save_point_id: int = SAVE_POINT_ID,
    ari: float = PRIMARY_ARI,
) -> dict[str, float]:
    """T1: scenarios whose ARI storm water level (plus runup allowance) is at or below each
    design elevation. Returns the per-scenario levels (ft, NAVD88)."""
    thresholds = {
        suffix: scenario_level_ft(sheets[suffix], save_point_id, ari)
        for suffix in swl_complete.ALL_SCENARIO_SUFFIXES
    }
    rows = []
    for design in DESIGN_ELEVATIONS_FT:
        for runup in RUNUP_ALLOWANCES_FT:
            for temp, suffixes in WARMING_SCENARIOS.items():
                adjusted = {suffix: thresholds[suffix] + runup for suffix in suffixes}
                worst_suffix = max(adjusted, key=lambda suffix: adjusted[suffix])
                passes = sum(value <= design for value in adjusted.values())
                rows.append(
                    {
                        "design_elevation_ft_NAVD88": design,
                        "runup_allowance_ft": runup,
                        "temp_delta_c": temp,
                        "scenario_count": len(suffixes),
                        "coverage_count": passes,
                        "coverage_pct": 100 * passes / len(suffixes),
                        "worst_case_scenario": worst_suffix,
                        "worst_case_threshold_ft_NAVD88": adjusted[worst_suffix],
                        "margin_to_worst_case_ft": design - adjusted[worst_suffix],
                    }
                )
    pd.DataFrame(rows).to_csv(output_dir / "T1_design_coverage.csv", index=False)
    return thresholds


def write_presentation_figures(
    thresholds: dict[str, float],
    output_dir: Path,
    save_point_id: int = SAVE_POINT_ID,
    ari: float = PRIMARY_ARI,
) -> None:
    """F4: the ARI surface without and with a 2 ft runup allowance."""
    stem = f"{save_point_id}_ari{ari:g}"
    write_presentation_figure(
        thresholds,
        output_dir / f"{stem}_elevation.png",
        output_dir / f"{stem}_elevation.csv",
        save_point_id,
        ari,
    )
    write_presentation_figure(
        thresholds,
        output_dir / f"{stem}_p2d00runup.png",
        output_dir / f"{stem}_p2d00runup.csv",
        save_point_id,
        ari,
        elevation_offset_ft=2.0,
    )


def write_presentation_figure(
    values: dict[str, float],
    output_path: Path,
    csv_path: Path,
    save_point_id: int,
    ari: float,
    elevation_offset_ft: float = 0.0,
) -> Path:
    """Write a marked threshold-ARI surface with optional runup allowance."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_grid_csv(values, csv_path, offset_ft=elevation_offset_ft)
    fig, ax = plt.subplots(figsize=(10, 7))
    draw_scenario_grid(
        ax,
        {suffix: value + elevation_offset_ft for suffix, value in values.items()},
        f"{ari:g}-year ARI elevation (ft, NAVD88)",
        contour_levels=(584.0, 586.0),
        value_fontsize=10,
        blocky=True,
        threshold=values["_0_0"] + elevation_offset_ft,
    )
    runup_text = f" - +{elevation_offset_ft:g} ft runup" if elevation_offset_ft else ""
    ax.set_title(f"Save point {save_point_id} - {ari:g}-year ARI{runup_text}")
    fig.text(0.01, 0.01, presentation_note(elevation_offset_ft))
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def presentation_note(elevation_offset_ft: float) -> str:
    """In-figure footnote; says whether values include a runup allowance."""
    runup = (
        f"SWL plus {elevation_offset_ft:g} ft runup allowance."
        if elevation_offset_ft
        else "SWL excludes runup."
    )
    return (
        "Solid: 586 ft; dashed: 584 ft. Black outline: modeled; * interpolated; "
        f"** extrapolated. {runup}"
    )
