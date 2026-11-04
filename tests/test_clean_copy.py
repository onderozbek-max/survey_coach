"""Read-time copy cleanup must never change captured content or version identity."""
import json
from pathlib import Path

import pytest

from surveycoach import snapshot as snapshot_module
from surveycoach.snapshot import Page, Question, SurveySnapshot

CASES = json.loads((Path(__file__).parent / "fixtures/clean_copy_cases.json").read_text())


@pytest.mark.parametrize("raw,expected", CASES)
def test_clean_copy_cases(raw, expected):
    assert snapshot_module.clean_copy(raw) == expected


def halloween_snapshot():
    return SurveySnapshot.model_validate({"title": "Halloween", "pages": [
        {"id": "p0", "position": 0, "kind": "info",
         "text": "Welcome! Let us know how you celebrated. It takes 10 minutes.\n\n\n\nNext"},
        {"id": "p1", "position": 1, "kind": "question", "questions": [
            {"id": "q", "text": "Pick", "kind": "single_choice",
             "options": [{"id": "a", "label": "A"}]}]},
    ]})


def test_time_rewrite_never_appends_to_a_button_label():
    snapshot = halloween_snapshot()
    assert snapshot.intro_text == "Welcome! Let us know how you celebrated. It takes 10 minutes."


def test_page_copy_cleans_each_part_before_deduplicating_in_capture_order():
    page = Page(id="p0", position=0, kind="info", intro_text="Welcome!\n\nNext",
                text="Welcome!", questions=[
                    Question(id="i0", text="Welcome!\nContinue", kind="info"),
                    Question(id="i1", text="Details  \n\n\nMore\u00a0\nDone", kind="info"),
                    Question(id="i2", text="Next", kind="info"),
                    Question(id="q", text="Not page copy\nNext", kind="text_short"),
                ])
    assert SurveySnapshot.page_copy(page) == "Welcome! Details\n\nMore"


def test_copy_projection_preserves_raw_snapshot_and_precleanup_hashes():
    snapshot = halloween_snapshot()
    raw = snapshot.model_dump(mode="json")
    review_hash = snapshot.review_hash
    content_hash = snapshot.content_hash
    # Captured from base 308cace: identities remain based on raw capture, not clean copy.
    assert review_hash == "39a26a5bbe2168af793a7057b8de595a7ecb3da2cf711d3a96a26a8e6ce3f6be"
    assert content_hash == "0f124be939b89a9f533c10144f4beb95dfad362703f3850b0c3ebf0ff4d136da"

    assert snapshot.intro_text.endswith("10 minutes.")
    assert snapshot.page_role(snapshot.pages[0]) == "intro"
    assert snapshot.model_dump(mode="json") == raw
    assert snapshot.review_hash == review_hash
    assert snapshot.content_hash == content_hash
    assert SurveySnapshot.model_validate_json(snapshot.model_dump_json()).model_dump(mode="json") == raw

    cleaned_capture = snapshot.model_copy(deep=True)
    cleaned_capture.pages[0].text = snapshot.intro_text
    assert cleaned_capture.review_hash != review_hash
    assert cleaned_capture.content_hash != content_hash
