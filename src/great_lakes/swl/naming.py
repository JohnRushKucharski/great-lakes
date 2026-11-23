"""Long Tail Point swl naming: runup allowances, output filename stems, plot titles."""

# Wave-runup allowance, in feet, per component_name code (GLOSSARY.md "Runup allowance").
RUNUP_FT_BY_COMPONENT: dict[str, float] = {
    "base": 0.0,
    "run2": 2.0,
    "run25": 2.5,
    "run3": 3.0,
}

# Maps build_resource_outputs' plot kinds to the "type" label in build_plot_title.
PLOT_TITLE_TYPE_LABELS: dict[str, str] = {
    "primary": "Overtopping Frequency",
    "equivalent_elevation": "Elevation Equivalents",
    "elevation_delta": "Elevation Delta",
}


def _runup_ft(component_name: str) -> float:
    if component_name not in RUNUP_FT_BY_COMPONENT:
        raise ValueError(
            f"Unknown runup component_name {component_name!r}; expected one of "
            f"{sorted(RUNUP_FT_BY_COMPONENT)}."
        )
    return RUNUP_FT_BY_COMPONENT[component_name]


def _format_ft_fixed2(value: float) -> str:
    """Two decimals, "." -> "d" (filename-safe): 586.4749 -> "586d47"."""
    return f"{value:.2f}".replace(".", "d")


def _format_ft_trim(value: float) -> str:
    """Minimal decimals, "." -> "d", none for whole numbers: 2.5 -> "2d5", 3.0 -> "3"."""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    if text in ("", "-"):
        text = "0"
    return text.replace(".", "d")


def output_file_stem(magnitude_ft: float, component_name: str, save_point_id: object) -> str:
    """Output filename stem "<elevation>ft_plus<runup>ft-runup_savepoint<id>".

    magnitude_ft is the row's magnitude in ft, NAVD88 (2 decimals); the runup comes from
    RUNUP_FT_BY_COMPONENT. Raises ValueError for an unknown component_name. This is only
    a filename concern; ResourceSpec.qualified_name stays the internal identifier.
    """
    runup_ft = _runup_ft(component_name)
    elevation_label = _format_ft_fixed2(magnitude_ft)
    runup_label = _format_ft_trim(runup_ft)
    return f"{elevation_label}ft_plus{runup_label}ft-runup_savepoint{save_point_id}"


def output_file_stem_savepoint_elevation_runup(
    magnitude_ft: float, component_name: str, save_point_id: object
) -> str:
    """Output filename stem "<save point>_<elevation>_<runup>": the combined elevation
    (magnitude_ft + runup) then the runup alone, each with 2 decimals and "d" for ".".
    Raises ValueError for an unknown component_name.
    """
    runup_ft = _runup_ft(component_name)
    elevation_label = _format_ft_fixed2(magnitude_ft + runup_ft)
    runup_label = _format_ft_fixed2(runup_ft)
    return f"{save_point_id}_{elevation_label}_{runup_label}"


def build_plot_title(
    plot_kind: str, magnitude_ft: float, component_name: str, save_point_id: object,
    baseline_ari: float | None = None,
) -> str:
    """Plot title for one swl resource's response-surface plot.

        Longtail Point <type>
        elevation: <magnitude + runup> ft (NAVD88), runup: <runup> ft
        [baseline ARI: <baseline_ari> yr]
        save point: <save_point_id>

    plot_kind is a PLOT_TITLE_TYPE_LABELS key. The baseline ARI line appears only for
    "equivalent_elevation"/"elevation_delta" when baseline_ari is given. magnitude_ft is in
    ft, NAVD88. Raises ValueError for an unknown plot_kind or component_name.
    """
    if plot_kind not in PLOT_TITLE_TYPE_LABELS:
        raise ValueError(
            f"Unknown plot_kind {plot_kind!r}; expected one of "
            f"{sorted(PLOT_TITLE_TYPE_LABELS)}."
        )
    runup_ft = _runup_ft(component_name)
    elevation_ft = magnitude_ft + runup_ft
    type_label = PLOT_TITLE_TYPE_LABELS[plot_kind]
    line1 = f"Longtail Point {type_label}"
    line2 = f"elevation: {elevation_ft:g} ft (NAVD88), runup: {runup_ft:g} ft"
    save_point_line = f"save point: {save_point_id}"
    if plot_kind in ("equivalent_elevation", "elevation_delta") and baseline_ari is not None:
        baseline_ari_line = f"baseline ARI: {baseline_ari:g} yr"
        return f"{line1}\n{line2}\n{baseline_ari_line}\n{save_point_line}"
    return f"{line1}\n{line2}\n{save_point_line}"


def build_threshold_ari_title(threshold_ari: float, save_point_id: object) -> str:
    """Title for one save point's threshold-ARI elevation plot (3 lines: type, ARI,
    save point). No elevation/runup line: the plot is shared by all rows at a save point.
    """
    return (
        "Longtail Point Threshold ARI Elevation\n"
        f"ARI: {threshold_ari:g} yr\n"
        f"save point: {save_point_id}"
    )


# One section body per filename style that has a pattern worth documenting.
_NAMING_SCHEME_README_BODIES: dict[str, str] = {
    "elevation_runup_savepoint": (
        "Output filename pattern: <elevation>ft_plus<runup>ft-runup_savepoint<save "
        "point ID>...\n\n"
        "  elevation - the resource's magnitude value, converted to feet, NAVD88 "
        "datum. Always shown with exactly 2 decimals, with \"d\" standing in for "
        "the decimal point (filenames can't contain \".\" safely on every "
        "platform), e.g. 586d47 means 586.47 ft.\n"
        "  runup     - the wave-runup allowance for this row's component, in feet, "
        "NAVD88 datum. Shown with only as many decimals as needed (no trailing "
        "zero), \"d\" for the decimal point, e.g. 2d5 means 2.5 ft.\n"
        "  save point ID - the save point identifier the row was evaluated at.\n"
    ),
    "savepoint_elevation_runup": (
        "Output filename pattern: <save point ID>_<elevation>_<runup>...\n\n"
        "  save point ID - the save point identifier the row was evaluated at.\n"
        "  elevation - the actual crest elevation being evaluated: the resource's "
        "magnitude value plus its runup allowance (both converted to feet, NAVD88 "
        "datum), combined. Always shown with exactly 2 decimals, with \"d\" "
        "standing in for the decimal point (filenames can't contain \".\" safely "
        "on every platform), e.g. 585d50 means 585.50 ft.\n"
        "  runup     - the wave-runup allowance alone, in feet, NAVD88 datum, also "
        "with exactly 2 decimals and \"d\" for the decimal point, e.g. 2d50 means "
        "2.50 ft.\n"
    ),
}


def naming_scheme_readme_text(filename_style: str) -> str:
    """Plain-text README content explaining one filename_style's naming scheme.

    Raises ValueError for a style with no documented naming convention.
    """
    if filename_style not in _NAMING_SCHEME_README_BODIES:
        raise ValueError(
            f"Unknown filename_style {filename_style!r} for a naming-scheme README; "
            f"expected one of {sorted(_NAMING_SCHEME_README_BODIES)}."
        )
    header = "Output filename naming scheme for this directory\n" + "=" * 50 + "\n\n"
    return header + _NAMING_SCHEME_README_BODIES[filename_style]
