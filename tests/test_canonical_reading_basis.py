"""Canonical timing evidence crosses serialization/JS without touching capture identity."""
from copy import deepcopy

import pytest

from surveycoach.demo_export import build_demo_data
from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from surveycoach.snapshot import Option, Page, Question, Scale, SurveySnapshot
from surveycoach.timing import TimingConstants, estimate
from test_preview_reading_projection import delta, fix


def snapshot(kind="single_choice"):
    q = Question(id="q1", text="Which household meal do you prefer today?", kind=kind,
                 help_text="Consider the entire household before choosing.",
                 options=[Option(id="a", label="Freshly prepared meals for the entire family"),
                          Option(id="b", label="Fresh salad kits")],
                 rows=["Convenient meals for busy weekdays"] if kind.startswith("grid") else [],
                 scale=Scale(points=2, low_label="Not at all appealing", high_label="Very appealing",
                             labels=["Not at all appealing", "Very appealing"]) if kind in {"rating", "slider"} else None)
    return SurveySnapshot(title="Made-up meals", pages=[Page(id="p", position=0, kind="question", questions=[q])])


def output(s):
    return enrich({"snapshot": s.model_dump(), "review": None}, load_rubric())["snapshot"]["pages"][0]


@pytest.mark.parametrize("kind", ["single_choice", "multi_choice", "dropdown", "grid_single", "grid_multi", "rating", "slider", "ranking"])
def test_exported_reading_fields_are_exactly_timings_reading_component(kind):
    s = snapshot(kind)
    q = s.pages[0].questions[0]
    basis = output(s)["reading_basis"]
    c = TimingConstants()
    assert basis["seconds_per_word"] == c.seconds_per_word
    assert all(f["question_id"] == q.id for f in basis["fields"])
    words = sum(len(f["text"].split()) for f in basis["fields"])
    assert estimate(s).total_seconds == pytest.approx(round(words * c.seconds_per_word + c.interaction(q) + c.page_overhead, 1))
    assert all(label in [f["text"] for f in basis["fields"]] for label in q.rows)
    if q.scale:
        assert all(label in [f["text"] for f in basis["fields"]] for label in q.scale.labels)
    # Feeding the counted fields back as an exact raw capture must not add cost.
    s.pages[0].text = "\n".join(f["text"] for f in basis["fields"])
    assert output(s)["reading_basis"] == basis
    assert estimate(s).total_seconds == pytest.approx(round(words * c.seconds_per_word + c.interaction(q) + c.page_overhead, 1))


@pytest.mark.parametrize("kind,attribute", [("dropdown", "option"), ("grid_single", "row"), ("slider", "scale")])
def test_produced_answer_row_and_scale_fields_work_in_real_preview(kind, attribute):
    s = snapshot(kind)
    q = s.pages[0].questions[0]
    original = {"option": q.options[0].label, "row": next(iter(q.rows), ""),
                "scale": q.scale.low_label if q.scale else ""}[attribute]
    assert delta([output(s)], [fix(original, "Meal", "q1")]) == [round((len(original.split()) - 1) * .3)]


def test_backend_fields_drive_real_js_without_duplicate_raw_intro_savings():
    s = snapshot("dropdown")
    original = s.pages[0].questions[0].text
    structured = output(s)
    s.pages[0].intro_text = "Imagine a convenient dinner for the whole family.\n" + original
    s.pages[0].text = s.pages[0].intro_text + "\n" + s.pages[0].questions[0].help_text + "\n" + "\n".join(o.label for o in s.pages[0].questions[0].options)
    captured = output(s)
    assert delta([structured, captured], [fix(original, "Preferred meal?", "q1")]) == [2, 2]
    prose = [f for f in captured["reading_basis"]["fields"] if "question_id" not in f]
    assert "Imagine a convenient dinner for the whole family." in " ".join(f["text"] for f in prose)
    assert original not in " ".join(f["text"] for f in prose)
    s.pages[0].text += "\n" + original
    repeated = output(s)
    assert original in " ".join(f["text"] for f in repeated["reading_basis"]["fields"] if "question_id" not in f)
    # The extra observed page-scoped copy is not a second question-scoped replacement.
    assert delta([repeated], [fix(original, "Preferred meal?", "q1")]) == [2]


def test_projection_is_derived_idempotent_and_not_part_of_hashes_or_model():
    s = snapshot()
    source = {"snapshot": s.model_dump(), "review": None}
    before = deepcopy(source)
    identity = (s.content_hash, s.review_hash)
    first = enrich(source, load_rubric())
    first["snapshot"]["pages"][0]["reading_basis"] = {"seconds_per_word": 999, "fields": [{"text": "Stale injected basis"}]}
    second = enrich(first, load_rubric())
    assert second["snapshot"]["pages"][0]["reading_basis"] == output(s)["reading_basis"]
    restored = SurveySnapshot.model_validate(second["snapshot"])
    assert (restored.content_hash, restored.review_hash) == identity
    assert "reading_basis" not in restored.model_dump()["pages"][0]
    assert source == before


def test_nondefault_reading_rate_comes_from_canonical_timing_projection():
    from surveycoach.timing import reading_basis
    s = snapshot()
    assert reading_basis(s.pages[0], TimingConstants(seconds_per_word=.7))["seconds_per_word"] == .7


def test_every_synthetic_demo_page_exports_backend_basis():
    for survey in build_demo_data()["surveys"]:
        s = SurveySnapshot.model_validate(survey["snapshot"])
        for page, encoded in zip(s.pages, survey["snapshot"]["pages"], strict=True):
            from surveycoach.timing import reading_basis
            assert encoded["reading_basis"] == reading_basis(page)


def test_unenriched_legacy_capture_remains_unavailable_not_zero():
    page = snapshot().model_dump()["pages"][0]
    assert "reading_basis" not in page
    assert delta([page], []) == [None]
