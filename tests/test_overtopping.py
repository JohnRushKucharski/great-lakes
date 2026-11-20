"""Tests for overtopping case-study report helpers."""

from great_lakes import overtopping


def test_presentation_note_names_runup_allowance_only_when_added():
    assert overtopping.presentation_note(0.0).endswith("SWL excludes runup.")
    note = overtopping.presentation_note(2.0)
    assert note.endswith("SWL plus 2 ft runup allowance.")
    assert "excludes runup" not in note
