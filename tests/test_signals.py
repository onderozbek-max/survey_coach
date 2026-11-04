"""Evidence-only member experience projection; no persistence or providers."""
from copy import deepcopy

import pytest

from builders import page, question, survey
from surveycoach.labels import screen_labels
from surveycoach.rubric import load_rubric
from surveycoach.server.plan import build_plan
from surveycoach.signals import build_overview, _minutes
from surveycoach.timing import estimate


def result(fraction=1.0, **extra):
    return {"fraction": fraction, "assessed": True, "applies": True,
            "findings": [], **extra}


def finding(fp="issue", cid="B2", severity="must_fix", **extra):
    return {"fingerprint": fp, "criterion_id": cid, "severity": severity,
            "headline": "An answer is missing", **extra}


def overview(results=None, findings=(), decisions=None, snapshot=None):
    snapshot = snapshot or survey(page(1, question()))
    screens = screen_labels(snapshot)
    review = {"results": results or {}, "findings": list(findings)}
    decisions = decisions or {}
    rubric = load_rubric()
    plan = build_plan(review["findings"], decisions,
                      {c.id: c.points for c in rubric.criteria}, screens)
    return build_overview(snapshot, review, decisions, screens, plan, rubric)


def signal(out, name):
    return next(item for item in out["signals"] if item["id"] == name)


def long_survey(conditional=False):
    # 2695 words × .3 seconds + 1.5 overhead = 810 seconds = 13.5 minutes.
    if not conditional:
        return survey(page(1, text="word " * 2695), survey_type="community_pulse")
    return survey(page(1, question(conditional=True), text="word " * 2695),
                  survey_type="community_pulse")


def test_six_signals_and_open_blocker_overrides_full_credit():
    out = overview({"4.2": result(), "5.1": result()}, [finding()])
    assert [s["id"] for s in out["signals"]] == [
        "time", "clarity", "honest", "energy", "tone", "phone"]
    honest = signal(out, "honest")
    assert honest["state"] == "needs_work"
    assert honest["label"] == "Needs attention"
    assert honest["findings"] == ["issue"]


@pytest.mark.parametrize("decision,expected", [
    ({"action": "keep", "reason": "Required for this study"}, "strong"),
    ({"action": "keep", "reason": "  "}, "needs_work"),
    ({"action": "keep"}, "needs_work"),
    ({"action": "pending"}, "needs_work"),
    ({"action": "pick"}, "strong"),
    ({"action": "original"}, "strong"),
])
def test_only_explicit_decisions_stop_blocker_override(decision, expected):
    out = overview({"4.2": result()}, [finding()], {"issue": decision})
    assert signal(out, "honest")["state"] == expected


@pytest.mark.parametrize("results", [
    {}, {"3.4": result(assessed=False)}, {"3.4": result(None)},
    {"3.4": result(applies=False)}, {"3.4": {"fraction": 1}},
    {"3.4": {"fraction": 1, "assessed": True}},
])
def test_no_assessed_evidence_is_unknown_or_mixed_with_findings(results):
    clean = signal(overview(results), "clarity")
    assert clean["state"] == "unknown"
    assert clean["label"] == "Not checked yet"
    issue = finding(cid="3.4", severity="worth_improving")
    assert signal(overview(results, [issue]), "clarity")["state"] == "mixed"


@pytest.mark.parametrize("fraction,expected", [
    (1, "strong"), (.85, "strong"), (.849, "mixed"), (.6, "mixed"),
    (.599, "needs_work"), (0, "needs_work"),
])
def test_weighted_ratio_thresholds(fraction, expected):
    assert signal(overview({"3.4": result(fraction)}), "clarity")["state"] == expected


