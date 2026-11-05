"""Evidence-only member experience projection; no persistence or providers.

Signals, tiles, screen markers and the verdict all read ONE item list, and every state comes
from surveycoach.status (brief 4.2). These tests pin that behaviour.
"""
from copy import deepcopy

import pytest

from builders import image, page, question, survey
from surveycoach.labels import screen_labels
from surveycoach.rubric import load_rubric
from surveycoach.server.plan import build_plan
from surveycoach.signals import SIGNALS, SIGNAL_OF, build_overview
from surveycoach.timing import estimate
from surveycoach.verdict import minutes_text as _minutes


def result(fraction=1.0, **extra):
    return {"fraction": fraction, "assessed": True, "applies": True,
            "findings": [], **extra}


def finding(fp="issue", cid="B2", severity="must_fix", **extra):
    return {"fingerprint": fp, "criterion_id": cid, "severity": severity,
            "headline": "An answer is missing", **extra}


def overview(results=None, findings=(), decisions=None, snapshot=None, **kw):
    snapshot = snapshot or survey(page(1, question()))
    screens = screen_labels(snapshot)
    review = {"results": results or {}, "findings": list(findings)}
    decisions = decisions or {}
    rubric = load_rubric()
    plan = build_plan(review["findings"], decisions,
                      {c.id: c.points for c in rubric.criteria}, screens)
    return build_overview(snapshot, review, decisions, screens, plan, rubric, **kw)


def signal(out, name):
    return next(item for item in out["signals"] if item["id"] == name)


def honest_passes():
    return {cid: result() for cid in ("4.1", "4.2", "4.3", "4.4")}   # 4 of the 8 honest-answer checks


def long_survey(conditional=False):
    # 2695 words × .3 seconds + 1.5 overhead = 810 seconds = 13.5 minutes.
    if not conditional:
        return survey(page(1, text="word " * 2695), survey_type="community_pulse")
    return survey(page(1, question(conditional=True), text="word " * 2695),
                  survey_type="community_pulse")


def test_six_signals_and_every_active_criterion_lives_in_exactly_one():
    out = overview()
    assert [s["id"] for s in out["signals"]] == ["time", "clarity", "honest", "energy", "tone", "phone"]
    ids = [cid for _, _, group in SIGNALS for cid in group]
    assert len(ids) == len(set(ids))
    rubric = load_rubric()
    assert {c.id for c in rubric.criteria if c.active} | {b.id for b in rubric.blockers} <= set(ids)


def test_welcome_time_and_reward_copy_belongs_to_tone_not_time():
    assert SIGNAL_OF["1.4"] == "tone" and SIGNAL_OF["B5"] == "time"
    out = overview({"1.4": result(0)}, [finding("welcome", "1.4", "worth_improving")])
    assert signal(out, "time")["items"] == []
    assert [i["id"] for i in signal(out, "tone")["items"]] == ["welcome"]
    assert signal(out, "time")["state"] != "worth_improving"


def test_an_open_must_fix_wins_over_full_credit_and_uses_the_new_labels():
    out = overview(honest_passes(), [finding()])
    honest = signal(out, "honest")
    assert honest["state"] == "fix_before_launch"
    assert honest["label"] == "Fix before launch"
    assert honest["findings"] == ["issue"]
    assert [(i["id"], i["state"], i["open"]) for i in honest["items"]] == [("issue", "fix_before_launch", True)]


@pytest.mark.parametrize("decision,expected", [
    ({"action": "keep", "reason": "Required for this study"}, "looks_good"),
    ({"action": "keep", "reason": "  "}, "fix_before_launch"),
    ({"action": "keep"}, "fix_before_launch"),
    ({"action": "pending"}, "fix_before_launch"),
    ({"action": "pick"}, "looks_good"),
    ({"action": "original"}, "looks_good"),
])
def test_only_explicit_decisions_close_an_item(decision, expected):
    out = overview(honest_passes(), [finding()], {"issue": decision})
    assert signal(out, "honest")["state"] == expected


