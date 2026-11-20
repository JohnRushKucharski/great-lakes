from pathlib import Path

from great_lakes.paths import REPO_ROOT, Layout


def test_default_layout_is_the_repo_root():
    assert Layout().root == REPO_ROOT
    assert (REPO_ROOT / "pyproject.toml").exists()


def test_layout_places_data_and_data_product_folders_under_root():
    layout = Layout(Path("r"))
    assert layout.raw == Path("r/data/raw")
    assert layout.avg == Path("r/data/avg")
    assert layout.swl_clean == Path("r/data/swl/clean")
    assert layout.swl_complete == Path("r/data/swl/complete")
    assert layout.avg_figures == Path("r/data/avg/figures")
    assert layout.swl_clean_figures == Path("r/data/swl/clean/figures")
    assert layout.swl_complete_figures == Path("r/data/swl/complete/figures")
    assert layout.swl_filled == Path("r/data-products/swl/outputs/filled")
    assert layout.avg_bulk_figures == Path("r/data-products/avg/outputs/figures")
    assert layout.swl_bulk_figures == Path("r/data-products/swl/outputs/figures")
    base = Path("r/data-products/swl/outputs/gates")
    assert layout.swl_fill_gate_outputs == base / "fill_vs_climate_canvas"
    assert layout.swl_ari_gate_outputs == base / "ari_curves"
    assert layout.swl_methods_outputs == Path("r/data-products/swl/outputs/methods")


def test_layout_places_analysis_workflows_under_root():
    layout = Layout(Path("r"))
    stats = Path("r/analyses/avg-statistics")
    assert layout.avg_statistics_outputs == stats / "outputs"
    for kind, folder in (("avg", "assess-avg-resources"), ("swl", "assess-swl-resources")):
        base = Path("r/analyses") / folder
        assert layout.assess_product(kind) == base
        template = base / "inputs" / "templates" / f"template_{kind}.xlsx"
        assert layout.assess_template(kind) == template
        assert layout.assess_outputs(kind) == base / "outputs"
    assert layout.assess_data_dir("avg") == layout.avg
    assert layout.assess_data_dir("swl") == layout.swl_complete


def test_layout_places_case_studies_under_root():
    layout = Layout(Path("r"))
    ltp = Path("r/case-studies/long-tail-point")
    assert layout.overtopping == ltp / "overtopping"
    assert layout.habitat == ltp / "habitat"
