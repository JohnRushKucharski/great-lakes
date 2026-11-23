"""Tests for the shared habitat case-study paths and run record."""
from great_lakes import habitat
from great_lakes.paths import Layout


def test_paths_are_under_the_habitat_case_study(tmp_path):
    layout = Layout(tmp_path)
    base = tmp_path / "case-studies" / "long-tail-point" / "habitat"

    assert habitat.levels_csv(layout) == tmp_path / "data" / "avg" / "michiganhuron_avg.csv"
    assert habitat.survey_xlsx(layout) == base / "inputs" / "Compiled PI Survey Data_jo.xlsx"
    assert habitat.jenny_maps_dir(layout) == base / "inputs" / "jenny_maps"
    assert habitat.figures_dir(layout) == base / "outputs" / "figures"
    assert habitat.reliability_dir(layout) == base / "outputs" / "reliability"


def test_record_outputs_lists_every_file_so_several_scripts_can_share_a_folder(tmp_path):
    layout = Layout(tmp_path)
    folder = habitat.figures_dir(layout)
    folder.mkdir(parents=True)
    (folder / "F1.png").write_bytes(b"1")
    (folder / "F3.png").write_bytes(b"3")

    readme = habitat.record_outputs(folder, "Habitat memo figures", [], "F<n>.png", layout)
    text = readme.read_text(encoding="utf-8")

    assert readme == folder / "README.txt"
    assert "F1.png" in text and "F3.png" in text
    assert "(none found)" in text

    (folder / "F5.png").write_bytes(b"5")
    habitat.record_outputs(folder, "Habitat memo figures", [], "F<n>.png", layout)
    assert "F5.png" in readme.read_text(encoding="utf-8")
