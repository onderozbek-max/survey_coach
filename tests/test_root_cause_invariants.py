"""Offline recurrence guards: capture representation is not member evidence."""
from copy import deepcopy

import pytest

from builders import context, image, one_question_survey, question
from surveycoach.checks import images, phone
from surveycoach.findings import CheckResult
from surveycoach.quality import build_quality
from surveycoach.review import run_review
from surveycoach.rubric import load_rubric
from surveycoach.scoring import score
from surveycoach.snapshot import Option, Page, Question, Scale, SurveySnapshot
from surveycoach.timing import estimate


@pytest.mark.parametrize("kind", ["grid_single", "grid_multi", "rating", "slider"])
def test_structured_rows_and_scale_labels_have_capture_independent_reading(kind):
    q = Question(id="q", text="Rate these products", kind=kind,
                 rows=["Prepared family meals", "Fresh salad kits"] if kind.startswith("grid") else [],
                 scale=Scale(points=5, low_label="Very dissatisfied", high_label="Very satisfied",
                             labels=["Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied"]))
    snapshot = SurveySnapshot(title="Meals", pages=[Page(id="p", position=0, kind="question", questions=[q])])
    raw = "\n".join([q.text, *q.rows, *q.scale.labels])
    captured = snapshot.model_copy(deep=True)
    captured.pages[0].text = raw
    assert estimate(snapshot).total_seconds == estimate(captured).total_seconds
    # End labels also occur in labels; each rendered label is counted once.
    words = len(raw.split())
    expected = words * .3 + 1.5 + 4 * len(q.rows) + (3 if kind.startswith("grid") else 4 if kind == "rating" else 6)
    assert estimate(snapshot).total_seconds == pytest.approx(round(expected, 1))


@pytest.mark.parametrize("kind", ["single_choice", "multi_choice", "dropdown", "image_choice", "ranking"])
def test_option_reading_is_stable_across_capture_representations(kind):
    q = Question(id="q", text="Choose a meal", kind=kind, help_text="Consider your household",
                 options=[Option(id="a", label="Prepared family meals"), Option(id="b", label="Fresh salad kits")])
    snapshot = SurveySnapshot(title="Meals", pages=[Page(id="p", position=0, kind="question", questions=[q])])
    before = snapshot.model_dump()
    captured = snapshot.model_copy(deep=True)
    captured.pages[0].text = "\n".join([q.text, q.help_text, *[o.label for o in q.options]])
    assert estimate(snapshot).total_seconds == estimate(captured).total_seconds
    assert snapshot.model_dump() == before


def test_unloaded_reader_image_does_not_silently_reduce_layout_credit():
    loaded = one_question_survey(question(media=[image()]))
    unloaded = loaded.model_copy(deep=True)
    unloaded.pages[1].questions[0].media[0].loaded = False
    assert phone.stays_put(context(unloaded)).fraction == phone.stays_put(context(loaded)).fraction
    review = run_review(unloaded)
    assert review.results["B7"].assessed is False
    assert review.results["B7"].findings[0].severity == "worth_improving"
    assert "B7" in review.scorecard.pending_blockers
    assert "B7" not in review.scorecard.open_blockers


@pytest.mark.parametrize("failure", ["link", "truncation", "both"])
@pytest.mark.parametrize("location", ["page", "question", "option"])
def test_media_cannot_dilute_observed_layout_failures(failure, location):
    snapshot = one_question_survey(question())
    page = snapshot.pages[1]
    if failure in {"link", "both"}:
        page.links_out = ["https://example.com/made-up-study-details"]
    if failure in {"truncation", "both"}:
        page.questions[0].text = "Which meal would you pref..."
    baseline = phone.stays_put(context(snapshot))
    assert 0 < baseline.fraction < 1
    assert len(baseline.findings) == (2 if failure == "both" else 1)
    before = snapshot.model_dump()
    for loaded in (True, False):
        pictured = snapshot.model_copy(deep=True)
        media = image(loaded=loaded)
        if location == "page":
            pictured.pages[1].media = [media]
        elif location == "question":
            pictured.pages[1].questions[0].media = [media]
        else:
            pictured.pages[1].questions[0].options[0].media = media
        assert phone.stays_put(context(pictured)) == baseline
    assert snapshot.model_dump() == before


@pytest.mark.parametrize("kind", ["grid_single", "grid_multi", "rating", "slider"])
@pytest.mark.parametrize("raw_container", [False, True])
def test_grid_scale_intro_overlap_counts_once_but_preserves_extra_occurrences(kind, raw_container):
    rows = ["Prepared family meals", "Fresh salad kits"] if kind.startswith("grid") else []
    q = Question(id="q", text="Rate these products", kind=kind, rows=rows,
                 help_text="Consider each product separately.",
                 scale=Scale(points=3, low_label="Not appealing", high_label="Very appealing",
                             labels=["Not appealing", "Somewhat appealing", "Very appealing"]))
    prose = "Imagine convenient meals for your family."
    baseline = SurveySnapshot(title="Meals", pages=[Page(id="p", position=0, kind="question",
                                                        intro_text=prose, questions=[q])])
    captured = baseline.model_copy(deep=True)
    container = "\n".join([prose, q.text, q.help_text, *rows, *q.scale.labels])
    captured.pages[0].intro_text = container
    if raw_container:
        captured.pages[0].text = container
    before = captured.model_dump()
    seconds = estimate(baseline).total_seconds
    assert estimate(captured).total_seconds == seconds
    assert captured.model_dump() == before
    # An extra row/scale occurrence inside the intro remains real reading, even
    # when raw repeats that complete intro. Never erase all matching labels.
    label = rows[0] if rows else q.scale.low_label
    extra_seconds = round(len(label.split()) * .3, 1)
    repeated_intro = captured.model_copy(deep=True)
    repeated_intro.pages[0].intro_text += "\n" + label
    if raw_container:
        repeated_intro.pages[0].text = repeated_intro.pages[0].intro_text
    assert estimate(repeated_intro).total_seconds == pytest.approx(seconds + extra_seconds)
    # A separate raw occurrence after an already-covered intro must also survive.
    if raw_container:
        repeated_raw = captured.model_copy(deep=True)
        repeated_raw.pages[0].text += "\n" + label
        assert estimate(repeated_raw).total_seconds == pytest.approx(seconds + extra_seconds)