def test_ratio_weights_only_assessed_applicable_active_criteria():
    # (3*1 + 2*0) / 5 = .6, not the unweighted .5 or a full group denominator.
    out = overview({"3.1": result(1), "3.4": result(0),
                    "3.2": result(0, assessed=False), "3.3": result(0, applies=False),
                    "3.5": result(None)})
    assert signal(out, "clarity")["state"] == "mixed"
    out = overview({"3.1": result(1), "3.4": result(0)})
    assert signal(out, "clarity")["state"] == "mixed"


def test_time_uses_effective_type_targets_and_half_minutes():
    out = overview(snapshot=long_survey())
    time = signal(out, "time")
    assert time["state"] == "needs_work"
    assert time["summary"] == (
        "About 13½ minutes (estimate). Community surveys aim for 5 minutes or less.")
    assert out["energy"]["total_seconds"] == 810


@pytest.mark.parametrize("seconds,expected", [(300, "strong"), (480, "mixed"), (481, "needs_work")])
def test_time_target_boundaries(seconds, expected):
    # Every whole 3 seconds can be represented by ten words.
    snapshot = survey(page(1, text="word " * int((seconds - 1.5) / .3)),
                      survey_type="community_pulse")
    assert signal(overview(snapshot=snapshot), "time")["state"] == expected


def test_branching_disables_length_rule_and_retained_length_credit():
    out = overview({"2.1": result(0)}, snapshot=long_survey(True))
    time = signal(out, "time")
    assert "Branching makes the total uncertain." in time["summary"]
    assert time["state"] == "unknown"
    assert out["energy"]["path_uncertain"] is True
    assert "Branching makes the total uncertain." in out["subline"]


@pytest.mark.parametrize("value,expected", [
    (1, "1 minute"), (13.5, "13½ minutes"), (13.24, "13 minutes"),
    (13.26, "13½ minutes"), (13.75, "14 minutes"), (.5, "½ minute"),
])
def test_half_minute_format(value, expected):
    assert _minutes(value) == expected


def test_strengths_are_only_full_evidence_backed_positives_sorted_by_points():
    results = {cid: result() for cid in ["3.4", "4.2", "8.3", "9.1", "10.1", "1.3"]}
    results.update({"6.2": result(assessed=False), "6.4": result(applies=False),
                    "8.1": result(.9), "8.2": result(findings=[finding()]),
                    "8.5": {"fraction": 1}, "3.1": result()})
    out = overview(results, [finding(cid="9.1", severity="worth_improving")])
    assert out["strengths"] == ["Treats members as co-creators", "A genuine thank-you",
                                "An insider moment members will enjoy"]


def test_legacy_scorecard_and_checked_list_do_not_imply_credit():
    snapshot = survey(page(1))
    review = {"findings": [], "checked_criteria": ["9.1", "8.3"],
              "scorecard": {"strengths": ["Warm and human"], "score": 100}}
    out = build_overview(snapshot, review, {}, screen_labels(snapshot), {}, load_rubric())
    assert out["strengths"] == []
    assert signal(out, "tone")["state"] == "unknown"


def test_energy_uses_per_screen_seconds_zones_and_visible_worst_with_question_lookup():
    snapshot = survey(page(1, question(qid="q1", kind="text_long")),
                      page(2, question(qid="q2", kind="single_choice")),
                      page(3, question(qid="q3", kind="text_long")), page(4))
    findings = [finding("hidden", page_id="p2", absorbed_by="root"),
                finding("soft", "3.1", "worth_improving", question_id="q1"),
                finding("hard", page_id="p1"), finding("survey-wide")]
    out = overview(findings=findings, snapshot=snapshot)
    timing = estimate(snapshot)
    assert len(out["energy"]["screens"]) == 4
    for screen, timed in zip(out["energy"]["screens"], timing.pages):
        assert screen["seconds"] == timed.seconds
        assert screen["zone"] == timed.fatigue
    assert [s["worst"] for s in out["energy"]["screens"]] == ["must_fix", None, None, None]
    assert out["energy"]["heaviest"] == ["p1", "p3", "p2"]
    assert signal(out, "clarity")["pages"] == ["p1"]


