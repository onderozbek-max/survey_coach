"""The verdict (brief 4.3): headline, survey story, tiles and time, all computed from data.

Rule, exactly as implemented (open = not yet decided; a kept item needs a reason):
  * any open fix_before_launch item            -> kind `fix_before_launch`
  * else any open worth_improving or you_check -> kind `almost_ready`
  * else                                       -> kind `ready_for_signoff`
Ready therefore means nothing is open: no fix, every curated You check done or kept, and every
improvement either applied or kept on purpose. No evidence at all (nothing assessed, nothing
raised) gives no verdict rather than a confident "ready".
"""
import pytest

from builders import intro, page, question, survey, thank_you
from concept_fixture import concept_survey
from surveycoach.labels import screen_labels
from surveycoach.rubric import load_rubric
from surveycoach.server.plan import build_plan
from surveycoach.signals import build_overview
from surveycoach.verdict import headline_for, survey_story

PASS = {"fraction": 1.0, "assessed": True, "applies": True, "findings": []}


def f(fp, severity, cid="3.2", **extra):
    return {"fingerprint": fp, "criterion_id": cid, "severity": severity, "headline": f"Issue {fp}", **extra}


def run(findings=(), decisions=None, snapshot=None, results=None, **kw):
    snapshot = snapshot or concept_survey()
    screens = screen_labels(snapshot)
    review = {"results": results if results is not None else {"3.4": PASS}, "findings": list(findings)}
    rubric = load_rubric()
    plan = build_plan(review["findings"], decisions or {}, {c.id: c.points for c in rubric.criteria}, screens)
    return build_overview(snapshot, review, decisions or {}, screens, plan, rubric, **kw)


def verdict(*args, **kw):
    return run(*args, **kw)["verdict"]


@pytest.mark.parametrize("fix,improve,check,expected", [
    (2, 0, 0, "2 things to fix before launch"),
    (1, 5, 4, "1 thing to fix before launch"),
    (0, 3, 4, "Almost ready: 3 quick improvements and 4 things to check yourself"),
    (0, 1, 1, "Almost ready: 1 quick improvement and 1 thing to check yourself"),
    (0, 3, 0, "Almost ready: 3 quick improvements"),
    (0, 0, 4, "Almost ready: 4 things to check yourself"),
    (0, 0, 0, "Ready for sign-off"),
])
def test_headline_counts_come_from_the_data(fix, improve, check, expected):
    assert headline_for(fix, improve, check) == expected


def test_kind_follows_the_rule_in_the_module_docstring():
    assert verdict([f("a", "must_fix")])["kind"] == "fix_before_launch"
    assert verdict([f("a", "worth_improving")])["kind"] == "almost_ready"
    both = verdict([f("a", "must_fix"), f("b", "worth_improving")])
    assert both["kind"] == "fix_before_launch" and both["headline"] == "1 thing to fix before launch"


def test_curated_you_check_items_keep_a_clean_survey_from_being_ready():
    v = verdict()
    assert v["kind"] == "almost_ready" and v["tiles"] == {"fix": 0, "improve": 0, "you_check": 6}
    assert v["headline"] == "Almost ready: 6 things to check yourself"


def test_ready_needs_every_you_check_done_or_kept_and_every_improvement_closed():
    clean = survey(page(1, question(required=True)), page(2, question("q2", required=True)))
    assert verdict(snapshot=clean)["kind"] == "ready_for_signoff"
    open_improve = verdict([f("a", "worth_improving")], snapshot=clean)
    assert open_improve["kind"] == "almost_ready"
    kept = {"a": {"action": "keep", "reason": "On purpose"}}
    assert verdict([f("a", "worth_improving")], kept, snapshot=clean)["kind"] == "ready_for_signoff"
    blank = {"a": {"action": "keep", "reason": " "}}
    assert verdict([f("a", "worth_improving")], blank, snapshot=clean)["kind"] == "almost_ready"
    assert verdict([f("a", "must_fix")], {"a": {"action": "original"}}, snapshot=clean)["kind"] == "ready_for_signoff"


def test_you_check_items_are_closed_through_the_ordinary_decisions():
    fingerprints = [item["fingerprint"] for item in run()["you_check"]]
    assert len(fingerprints) == 6 and all(fp.startswith("you-check:") for fp in fingerprints)
    decisions = {fp: {"action": "original"} for fp in fingerprints}
    done = verdict(decisions=decisions)
    assert done["kind"] == "ready_for_signoff" and done["headline"] == "Ready for sign-off"
    assert done["tiles"] == {"fix": 0, "improve": 0, "you_check": 0}
    one_kept = {**decisions, fingerprints[0]: {"action": "keep", "reason": "Fine as is"}}
    assert verdict(decisions=one_kept)["kind"] == "ready_for_signoff"


