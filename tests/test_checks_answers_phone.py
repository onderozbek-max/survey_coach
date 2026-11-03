from builders import context, intro, one_question_survey, page, question, scale, survey, thank_you

from surveycoach.checks import answers, phone

AGREE = ("Strongly agree", "Agree", "Neither agree nor disagree", "Disagree", "Strongly disagree")


def run(fn, snapshot):
    return fn(context(snapshot))


def single(q):
    return one_question_survey(q)


# 4.2 overlapping choices
def test_4_2_flags_ranges_that_share_an_endpoint():
    q = question(text="How long have you owned it?", options=("1 to 5 years", "5 to 10 years", "Over 10 years"))
    result = run(answers.no_overlap, single(q))
    assert result.fraction == 0.0
    assert "1 to 5 years" in result.findings[0].evidence and "5 to 10 years" in result.findings[0].evidence


def test_4_2_passes_clean_ranges():
    q = question(text="Age?", options=("Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65 or older"))
    assert run(answers.no_overlap, single(q)).fraction == 1.0


def test_4_2_handles_open_ended_boundaries():
    clean = question(options=("Less than 5", "5 to 10", "More than 10"))
    assert run(answers.no_overlap, single(clean)).fraction == 1.0
    overlapping = question(options=("10 or more", "At least 5", "Under 5"))
    assert run(answers.no_overlap, single(overlapping)).fraction == 0.0


def test_4_2_ignores_non_numeric_choices():
    assert run(answers.no_overlap, single(question())).fraction == 1.0


# 4.4 honest scales
def rating(scale_obj, qid="r1"):
    return question(qid, "How satisfied were you?", "rating", options=(), scale=scale_obj)


def test_4_4_passes_a_labeled_balanced_scale():
    labels = ["Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied"]
    assert run(answers.honest_scales, single(rating(scale(5, "Very dissatisfied", "Very satisfied", labels)))).fraction == 1.0


def test_4_4_flags_missing_end_labels():
    result = run(answers.honest_scales, single(rating(scale(5, None, None))))
    assert result.fraction == 0.5
    assert "labeled" in result.findings[0].explanation


def test_4_4_flags_unbalanced_labels():
    labels = ["Poor", "Good", "Very good", "Great", "Excellent"]
    result = run(answers.honest_scales, single(rating(scale(5, "Poor", "Excellent", labels))))
    assert result.fraction == 0.5 and "balanced" in result.findings[0].explanation


def test_4_4_flags_a_flipped_direction_between_questions():
    first = rating(scale(5, "Very dissatisfied", "Very satisfied"), "r1")
    flipped = rating(scale(5, "Very satisfied", "Very dissatisfied"), "r2")
    snapshot = survey(intro(), page(1, first), page(2, flipped), thank_you())
    result = run(answers.honest_scales, snapshot)
    assert result.fraction == 0.5 and "direction" in result.findings[0].explanation


# 5.4 wall of agree/disagree
def agree_question(i):
    return question(f"a{i}", "The package was easy to open.", "single_choice", options=AGREE)


def test_5_4_flags_four_agree_scales_in_a_row():
    snapshot = survey(intro(), *[page(i + 1, agree_question(i)) for i in range(4)], thank_you())
    assert run(answers.agree_wall, snapshot).fraction == 0.0


def test_5_4_allows_three_and_resets_after_a_different_question():
    run_of_three = [page(i + 1, agree_question(i)) for i in range(3)]
    snapshot = survey(intro(), *run_of_three, page(4, question("x")), page(5, agree_question(9)), thank_you())
    assert run(answers.agree_wall, snapshot).fraction == 1.0


# 6.1 fits on one screen
def test_6_1_flags_long_question_text():
    long_text = " ".join(["word"] * 40) + "?"
    result = run(phone.fits_one_screen, single(question(text=long_text)))
    assert result.fraction == 0.0 and "40 words" in result.findings[0].evidence


def test_6_1_flags_answers_below_the_fold():
    q = question(options_below_fold=1, fits_one_screen=False)
    assert run(phone.fits_one_screen, single(q)).fraction == 0.0