@pytest.mark.parametrize("results", [
    {}, {"3.4": result(assessed=False)}, {"3.4": result(None)},
    {"3.4": result(applies=False)}, {"3.4": {"fraction": 1}},
    {"3.4": {"fraction": 1, "assessed": True}},
])
def test_no_assessed_evidence_has_no_state_and_an_open_finding_is_worth_improving(results):
    clean = signal(overview(results), "clarity")
    assert clean["state"] is None and clean["label"] == "Not checked automatically"
    issue = finding(cid="3.4", severity="worth_improving")
    assert signal(overview(results, [issue]), "clarity")["state"] == "worth_improving"


# --- D2: no positive state without evidence --------------------------------------------------

def test_one_of_seven_checks_never_looks_good():
    tone = signal(overview({"1.1": result()}), "tone")
    assert tone["state"] is None and tone["summary"] == "Not checked automatically."
    assert tone["methodology"]["coverage"]["checked"] == 1


def test_enough_real_evidence_looks_good_and_says_nothing_to_fix():
    clarity = signal(overview({cid: result() for cid in ("3.1", "3.2", "3.3", "3.4")}), "clarity")
    assert clarity["state"] == "looks_good" and clarity["summary"] == "Nothing to fix here."


@pytest.mark.parametrize("decided", [False, True])
@pytest.mark.parametrize("severity", ["must_fix", "worth_improving"])
def test_a_card_whose_summary_names_a_problem_is_never_positive(severity, decided):
    results = {cid: result() for cid in ("3.1", "3.2", "3.3", "3.5")}
    issue = finding("q1", "3.4", severity, headline="Wording problem in Q1")
    decisions = {"q1": {"action": "original"}} if decided else {}
    clarity = signal(overview(results, [issue], decisions), "clarity")
    if "Wording problem" in clarity["summary"]:
        assert clarity["state"] != "looks_good"
    assert (clarity["state"] == "looks_good") is decided


def test_partial_credit_without_any_finding_is_never_a_pass():
    results = {cid: result() for cid in ("3.1", "3.2", "3.3")} | {"3.4": result(.5)}
    assert signal(overview(results), "clarity")["state"] is None


def test_b7_unverified_image_is_you_check_not_improve_and_a_confirmed_one_is_a_fix():
    unverified = finding("img", "B7", "worth_improving", headline="Reader could not verify image loading: Hero")
    assert signal(overview(findings=[unverified]), "phone")["state"] == "you_check"
    tiny = finding("tiny", "B7", "must_fix", headline="Image options are too small to judge (80 px)")
    assert signal(overview(findings=[tiny]), "phone")["state"] == "fix_before_launch"


def test_a_long_choice_list_is_a_you_check_not_a_quick_win():
    long_list = finding("long", "6.2", "worth_improving", headline="10 answer choices; review the phone layout")
    out = overview(findings=[long_list])
    assert signal(out, "phone")["state"] == "you_check"
    assert out["verdict"]["tiles"]["improve"] == 0


def test_a_signal_takes_the_worst_state_among_its_open_items():
    mixed = [finding("a", "3.4", "worth_improving"),
             finding("b", "3.2", "worth_improving", action_kind="you_check", you_check="Does it read well?")]
    assert signal(overview(findings=mixed), "clarity")["state"] == "worth_improving"
    only_check = [mixed[1]]
    assert signal(overview(findings=only_check), "clarity")["state"] == "you_check"


# --- time (D7): duration only, same four states ------------------------------------------------

def test_time_uses_effective_type_targets_and_half_minutes():
    out = overview(snapshot=long_survey())
    time = signal(out, "time")
    assert time["state"] == "worth_improving"
    assert time["summary"] == "About 13½ minutes. Community surveys usually take 5–8 minutes."
    assert out["energy"]["total_seconds"] == 810


@pytest.mark.parametrize("seconds,expected", [(300, "looks_good"), (480, "looks_good"),
                                              (481, "worth_improving")])
def test_time_target_boundaries(seconds, expected):
    # Every whole 3 seconds can be represented by ten words.
    snapshot = survey(page(1, text="word " * int((seconds - 1.5) / .3)), survey_type="community_pulse")
    assert signal(overview(snapshot=snapshot), "time")["state"] == expected