def test_nothing_assessed_and_nothing_raised_gives_no_verdict():
    plain = survey(page(1, question(required=True)))
    assert verdict(results={}, snapshot=plain) is None


def test_progress_counts_done_and_total_items():
    v = verdict([f("a", "worth_improving"), f("b", "worth_improving", cid="3.1")],
                {"a": {"action": "original"}})
    assert v["progress"] == {"done": 1, "total": 2 + 6}


# --- the story ------------------------------------------------------------------------------

def test_story_is_built_only_from_detected_structure():
    assert survey_story(concept_survey()) == (
        "Members get a welcome, answer 1 warm-up question, see the idea, react to 3 similar ideas, "
        "then wrap up with 3 questions.")


def test_story_never_invents_names_or_praise():
    story = survey_story(concept_survey())
    for invented in ("Sunrise", "Skillet", "friendly", "fun", "tray", "kit", "breakfast"):
        assert invented not in story


def test_story_omits_whatever_it_cannot_detect():
    plain = survey(page(1, question()), page(2, question("q2")), thank_you())
    assert survey_story(plain) == "Members answer 2 questions."
    with_welcome = survey(intro(), page(1, question()))
    assert survey_story(with_welcome) == "Members get a welcome, then answer 1 question."
    assert survey_story(survey()) == ""
    no_warm = concept_survey()
    no_warm.pages.pop(1)
    assert "warm-up" not in survey_story(no_warm)
    no_wrap = concept_survey()
    del no_wrap.pages[9:12]
    story = survey_story(no_wrap)
    assert "wrap up" not in story and story.endswith("react to 3 similar ideas.")


def test_story_reaches_the_verdict():
    assert verdict()["story"] == survey_story(concept_survey())


# --- time -----------------------------------------------------------------------------------

def test_time_uses_the_survey_types_target_and_the_same_states():
    v = verdict(snapshot=concept_survey("services_concept"))
    time = v["time"]
    assert (time["target_low"], time["target_high"]) == (6.0, 10.0)
    assert time["minutes"] == pytest.approx(3.5, abs=.1) and time["state"] == "looks_good"


def test_over_target_time_is_worth_improving_never_a_fix_and_blocks_ready_until_closed():
    long = survey(page(1, question(required=True), text="word " * 2695), survey_type="community_pulse")
    out = run(snapshot=long)
    time = out["verdict"]["time"]
    assert 13 < time["minutes"] < 14 and time["state"] == "worth_improving"
    assert out["verdict"]["kind"] == "almost_ready"
    assert out["verdict"]["tiles"] == {"fix": 0, "improve": 1, "you_check": 0}
    assert out["verdict"]["headline"] == "Almost ready: 1 quick improvement"
    [item] = out["items"]
    assert item["kind"] == "time" and item["signal"] == "time" and item["fingerprints"][0].startswith("time:over-target:")
    kept = {item["fingerprints"][0]: {"action": "keep", "reason": "Long on purpose"}}
    assert verdict(snapshot=long, decisions=kept)["kind"] == "ready_for_signoff"


def test_a_length_finding_already_explains_an_over_target_survey():
    long = survey(page(1, question(required=True), text="word " * 2695), survey_type="community_pulse")
    out = run([f("len", "worth_improving", cid="2.1")], snapshot=long)
    assert [i["kind"] for i in out["items"]] == ["finding"]
    assert out["verdict"]["tiles"]["improve"] == 1
    assert out["verdict"]["time"]["state"] == "worth_improving"


def test_branching_makes_the_duration_state_unknown_not_good():
    branching = survey(page(1, question(required=True, conditional=True)))
    assert verdict(snapshot=branching)["time"]["state"] is None


def test_the_chosen_or_detected_type_sets_the_target():
    snapshot = concept_survey("non_ihut_product")
    assert verdict(snapshot=snapshot)["time"]["target_high"] == 8.0
    detected = verdict(snapshot=snapshot, survey_type="services_concept", type_source="detected")
    assert detected["time"]["target_high"] == 10.0 and detected["time"]["type_source"] == "detected"
    assert detected["time"]["survey_type"] == "services_concept"