def test_headline_and_heaviest_screen_subline():
    snapshot = survey(page(1, text="word " * 2695))
    screens = [{"page_id": "p1", "screen": 1, "name": "Q8–Q18", "questions": []}]
    plan = {"counts": {"must_fix": 3, "open_must_fix": 3, "quick_wins": 6}}
    out = build_overview(snapshot, {}, {}, screens, plan, load_rubric())
    assert out["headline"] == "3 must-fixes before launch, then 6 quick wins"
    assert out["subline"] == ("About 13½ minutes for members (estimate). "
                               "The heaviest moment is Q8–Q18.")
    plan["counts"]["open_must_fix"] = 0
    assert build_overview(snapshot, {}, {}, screens, plan, load_rubric())["headline"] == (
        "No must-fixes found in what we checked")


def test_unassessed_blocker_concern_is_not_a_pass():
    out = overview({"B2": result(None, assessed=False), "4.2": result()},
                   [finding(question_id="q1")])
    assert signal(out, "honest")["state"] == "needs_work"
    assert signal(out, "honest")["pages"] == ["p1"]


def test_time_ignores_stale_stored_timing_and_uses_each_survey_type_target():
    snapshot = long_survey().model_copy(update={"survey_type": "ihut"})
    review = {"est_minutes": 1, "timing": {"total_seconds": 60}, "results": {}}
    out = build_overview(snapshot, review, {}, screen_labels(snapshot), {}, load_rubric())
    assert signal(out, "time")["state"] == "mixed"
    assert signal(out, "time")["summary"] == (
        "About 13½ minutes (estimate). Home-use test surveys aim for 10 minutes or less.")
    assert out["energy"]["total_seconds"] == 810


def test_absorbed_concerns_still_disqualify_strengths_not_navigation_or_markers():
    out = overview({"4.2": result()}, [finding(cid="4.2", severity="worth_improving",
                                             absorbed_by="root", page_id="p1")])
    assert out["strengths"] == []
    assert signal(out, "honest")["findings"] == []
    assert out["energy"]["screens"][0]["worst"] is None


def test_worth_improving_marker_and_question_location_take_precedence():
    snapshot = survey(page(1, question(qid="q1")), page(2))
    out = overview(findings=[finding(cid="3.4", severity="worth_improving",
                                    question_id="q1", page_id="p2")], snapshot=snapshot)
    assert [s["worst"] for s in out["energy"]["screens"]] == ["worth_improving", None]
    assert signal(out, "clarity")["pages"] == ["p1"]


def test_projection_with_findings_decisions_and_screens_is_detached():
    snapshot = survey(page(1, question()))
    review = {"results": {"3.4": result()}, "findings": [finding(page_id="p1")]}
    decisions = {"issue": {"action": "keep", "reason": "Study requirement"}}
    screens = screen_labels(snapshot)
    plan = build_plan(review["findings"], decisions, {}, screens)
    args = (snapshot, review, decisions, screens, plan, load_rubric())
    before = deepcopy(args)
    first = build_overview(*args)
    assert first == build_overview(*args)
    first["energy"]["screens"][0]["name"] = "Changed"
    first["signals"][2]["pages"].clear()
    first["signals"][2]["findings"].clear()
    assert args == before


def test_empty_snapshot_and_pure_repeatable_detached_projection():
    snapshot = survey()
    review = {"results": {"3.4": result()}, "findings": []}
    args = (snapshot, review, {}, [], {}, load_rubric())
    before = deepcopy(args)
    out = build_overview(*args)
    assert out["energy"] == {"total_seconds": 0, "path_uncertain": False,
                             "screens": [], "heaviest": []}
    assert "heaviest" not in out["subline"]
    assert args == before
    assert out == build_overview(*args)
    out["signals"][1]["findings"].append("mutation")
    out["strengths"].clear()
    assert args == before
