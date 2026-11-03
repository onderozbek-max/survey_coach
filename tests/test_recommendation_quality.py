"""Recommendations must be usable wording, not homework disguised as a rewrite."""
import json

import pytest

from surveycoach.findings import Finding, RewriteOption
from surveycoach.judge.batches import STORY
from surveycoach.judge.grounding import ground
from surveycoach.judge.prompts import PROMPT_VERSION, system_prompt
from surveycoach.judge.schemas import AiFinding, BatchOutput, Verdict
from surveycoach.rubric import load_rubric
from surveycoach.server.repository import Repository
from tests.builders import intro, survey

ORIGINAL = "Welcome to our survey!"
EXPLANATION = "State the research purpose after confirming it with the study owner."


def raw_finding(**updates):
    return AiFinding(**(dict(
        criterion_id="1.1", page_id="p0", headline="The purpose is missing",
        evidence=ORIGINAL, current_text=ORIGINAL, explanation=EXPLANATION,
        member_impact="Members cannot tell what their answers will inform.",
        suggested_text="Help us learn [what you want to learn].",
        options=[RewriteOption(label="Neutral", text="Help us learn [research purpose].")],
    ) | updates))


def grounded(raw):
    output = BatchOutput(verdicts=[Verdict(criterion_id="1.1", fraction=0.5)], findings=[raw])
    return ground(output, STORY, survey(intro(raw.evidence)), load_rubric()).results["1.1"]


@pytest.mark.parametrize("template", [
    "Help us learn [what you want to learn].", "Tell us about [product name].",
    "Your feedback will inform [decision].", "Welcome, [insert audience here].",
    "Learn about [topic] in [timeframe].", "You'll receive [X] points.",
    "Help improve {product_name}.", "Help us learn <insert research purpose>.",
    "Help us understand [specific behavior].", "Learn about [brief description].",
])
def test_template_rewrites_become_explanation_only_without_losing_the_finding(template):
    result = grounded(raw_finding(suggested_text=template, options=[RewriteOption(label="Neutral", text=template)]))
    finding = result.findings[0]
    assert result.fraction == 0.5
    assert finding.suggested_text is None
    assert finding.options == []
    assert finding.evidence == ORIGINAL and finding.current_text == ORIGINAL
    assert finding.explanation.startswith(EXPLANATION)
    assert "No ready-to-use rewrite" in finding.explanation
    assert "context" in finding.explanation


def test_bad_options_are_removed_but_grounded_concrete_alternatives_survive():
    good = "Welcome! Please share your feedback."
    finding = grounded(raw_finding(options=[
        RewriteOption(label="Neutral", text="Tell us about [topic]."),
        RewriteOption(label="Shorter", text=good),
    ])).findings[0]
    assert finding.suggested_text == good
    assert [o.text for o in finding.options] == [good]
    assert finding.explanation == EXPLANATION


@pytest.mark.parametrize("rewrite", [
    "Rate your experience on [0-10].", "Choose a value in [0, 10].",
    "Choose a value in [-1.5, +2.5].", "Rate the item marked [A].",
])
def test_numeric_notation_and_brackets_quoted_from_the_original_are_not_templates(rewrite):
    original = "Please rate the item marked [A] on a scale."
    finding = grounded(raw_finding(evidence=original, current_text=original,
                                  suggested_text=rewrite, options=[])).findings[0]
    assert finding.suggested_text == rewrite
    assert finding.explanation == EXPLANATION


def test_original_template_evidence_is_preserved_but_not_offered_as_replacement():
    original = "Welcome! We want to learn [research purpose]."
    finding = grounded(raw_finding(evidence=original, current_text=original,
                                  suggested_text="Tell us about [research purpose].",
                                  options=[])).findings[0]
    assert finding.evidence == original and finding.current_text == original
    assert finding.suggested_text is None


def test_guard_preserves_valid_suggestion_when_all_options_are_templates():
    from surveycoach.recommendations import guard_recommendation

    concrete = "Welcome! Please share your feedback."
    original = raw_finding(suggested_text=concrete).model_dump()
    cleaned = guard_recommendation(original)
    assert cleaned["suggested_text"] == concrete and cleaned["options"] == []
    assert cleaned["explanation"] == EXPLANATION
    assert original["options"]  # input is not mutated
    assert guard_recommendation(cleaned) == cleaned


def test_guard_explanation_is_idempotent_when_only_options_contain_templates():
    from surveycoach.recommendations import guard_recommendation

    original = raw_finding(suggested_text=None).model_dump()
    cleaned = guard_recommendation(original)
    assert cleaned["suggested_text"] is None and cleaned["options"] == []
    assert cleaned["explanation"].count("No ready-to-use rewrite") == 1
    assert guard_recommendation(cleaned) == cleaned


def test_saved_reviews_are_guarded_on_read_without_rewriting_stored_history():
    repository = Repository(":memory:")
    try:
        submitted = repository.submit(survey(intro(ORIGINAL)), ai=True)
        finding = Finding(**raw_finding().model_dump(), source="ai").model_dump()
        finding["fingerprint"] = "stable-id"
        payload = {"review": {"findings": [finding], "scorecard": {"readiness": "almost_ready"}}}
        repository.finish(submitted["job_id"], payload)
        legacy_decision = {"action": "pick", "picked_text": finding["suggested_text"], "manual_done": True}
        repository.db.execute("INSERT INTO decisions(survey_id,version,fingerprint,data) VALUES (?,?,?,?)",
                              (submitted["id"], 1, "stable-id", json.dumps(legacy_decision)))
        repository.db.commit()
        detail = repository.detail(submitted["id"])
        assert detail["decisions"]["stable-id"]["action"] == "open"
        assert detail["decisions"]["stable-id"]["picked_text"] is None
        saved = detail["review"]["findings"][0]
        assert saved["suggested_text"] is None and saved["options"] == []
        assert saved["fingerprint"] == "stable-id" and saved["evidence"] == ORIGINAL
        assert "No ready-to-use rewrite" in saved["explanation"]
        assert repository.detail(submitted["id"])["review"] == detail["review"]
        stored = json.loads(repository.db.execute("SELECT data FROM reviews").fetchone()[0])
        assert stored == payload
        with pytest.raises(ValueError, match="saved suggestions"):
            repository.save_decision(submitted["id"], 1, "stable-id", {
                "action": "pick", "picked_text": finding["suggested_text"],
            })
    finally:
        repository.close()


@pytest.mark.parametrize('text', ['Your feedback will inform [intended outcome].',
                                'Your answers will help us [confirmed use of answers].'])
def test_ambiguous_bracketed_prose_is_never_copyable(text):
    from surveycoach.recommendations import guard_recommendation
    cleaned = guard_recommendation({'suggested_text': text, 'options': [], 'explanation': 'Clarify the goal.'})
    assert cleaned['suggested_text'] is None


def test_prompt_requires_grounded_ready_to_use_wording_or_an_action_not_templates():
    prompt = system_prompt(STORY, load_rubric())
    assert PROMPT_VERSION != "4"
    assert "ready-to-use" in prompt
    assert "no rewrite" in prompt
    assert "Never use" in prompt and "placeholder" in prompt
    assert "fact in square brackets" not in prompt
