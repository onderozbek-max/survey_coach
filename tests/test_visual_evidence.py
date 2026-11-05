"""Definition wording is not rendered evidence: unrendered media is unverified, never N/A or passed."""
import json

import pytest

from surveycoach.reader.definition import adapt_definition, apply_definition
from surveycoach.reader.models import Coverage, ReadResult
from surveycoach.review import MEDIA_CRITERIA, run_review
from surveycoach.snapshot import Media, Page, Question, SurveySnapshot
from tests.builders import intro, page, question, survey, thank_you

IMG = '<img src="synthetic.png" alt="Important stimulus">'


def definition(*page_ids, prompt="Choose one"):
    pages = [{"id": pid, "questions": [{
        "cid": f"q-{pid}", "text": {"en_US": f"{prompt} {IMG}" if pid == page_ids[0] else prompt},
        "question_type": "radio", "answers": [{"id": f"a-{pid}-1", "text": {"en_US": "Yes"}},
                                              {"id": f"a-{pid}-2", "text": {"en_US": "No"}}]}]}
             for pid in page_ids]
    return adapt_definition({"title": "Synthetic", "data": {"pages": pages}})


def applied(parsed, tmp_path, rendered_pages=()):
    result = ReadResult(snapshot=SurveySnapshot(title="", pages=list(rendered_pages)),
                        coverage=Coverage(), capture_dir=tmp_path)
    apply_definition(result, parsed)
    return result


def rendered(pid, *, media=()):
    return Page(id=pid, position=0, kind="question", media=list(media),
                questions=[Question(id=f"q-{pid}", text="Choose one", kind="single_choice")])


def test_definition_only_pages_are_marked_unrendered(tmp_path):
    result = applied(definition("p1", "p2"), tmp_path)
    assert [p.visual_evidence for p in result.snapshot.pages] == ["definition_only", "definition_only"]
    assert result.coverage.visual_media_verified is False


def test_pages_merged_by_explicit_ids_become_rendered(tmp_path):
    result = applied(definition("p1", "p2"), tmp_path, [rendered("p1")])
    assert [p.visual_evidence for p in result.snapshot.pages] == ["rendered", "definition_only"]
    assert result.coverage.visual_media_verified is False


def test_media_is_verified_only_when_every_defined_page_was_rendered(tmp_path):
    result = applied(definition("p1"), tmp_path, [rendered("p1")])
    assert result.coverage.visual_media_verified is True


def test_embedded_media_in_definition_wording_is_declared_not_invented(tmp_path):
    result = applied(definition("p1", "p2"), tmp_path)
    first, second = result.snapshot.pages
    assert first.declared_media == 1 and second.declared_media == 0
    assert first.media == [] and first.questions[0].media == []   # no fabricated loading/dimensions


def test_declared_media_survives_a_snapshot_round_trip(tmp_path):
    snapshot = applied(definition("p1"), tmp_path).snapshot
    restored = SurveySnapshot.model_validate(json.loads(snapshot.model_dump_json()))
    assert restored.pages[0].declared_media == 1
    assert restored.pages[0].visual_evidence == "definition_only"


@pytest.mark.parametrize("criterion", MEDIA_CRITERIA)
def test_definition_only_review_leaves_every_image_check_unassessed(tmp_path, criterion):
    review = run_review(applied(definition("p1", "p2"), tmp_path).snapshot)
    result = review.results[criterion]
    assert result.assessed is False
    assert result.fraction is None


def test_unverified_images_are_unchecked_and_block_a_clean_blocker_pass(tmp_path):
    review = run_review(applied(definition("p1"), tmp_path).snapshot)
    assert review.scorecard.pending_blockers and "B7" in review.scorecard.pending_blockers
    assert review.unchecked


def test_partially_rendered_definition_still_withholds_image_checks(tmp_path):
    review = run_review(applied(definition("p1", "p2"), tmp_path, [rendered("p1")]).snapshot)
    assert review.results["B7"].assessed is False


def test_rendered_image_free_survey_still_passes_image_checks():
    review = run_review(survey(intro(), page(1, question()), thank_you()))
    assert review.results["B7"].assessed is True
    assert review.results["7.2"].assessed is True and review.results["7.2"].applies is False


def test_rendered_media_findings_survive_the_withholding(tmp_path):
    broken = rendered("p1", media=[Media(element_id="hero", loaded=False)])
    review = run_review(applied(definition("p1", "p2"), tmp_path, [broken]).snapshot)
    assert review.results["B7"].assessed is False
    assert any(f.criterion_id == "B7" for f in review.findings)


def test_default_provenance_does_not_change_legacy_hashes():
    snapshot = survey(intro(), page(1, question()), thank_you())
    legacy = json.loads(snapshot.model_dump_json())
    for encoded in legacy["pages"]:
        encoded.pop("visual_evidence", None)
        encoded.pop("declared_media", None)
    assert SurveySnapshot.model_validate(legacy).review_hash == snapshot.review_hash


def test_unrendered_wording_is_different_evidence_from_a_rendered_read():
    base = survey(intro(), page(1, question()), thank_you())
    other = base.model_copy(deep=True)
    other.pages[1].visual_evidence = "definition_only"
    assert other.review_hash != base.review_hash
    assert other.content_hash == base.content_hash
