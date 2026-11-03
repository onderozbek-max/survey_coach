from dataclasses import replace

from builders import (INTRO_TEXT, context, intro, one_question_survey, page, question, survey, thank_you)

from surveycoach.checks import structure


def run(fn, snapshot):
    return fn(context(snapshot))


def long_text_survey(count: int, required=True, survey_type="non_ihut_product", intro_text=INTRO_TEXT):
    pages = [intro(intro_text)] + [
        page(i + 1, question(f"q{i}", "Tell us more", "text_long", options=(), required=required))
        for i in range(count)
    ] + [thank_you()]
    return survey(*pages, survey_type=survey_type)


# B4 no intro page
def test_b4_flags_a_survey_that_starts_with_questions():
    result = run(structure.no_intro, one_question_survey(question(), with_intro=False))
    assert [f.severity for f in result.findings] == ["must_fix"]


def test_b4_passes_with_an_intro_first():
    assert run(structure.no_intro, one_question_survey(question())).findings == []


# B5 broken time promise
def test_b5_flags_a_calibrated_route_far_longer_than_promised():
    snapshot = long_text_survey(12, intro_text="Thanks! This takes about 2 minutes.")
    ctx = context(snapshot)
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"calibrated": True}))
    assert [f.severity for f in structure.broken_time_promise(ctx).findings] == ["must_fix"]


def test_b5_needs_both_50_percent_and_3_minutes_over():
    snapshot = long_text_survey(4, intro_text="This takes about 2 minutes.")   # ~3.3 min: 65% over but < 3 min over
    ctx = context(snapshot)
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"calibrated": True}))
    assert structure.broken_time_promise(ctx).findings == []
    assert structure.broken_time_promise(ctx).assessed


def test_b5_is_silent_when_no_time_is_promised():
    ctx = context(long_text_survey(12, intro_text="Thanks for helping!"))
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"calibrated": True}))
    assert structure.broken_time_promise(ctx).findings == []
    assert structure.broken_time_promise(ctx).assessed


# B3 late screen-out
def test_b3_flags_a_verified_route_screen_out_after_two_minutes_of_effort():
    pages = [intro()] + [page(i + 1, question(f"q{i}", "Tell us", "text_long", options=())) for i in range(4)]
    pages += [page(5, kind="screen_out", text="Sorry, you don't qualify."), thank_you()]
    ctx = context(survey(*pages))
    # Explicitly verified single route; a raw capture with alternatives cannot prove effort.
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"calibrated": True, "path_uncertain": False}))
    assert any("minutes" in f.explanation for f in structure.late_screen_out(ctx).findings)


def test_b3_flags_a_screen_out_that_does_not_thank_the_member():
    pages = [intro(), page(1, question()), page(2, kind="screen_out", text="You do not qualify."), thank_you()]
    result = run(structure.late_screen_out, survey(*pages))
    assert any("thank" in f.explanation.lower() for f in result.findings)


def test_b3_passes_for_an_early_warm_screen_out():
    pages = [intro(), page(1, question()), page(2, kind="screen_out", text="Thanks for your time!"), thank_you()]
    assert run(structure.late_screen_out, survey(*pages)).findings == []


# 1.4 time and reward stated
def test_1_4_full_credit_when_time_and_reward_are_stated():
    assert run(structure.time_and_reward, one_question_survey(question())).fraction == 1.0


def test_1_4_half_credit_when_the_reward_is_missing():
    snapshot = one_question_survey(question())
    snapshot.pages[0].intro_text = "Thanks! This takes about 5 minutes."
    assert run(structure.time_and_reward, snapshot).fraction == 0.5


def test_1_4_no_credit_when_both_missing():
    snapshot = one_question_survey(question())
    snapshot.pages[0].intro_text = "Welcome to the survey."
    result = run(structure.time_and_reward, snapshot)
    assert result.fraction == 0.0 and len(result.findings) == 1   # one intro rewrite, not two


# 2.1 length fits the type
def test_2_1_bands_by_survey_type():
    short = long_text_survey(2)                                  # about 2 minutes
    assert run(structure.length_fits_type, short).fraction == 1.0
    medium = long_text_survey(7)                                 # ~6 minutes: partial for non-IHUT product (5 to 8)
    assert run(structure.length_fits_type, medium).fraction == 0.6
    huge = long_text_survey(20)
    assert run(structure.length_fits_type, huge).fraction == 0.0


def test_2_1_same_survey_is_fine_as_an_ihut():
    assert run(structure.length_fits_type, long_text_survey(7, survey_type="ihut")).fraction == 1.0


# 2.2 qualifying questions first
def test_2_2_flags_a_screen_out_after_the_third_question():
    pages = [intro()] + [page(i + 1, question(f"q{i}")) for i in range(4)]
    pages += [page(5, kind="screen_out", text="Thanks, but you don't qualify."), thank_you()]
    assert run(structure.screeners_first, survey(*pages)).fraction == 0.0


def test_2_2_passes_when_screening_is_within_three_questions():
    pages = [intro(), page(1, question()), page(2, kind="screen_out", text="Thanks!"), thank_you()]
    assert run(structure.screeners_first, survey(*pages)).fraction == 1.0


# 2.4 typing load
def test_2_4_scales_with_required_open_text():
    assert run(structure.typing_load, long_text_survey(2)).fraction == 1.0
    assert run(structure.typing_load, long_text_survey(3)).fraction == 0.5
    assert run(structure.typing_load, long_text_survey(4)).fraction == 0.0
    assert run(structure.typing_load, long_text_survey(6, required=False)).fraction == 1.0


# 8.2 format variety
def test_8_2_one_format_is_not_enough():
    pages = [intro()] + [page(i + 1, question(f"q{i}")) for i in range(5)] + [thank_you()]
    assert run(structure.format_variety, survey(*pages)).fraction == 0.0


def test_8_2_two_formats_pass_a_short_survey_but_not_a_long_one():
    mixed = lambda n: survey(intro(), *[page(i + 1, question(f"q{i}", kind="single_choice" if i % 2 else "multi_choice"))
                                        for i in range(n)], thank_you())
    assert run(structure.format_variety, mixed(6)).fraction == 1.0
    assert run(structure.format_variety, mixed(10)).fraction == 0.5


# 8.6 room to speak freely
def test_8_6_wants_an_optional_open_comment_near_the_end():
    closing = question("last", "Anything else you'd like the product team to know?", "text_long", options=(), required=False)
    with_comment = survey(intro(), page(1, question()), page(2, closing), thank_you())
    assert run(structure.room_to_speak, with_comment).fraction == 1.0
    assert run(structure.room_to_speak, one_question_survey(question())).fraction == 0.0
    required = closing.model_copy(update={"required": True})
    assert run(structure.room_to_speak, survey(intro(), page(1, required), thank_you())).fraction == 0.0


def test_2_2_is_not_applicable_when_no_screen_out_was_seen():
    assert run(structure.screeners_first, one_question_survey(question())).applies is False
