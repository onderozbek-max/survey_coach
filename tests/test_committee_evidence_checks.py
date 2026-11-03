"""Evidence-only experience and answer-integrity checks, no respondent predictions."""
from builders import context, intro, page, question, scale, survey
from surveycoach.checks import run_all
from surveycoach.snapshot import Option


def results(*questions):
    return run_all(context(survey(intro(), *[page(i + 1, q) for i, q in enumerate(questions)])))


def test_unknown_none_and_other_semantics_are_not_invented():
    q = question(kind="multi_choice", options=("A", "None of these", "Other"))
    got = results(q)
    assert not got.get("4.1", None) or not got["4.1"].findings
    assert not got.get("4.3", None) or not got["4.3"].findings
    assert q.options[-1].is_other_with_text is None
    assert q.options[-2].is_exclusive is None


def test_explicit_nonexclusive_none_is_flagged_with_exact_option_evidence():
    q = question(kind="multi_choice", options=())
    q.options = [Option(id="a", label="A"), Option(id="none", label="None of these", is_exclusive=False)]
    found = results(q)["4.1"].findings
    assert len(found) == 1 and found[0].evidence == "None of these"
    assert found[0].question_id == q.id


def test_explicit_other_without_text_is_flagged_but_other_with_text_is_not():
    q = question(options=())
    q.options = [Option(id="o", label="Other (please specify)", is_other_with_text=False)]
    assert results(q)["4.3"].findings
    q.options[0].is_other_with_text = True
    assert not results(q)["4.3"].findings


def test_other_alone_is_a_valid_category_not_a_mandatory_write_in():
    q = question(options=())
    q.options = [Option(id="o", label="Other", is_other_with_text=False)]
    assert not results(q)["4.3"].findings


def test_obvious_placeholder_is_a_grounded_blocker_not_any_word_test():
    bad = question(text="TODO: INSERT QUESTION HERE", options=("Option 1", "Option 2"))
    got = results(bad)
    assert got["B2"].findings[0].severity == "must_fix"
    assert got["B2"].findings[0].evidence == bad.text
    assert not results(question(text="How did the product test go?"))["B2"].findings


def test_five_repeated_scales_report_one_grounded_pattern_not_a_prediction():
    qs = [question(f"q{i}", kind="rating", text=f"How would you rate item {i}?", scale=scale()) for i in range(5)]
    got = results(*qs)["8.5"]
    assert len(got.findings) == 1
    f = got.findings[0]
    assert "5" in f.headline and f.evidence == qs[0].text
    assert not any(word in f.member_impact.lower() for word in ("drop-off", "%", "will quit"))


def test_short_scale_run_is_not_a_monotony_finding():
    qs = [question(f"q{i}", kind="rating", scale=scale()) for i in range(3)]
    assert not results(*qs)["8.5"].findings


def test_three_back_to_back_open_ends_have_one_actionable_pattern():
    qs = [question(f"q{i}", kind="text_long", options=()) for i in range(3)]
    found = results(*qs)["8.5"].findings
    assert len(found) == 1 and "3" in found[0].headline
    assert found[0].question_id == qs[0].id


def test_large_total_grid_load_is_counted_without_straightlining_claims():
    qs = [question(f"q{i}", kind="grid_single", rows=[f"Attribute {r}" for r in range(5)]) for i in range(4)]
    found = results(*qs)["8.5"].findings
    assert any("20" in f.headline and "row" in f.headline.lower() for f in found)


def test_conditional_questions_do_not_form_a_fake_consecutive_run():
    qs = [question(f"q{i}", kind="text_long", options=(), conditional=True) for i in range(4)]
    assert not results(*qs)["8.5"].findings