def test_over_target_time_is_never_a_fix_before_launch():
    assert signal(overview(snapshot=long_survey()), "time")["state"] != "fix_before_launch"


def test_branching_disables_the_duration_rule_and_asks_for_a_timed_run():
    out = overview({"2.1": result(0)}, snapshot=long_survey(True))
    time = signal(out, "time")
    assert "Branching makes the total uncertain." in time["summary"]
    assert time["state"] == "you_check"
    assert [i["id"] for i in time["items"]] == [out["you_check"][0]["fingerprint"]]
    assert out["energy"]["path_uncertain"] is True


def test_time_ignores_stale_stored_timing_and_uses_each_survey_types_target():
    snapshot = long_survey().model_copy(update={"survey_type": "ihut"})
    review = {"est_minutes": 1, "timing": {"total_seconds": 60}, "results": {}}
    out = build_overview(snapshot, review, {}, screen_labels(snapshot), {}, load_rubric())
    assert signal(out, "time")["state"] == "looks_good"
    assert signal(out, "time")["summary"] == "About 13½ minutes. Home-use tests usually take 10–15 minutes."
    assert out["energy"]["total_seconds"] == 810


@pytest.mark.parametrize("value,expected", [
    (1, "1 minute"), (13.5, "13½ minutes"), (13.24, "13 minutes"),
    (13.26, "13½ minutes"), (13.75, "14 minutes"), (.5, "½ minute"),
])
def test_half_minute_format(value, expected):
    assert _minutes(value) == expected


# --- strengths, legacy, energy ---------------------------------------------------------------

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
    assert signal(out, "tone")["state"] is None


def test_energy_uses_per_screen_seconds_zones_and_the_shared_state_marker():
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
    assert [s["state"] for s in out["energy"]["screens"]] == ["fix_before_launch", None, None, None]
    assert out["energy"]["heaviest"] == ["p1", "p3", "p2"]
    assert signal(out, "clarity")["pages"] == ["p1"]


def test_unassessed_blocker_concern_is_not_a_pass():
    out = overview({"B2": result(None, assessed=False), "4.2": result()},
                   [finding(question_id="q1")])
    assert signal(out, "honest")["state"] == "fix_before_launch"
    assert signal(out, "honest")["pages"] == ["p1"]


def test_absorbed_concerns_still_disqualify_strengths_not_navigation_or_markers():
    out = overview({"4.2": result()}, [finding(cid="4.2", severity="worth_improving",
                                              absorbed_by="root", page_id="p1")])
    assert out["strengths"] == []
    assert signal(out, "honest")["findings"] == []
    assert signal(out, "honest")["items"] == []
    assert out["energy"]["screens"][0]["state"] is None


def test_worth_improving_marker_and_question_location_take_precedence():
    snapshot = survey(page(1, question(qid="q1")), page(2))
    out = overview(findings=[finding(cid="3.4", severity="worth_improving",
                                    question_id="q1", page_id="p2")], snapshot=snapshot)
    assert [s["state"] for s in out["energy"]["screens"]] == ["worth_improving", None]
    assert signal(out, "clarity")["pages"] == ["p1"]


def test_decided_items_leave_the_screen_markers():
    snapshot = survey(page(1, question(qid="q1", required=True)))
    out = overview(findings=[finding(question_id="q1")], decisions={"issue": {"action": "original"}},
                   snapshot=snapshot)
    assert out["energy"]["screens"][0]["state"] is None
    assert out["items"][0]["open"] is False


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
    first["items"].clear()
    assert args == before


def test_empty_snapshot_and_pure_repeatable_detached_projection():
    snapshot = survey()
    review = {"results": {"3.4": result()}, "findings": []}
    args = (snapshot, review, {}, [], {}, load_rubric())
    before = deepcopy(args)
    out = build_overview(*args)
    assert out["energy"] == {"total_seconds": 0, "path_uncertain": False,
                             "screens": [], "heaviest": []}
    assert args == before
    assert out == build_overview(*args)
    out["signals"][1]["findings"].append("mutation")
    out["strengths"].clear()
    assert args == before


# --- one item list for everything ------------------------------------------------------------

