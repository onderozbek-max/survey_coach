import json
from pathlib import Path

from surveycoach.demo_export import SITE_DATA, build_demo_data, render_data_js
from surveycoach.judge.grounding import norm

ROOT = Path(__file__).parent.parent


def parsed() -> dict:
    prefix = "window.SURVEYCOACH_DEMO = "
    text = render_data_js(build_demo_data())
    assert text.startswith(prefix) and text.rstrip().endswith(";")
    return json.loads(text[len(prefix):].rstrip().rstrip(";"))


def test_committed_site_data_is_not_stale():
    assert SITE_DATA.read_text() == render_data_js(build_demo_data()), \
        "Run: .venv/bin/python -m surveycoach.demo_export"


def test_data_js_is_pure_ascii_so_no_literal_emoji_in_any_file():
    assert render_data_js(build_demo_data()).isascii()


def test_both_samples_with_reviews_and_snapshots():
    data = parsed()
    assert [s["id"] for s in data["surveys"]] == ["boxer-briefs", "coffee-pods"]
    boxer = data["surveys"][0]
    assert boxer["review"]["scorecard"]["readiness"] == "needs_work"
    assert boxer["review"]["findings"][0]["severity"] == "must_fix"
    assert boxer["snapshot"]["pages"][0]["kind"] == "intro"


def test_criteria_lookup_covers_every_finding_so_the_page_can_name_them():
    data = parsed()
    cited = {f["criterion_id"] for s in data["surveys"] for f in s["review"]["findings"]}
    assert cited <= set(data["criteria"])
    assert data["criteria"]["6.3"]["title"]


def test_demo_says_it_is_sample_data_that_changes_nothing_in_redjade():
    disclaimer = parsed()["disclaimer"].lower()
    assert "sample" in disclaimer and "redjade" in disclaimer


def test_every_sample_replays_its_ai_answers_from_the_committed_cache():
    for survey in parsed()["surveys"]:
        ai = survey["review"]["ai"]
        assert ai and ai["failed"] == {} and ai["from_cache"] == ai["checked"] == ["wording", "story", "flow"], \
            f"{survey['id']}: refresh with .venv/bin/python -m surveycoach.demo_export --ai-refresh  ({ai and ai['failed']})"


def test_exported_findings_carry_their_source_and_rewrite_options_and_the_model_name():
    boxer = parsed()["surveys"][0]["review"]
    assert boxer["ai"]["model"] == "gpt-6.1-sol"
    ai_findings = [f for f in boxer["findings"] if f["source"] == "ai"]
    assert ai_findings and any(len(f["options"]) == 3 for f in ai_findings)
    assert all(f["headline"] and f["evidence"] for f in ai_findings)


def test_the_demo_build_can_never_call_the_network():
    from surveycoach.demo_export import CacheOnlyProvider
    from surveycoach.judge.schemas import Answer
    from surveycoach.llm import LlmError
    import pytest
    with pytest.raises(LlmError, match="ai-refresh"):
        CacheOnlyProvider().complete_json("s", "d", Answer)


def test_every_ai_finding_in_the_demo_is_grounded_in_the_sample_survey():
    """Belt and braces on the human-reviewed cache: each quote really is in the survey it is attached to."""
    from surveycoach.judge.grounding import locate, quote_is_real
    from surveycoach.snapshot import SurveySnapshot
    for survey in parsed()["surveys"]:
        snapshot = SurveySnapshot.model_validate_json((ROOT / "fixtures" / f"{survey['id']}.json").read_text())
        for f in survey["review"]["findings"]:
            if f["source"] != "ai":
                continue
            text, _ = locate(snapshot, f["page_id"], f["question_id"])
            if f["criterion_id"] == "1.1":
                text += " " + snapshot.title
            assert quote_is_real(f["evidence"], text), (survey["id"], f["criterion_id"], f["evidence"])


def _ai_findings(survey):
    return [f for f in survey["review"]["findings"] if f["source"] == "ai"]


def test_no_text_is_offered_two_competing_ai_rewrites():
    for survey in parsed()["surveys"]:
        rewritten = [norm(f["current_text"]) for f in _ai_findings(survey) if f["current_text"] and f["options"]]
        assert len(rewritten) == len(set(rewritten)), survey["id"]


def test_an_ai_finding_never_repeats_a_blocker_with_the_same_root_problem():
    for survey in parsed()["surveys"]:
        findings = _ai_findings(survey)
        blocked = {(f["question_id"] or f["page_id"], norm(f["evidence"]), norm(f['headline'])) for f in findings if f["criterion_id"].startswith("B")}
        repeats = [f["criterion_id"] for f in findings
                   if not f["criterion_id"].startswith("B") and (f["question_id"] or f["page_id"], norm(f["evidence"]), norm(f['headline'])) in blocked]
        assert repeats == [], (survey["id"], repeats)


def test_every_multi_line_rewrite_is_marked_copy_only():
    for survey in parsed()["surveys"]:
        for f in _ai_findings(survey):
            bundled = any("\n" in t for t in [f["suggested_text"] or "", *[o["text"] for o in f["options"]]])
            assert f["structural"] is bundled, (survey["id"], f["criterion_id"])
