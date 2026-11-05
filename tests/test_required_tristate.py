"""Requiredness is three-state: True, False, or None when the source did not say."""
import json

from surveycoach.reader.definition import adapt_definition
from surveycoach.reader.extract import extract_page
from surveycoach.snapshot import Page, Question, SurveySnapshot


def group(prompt="How was it?", required=False, **extra):
    return {"prompt": prompt, "kind": "text_long", "source_id": "q", "required": required,
            "items": [{"label": "", "row": ""}], **extra}


def read(*groups):
    return extract_page({"title": "t", "text": "x", "source_page_id": "p", "groups": list(groups),
                         "media": [], "screenout": False}, 0).questions


def test_question_without_requiredness_loads_as_unknown():
    assert Question.model_validate({"id": "q", "text": "Why?", "kind": "text_long"}).required is None


def test_saved_true_and_false_are_unchanged():
    for saved in (True, False):
        question = Question.model_validate({"id": "q", "text": "Why?", "kind": "text_long", "required": saved})
        assert question.required is saved


def test_unknown_requiredness_survives_a_snapshot_round_trip():
    page = Page(id="p", position=0, kind="question",
                questions=[Question(id="q", text="Why?", kind="text_long")])
    snapshot = SurveySnapshot(title="t", pages=[page])
    restored = SurveySnapshot.model_validate(json.loads(snapshot.model_dump_json()))
    assert restored.pages[0].questions[0].required is None
    assert restored.review_hash == snapshot.review_hash


def test_html_required_attribute_proves_required():
    assert read(group(required=True))[0].required is True


def test_missing_html_attribute_is_unknown_not_optional():
    assert read(group(required=False))[0].required is None


def test_visible_optional_label_on_its_own_line_proves_optional_and_is_not_wording():
    question = read(group("What else would you tell us?\nOptional"))[0]
    assert question.required is False
    assert question.text == "What else would you tell us?"


def test_visible_optional_flag_from_the_page_proves_optional():
    assert read(group(optional_label=True))[0].required is False


def test_optional_word_inside_a_sentence_is_not_a_label():
    question = read(group("Which of these extras is optional"))[0]
    assert question.required is None
    assert question.text == "Which of these extras is optional"


def test_conflicting_evidence_stays_unknown():
    assert read(group(required=True, optional_label=True))[0].required is None


def _definition(**question):
    base = {"cid": "q1", "text": {"en_US": "Why?"}, "question_type": "textarea"}
    page = {"id": "p1", "questions": [{**base, **question}]}
    return adapt_definition({"data": {"pages": [page]}}).snapshot.pages[0].questions[0]


def test_definition_required_field_is_used_when_present():
    assert _definition(required=True).required is True
    assert _definition(required=False).required is False


def test_definition_without_required_field_is_unknown():
    assert _definition().required is None


def test_definition_with_non_boolean_required_is_unknown():
    assert _definition(required="yes").required is None


def test_rendered_optional_label_fills_unknown_definition_requiredness(tmp_path):
    from surveycoach.reader.definition import apply_definition
    from surveycoach.reader.models import Coverage, ReadResult

    definition = adapt_definition({"data": {"pages": [{"id": "p1", "questions": [
        {"cid": "q1", "text": {"en_US": "Why?"}, "question_type": "textarea"},
        {"cid": "q2", "text": {"en_US": "Where?"}, "question_type": "textarea", "required": True}]}]}})
    rendered = Page(id="p1", position=0, kind="question", questions=[
        Question(id="q1", text="Why?", kind="text_long", required=False),
        Question(id="q2", text="Where?", kind="text_long", required=False)])
    result = ReadResult(snapshot=SurveySnapshot(title="", pages=[rendered]), coverage=Coverage(), capture_dir=tmp_path)
    apply_definition(result, definition)
    first, second = result.snapshot.pages[0].questions
    assert first.required is False       # visible label fills the unknown
    assert second.required is True       # the definition stays authoritative


def test_judge_prompt_never_calls_unknown_requiredness_optional():
    from surveycoach.judge.prompts import _question_lines

    def line(required):
        return _question_lines(Question(id="q", text="Why?", kind="text_long", required=required))[0]
    assert "[text_long, required]" in line(True)
    assert "[text_long, optional]" in line(False)
    assert "optional" not in line(None)
    assert "requiredness unknown" in line(None)


def test_round_context_treats_a_missing_field_as_unknown_not_required():
    from surveycoach.server.rounds import locations

    def context(question):
        snapshot = {"title": "t", "survey_type": "non_ihut_product", "pages": [
            {"id": "p", "position": 0, "kind": "question", "questions": [question]}]}
        return next(place["context"] for place in locations(snapshot) if place["question_id"])
    base = {"id": "q", "text": "Why?", "kind": "text_long"}
    assert context(base)[3] is None
    assert context(dict(base, required=True))[3] is True
    assert context(dict(base, required=False))[3] is False
