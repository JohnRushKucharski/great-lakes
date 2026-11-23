"""Shared entry logic of the assess-{avg,swl}-resources scripts."""
import dataclasses
from pathlib import Path
from typing import Literal

from great_lakes.batch import avg, swl, template_avg, template_swl
from great_lakes.paths import Layout

Kind = Literal["avg", "swl"]


def build_template(kind: Kind, layout: Layout) -> Path:
    """Write the blank resources+config template for `kind` to its inputs/templates folder."""
    path = layout.assess_template(kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    builder = template_avg if kind == "avg" else template_swl
    return builder.build_template(path)


def assess_resources(
    kind: Kind,
    layout: Layout,
    resources_path: Path | None = None,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
) -> int:
    """Run every row of a resources workbook; returns 0 if all rows succeeded, else 1.

    Defaults: the shipped template, the avg or complete swl data product, and (for the
    shipped template only) the workflow's `outputs/` folder. A workbook given explicitly
    keeps its own `output_directory` unless `output_dir` overrides it.
    """
    module = avg if kind == "avg" else swl
    path = resources_path or layout.assess_template(kind)
    config = module.read_config_sheet(path)
    if output_dir is None and resources_path is None:
        output_dir = layout.assess_outputs(kind)
    if output_dir is not None:
        config = dataclasses.replace(config, output_directory=str(output_dir))
    summary = module.run_batch(
        path, data_dir or layout.assess_data_dir(kind), config, workspace_root=layout.root)
    print(module.format_summary(summary))
    return 1 if summary.failed else 0