def test_image_choice_threshold_is_layout_advice_not_answer_deletion():
    q = question(kind="image_choice", options=tuple(f"Pack {i}" for i in range(7)))
    for option in q.options:
        option.media = image()
    before = q.model_dump()
    checked = images.fair_image_choices(context(one_question_survey(q)))
    finding = next(f for f in checked.findings if "7 image options" in f.evidence)
    assert "review" in finding.headline.lower()
    assert "configured" in finding.explanation.lower()
    assert "not" in finding.explanation and "maximum" in finding.explanation
    assert "distinct" in finding.explanation
    assert "routing" in finding.explanation and "randomization" in finding.explanation
    assert finding.suggested_text is None and finding.options == []
    assert q.model_dump() == before


def full_results():
    rubric = load_rubric()
    return {c.id: CheckResult(criterion_id=c.id, fraction=1) for c in rubric.criteria if c.active} | {
        b.id: CheckResult(criterion_id=b.id) for b in rubric.blockers}


@pytest.mark.parametrize("cid", ["2.1", "3.1", "6.5", "8.3"])
def test_unassessed_numeric_credit_never_allows_ready(cid):
    results = full_results()
    results[cid].assessed = False
    card = score(load_rubric(), results)
    assert card.provisional and card.unchecked_points > 0
    assert card.readiness != "ready"


@pytest.mark.parametrize("cid", ["2.1", "6.5"])
def test_unassessed_na_is_unknown_not_an_exclusion(cid):
    results = full_results()
    results[cid] = CheckResult(criterion_id=cid, applies=False, assessed=False)
    before = deepcopy(results)
    rubric = load_rubric()
    card = score(rubric, results)
    quality = build_quality({"results": {key: r.model_dump() for key, r in results.items()}}, rubric)
    assert card.not_applicable_points == 0
    assert card.unchecked_points > 0 and card.provisional
    assert card.readiness != "ready"
    assert quality["applicable_points"] == 100
    assert quality["unchecked_points"] == card.unchecked_points
    assert quality["provisional"]
    assert results == before


def test_unknown_applicability_remains_in_scope_and_review_unchecked(monkeypatch):
    from surveycoach import review as pipeline
    from surveycoach.server.rounds import scope
    results = full_results()
    results["6.5"] = CheckResult(criterion_id="6.5", fraction=1, assessed=False, applies=False)
    monkeypatch.setattr(pipeline, "run_all", lambda ctx: results)
    reviewed = pipeline.run_review(one_question_survey(question()))
    title = next(c.title for c in load_rubric().criteria if c.id == "6.5")
    assert title in reviewed.unchecked
    scoped = scope({"review": {"results": {cid: r.model_dump() for cid, r in results.items()}}})
    assert scoped["total_count"] == len(results)
    assert scoped["checked_count"] == len(results) - 1
    assert title in scoped["unchecked_checks"]


@pytest.mark.parametrize("missing", ["assessed", "applies"])
def test_partial_saved_results_cannot_manufacture_quality_credit(missing):
    results = {cid: r.model_dump() for cid, r in full_results().items()}
    del results["2.1"][missing]
    del results["B4"][missing]
    q = build_quality({"results": results}, load_rubric())
    assert q["unchecked_points"] == 5
    assert q["blockers"]["unchecked"] == 1
    assert q["provisional"]


def test_scale_endpoints_duplicate_options_but_not_legitimate_extra_raw_occurrences():
    q = Question(id="q", text="Rate your meal", kind="rating",
                 options=[Option(id="a", label="Very poor"), Option(id="b", label="Very good")],
                 scale=Scale(points=2, low_label="Very poor", high_label="Very good"))
    snapshot = SurveySnapshot(title="Meals", pages=[Page(id="p", position=0, kind="question", questions=[q])])
    base = estimate(snapshot).total_seconds
    snapshot.pages[0].text = "\n".join([q.text, "Very poor", "Very good"])
    assert estimate(snapshot).total_seconds == base
    snapshot.pages[0].text += "\nVery poor"
    assert estimate(snapshot).total_seconds == pytest.approx(base + .6)


@pytest.mark.parametrize("bid", ["B4", "B7"])
def test_unassessed_na_blocker_stays_pending_in_quality_and_score(bid):
    results = full_results()
    results[bid] = CheckResult(criterion_id=bid, applies=False, assessed=False)
    rubric = load_rubric()
    assert score(rubric, results).pending_blockers == [bid]
    quality = build_quality({"results": {key: r.model_dump() for key, r in results.items()}}, rubric)
    assert quality["blockers"]["unchecked"] == 1
    assert quality["provisional"]