def test_pattern_groups_and_curated_items_are_counted_once_each():
    snapshot = survey(page(1, question("q1", required=True)), page(2, question("q2", required=True)))
    twins = [finding("a", "3.4", "worth_improving", question_id="q1"),
             finding("b", "3.4", "worth_improving", question_id="q2")]
    out = overview(findings=twins, snapshot=snapshot)
    assert len(out["items"]) == 1 and out["items"][0]["count"] == 2
    assert out["items"][0]["fingerprints"] == ["a", "b"]
    assert out["verdict"]["tiles"] == {"fix": 0, "improve": 1, "you_check": 0}


def test_the_overview_headline_and_subline_come_from_the_verdict():
    out = overview(findings=[finding()])
    assert out["headline"] == out["verdict"]["headline"] == "1 thing to fix before launch"
    assert out["subline"] == out["verdict"]["story"]


def test_not_checked_automatically_lists_unassessed_criteria_off_the_curated_list():
    out = overview({"3.4": result()})
    listed = {entry["id"] for entry in out["not_checked_automatically"]}
    assert "3.4" not in listed and "3.1" in listed
    assert all(entry["title"] for entry in out["not_checked_automatically"])
    covered = overview({"2.4": result(assessed=False, fraction=None)},
                       snapshot=survey(page(1, question(required=None))))
    assert "2.4" not in {entry["id"] for entry in covered["not_checked_automatically"]}   # a You check covers it


def test_a_b7_you_check_finding_supersedes_the_curated_images_item_so_images_count_once():
    snapshot = survey(page(1, question(required=True), text="Look."))
    snapshot.pages[0].media = [image()]
    assert [i["id"] for i in overview(snapshot=snapshot)["you_check"]] == ["images"]
    unverified = finding("img", "B7", "worth_improving", headline="Reader could not verify image loading: Hero",
                         page_id="p1")
    out = overview(findings=[unverified], snapshot=snapshot)
    assert out["you_check"] == []
    assert [i["kind"] for i in out["items"]] == ["finding"]
    assert out["verdict"]["tiles"]["you_check"] == 1


def test_partial_credit_explained_only_by_an_absorbed_finding_is_not_a_pass():
    results = honest_passes() | {"4.2": result(.5)}
    absorbed = finding(cid="4.2", severity="worth_improving", absorbed_by="root", page_id="p1")
    card = signal(overview(results, [absorbed]), "honest")
    assert card["items"] == [] and card["state"] is None     # the parent lives elsewhere; this card stays unproven


def test_partial_credit_that_the_user_handled_may_look_good():
    results = honest_passes() | {"4.2": result(.5)}
    issue = finding("kept", cid="4.2", severity="worth_improving")
    decided = {"kept": {"action": "keep", "reason": "On purpose"}}
    assert signal(overview(results, [issue], decided), "honest")["state"] == "looks_good"
    assert signal(overview(results, [issue]), "honest")["state"] == "worth_improving"


# --- time agrees with the verdict once the user has dealt with it ------------------------------

def _duration_fingerprint():
    return overview(snapshot=long_survey())["items"][0]["id"]


def test_keeping_an_over_target_length_on_purpose_settles_the_time_card_and_the_verdict():
    snapshot = long_survey()
    fingerprint = _duration_fingerprint()
    kept = overview(snapshot=snapshot, decisions={fingerprint: {"action": "keep", "reason": "Needed for the study"}})
    assert signal(kept, "time")["state"] == "looks_good"
    assert signal(kept, "time")["summary"] == "About 13½ minutes. Community surveys usually take 5–8 minutes."
    assert kept["verdict"]["tiles"] == {"fix": 0, "improve": 0, "you_check": 0}
    assert kept["verdict"]["time"]["state"] == "worth_improving"     # the measurement itself is unchanged


def test_an_absorbed_length_finding_does_not_hide_the_over_target_item():
    absorbed = finding("len", "2.1", "worth_improving", absorbed_by="root")
    out = overview(findings=[absorbed], snapshot=long_survey())
    assert [i["kind"] for i in signal(out, "time")["items"]] == ["time"]
    assert signal(out, "time")["state"] == "worth_improving"