def test_6_1_flags_two_questions_on_one_page():
    snapshot = survey(intro(), page(1, question("a"), question("b")), thank_you())
    assert run(phone.fits_one_screen, snapshot).fraction == 0.0


def test_6_1_proportional_credit():
    snapshot = survey(intro(), page(1, question("a")), page(2, question("b", options_below_fold=2, fits_one_screen=False)),
                      thank_you())
    assert run(phone.fits_one_screen, snapshot).fraction == 0.5


# 6.2 tappable answers
def test_6_2_flags_long_labels_and_too_many_choices():
    wordy = question(options=("x" * 61, "Short"))
    assert run(phone.tappable_answers, single(wordy)).fraction == 0.0
    many = question(options=tuple(f"Choice {i}" for i in range(9)))
    assert run(phone.tappable_answers, single(many)).fraction == 0.0


def test_6_2_flags_a_dropdown_with_a_short_list():
    result = run(phone.tappable_answers, single(question(kind="dropdown", options=("A", "B", "C"))))
    assert result.fraction == 0.0 and "buttons" in result.findings[0].explanation


def test_6_2_passes_short_button_lists():
    assert run(phone.tappable_answers, single(question())).fraction == 1.0


# 6.3 grids and scales
def test_6_3_flags_big_grids_and_long_scales():
    grid = question("g", "Rate each", "grid_single", options=(), rows=[f"row {i}" for i in range(6)], scale=scale(5))
    assert run(phone.small_grids, single(grid)).fraction == 0.0
    wide = question("g", "Rate each", "grid_single", options=(), rows=["a", "b"], scale=scale(7))
    assert run(phone.small_grids, single(wide)).fraction == 0.0   # 7 columns exceeds 5
    eleven = question("s", "How likely?", "rating", options=(), scale=scale(11))
    assert run(phone.small_grids, single(eleven)).fraction == 0.0


def test_6_3_passes_small_grids():
    grid = question("g", "Rate each", "grid_single", options=(), rows=["a", "b", "c"], scale=scale(5))
    assert run(phone.small_grids, single(grid)).fraction == 1.0


# 6.4 thumb friendly
def test_6_4_flags_desktop_words_but_not_unobserved_ranking_defects():
    assert run(phone.thumb_friendly, single(question(text="Click the one you like best."))).fraction == 0.0
    assert run(phone.thumb_friendly, single(question(text="Choose the option on the left."))).fraction == 0.0
    ranking = question("r", "Rank these", "ranking")
    result = run(phone.thumb_friendly, single(ranking))
    assert result.fraction == 1.0 and result.findings == []


def test_6_4_passes_tap_language():
    assert run(phone.thumb_friendly, single(question(text="Tap the one you like best."))).fraction == 1.0


# 6.5 stays put and renders cleanly
def test_6_5_flags_outbound_links_and_truncated_text():
    snapshot = survey(intro(), page(1, question(), links_out=["https://example.com/terms"]), thank_you())
    assert run(phone.stays_put, snapshot).fraction < 1.0
    truncated = single(question(text="Which of these flavors do you pref..."))
    assert run(phone.stays_put, truncated).fraction < 1.0


def test_6_5_passes_a_clean_survey():
    assert run(phone.stays_put, single(question())).fraction == 1.0


def test_negated_labels_are_negative():
    from surveycoach.checks.answers import polarity
    assert polarity("Not at all likely") == -1
    assert polarity("Never") == -1
    assert polarity("Very likely") == 1
    assert polarity("Strongly disagree") == -1


def test_4_4_does_not_flip_direction_for_negated_low_labels():
    disagree = rating(scale(5, "Strongly disagree", "Strongly agree"), "r1")
    unlikely = rating(scale(5, "Not at all likely", "Extremely likely"), "r2")
    snapshot = survey(intro(), page(1, disagree), page(2, unlikely), thank_you())
    assert run(answers.honest_scales, snapshot).fraction == 1.0
