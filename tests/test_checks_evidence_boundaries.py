"""Audit 3, 5, 14, 15: a check may only claim what its evidence supports.

Each case is a synthetic reproduction from docs/superpowers/internal-audit-2026-11-04.md.
"""
import pytest
from builders import context, one_question_survey, question

from surveycoach.checks import answers, images
from surveycoach.snapshot import Media


def run(fn, snapshot):
    return fn(context(snapshot))


def choice(*labels, text="Which describes you?", **extra):
    return one_question_survey(question(text=text, options=labels, **extra))


def loaded(**extra):
    return Media(loaded=True, alt=extra.pop("alt", "A product"), **extra)


# Audit 3: a continuous range rewrite must never leave uncovered values.
def test_continuous_money_ranges_never_get_an_integer_gap_rewrite():
    result = run(answers.no_overlap, choice("0 to 10 dollars", "10 to 20 dollars", text="How much do you spend?"))
    assert result.findings, "the shared boundary is still a real overlap"
    assert all(f.suggested_text is None for f in result.findings)
    assert "9" not in " ".join(f.suggested_text or "" for f in result.findings)
    assert "under" in result.findings[0].explanation.lower() or "exclusive" in result.findings[0].explanation.lower()


@pytest.mark.parametrize("labels,expected", [
    (("1 to 5 years", "5 to 10 years"), "1 to 4 years"),
    (("1 to 3 days", "3 to 7 days"), "1 to 2 days"),
    (("1-4 times", "4-8 times"), "1-3 times"),
])
def test_clearly_integral_units_still_get_a_verified_rewrite(labels, expected):
    result = run(answers.no_overlap, choice(*labels))
    assert result.findings[0].suggested_text == expected


def test_unit_less_boundaries_are_not_assumed_integral():
    result = run(answers.no_overlap, choice("0 to 10", "10 to 20", text="What is the price?"))
    assert result.findings and result.findings[0].suggested_text is None


def test_question_wording_can_establish_a_count():
    result = run(answers.no_overlap, choice("1 to 4", "4 to 8", text="How many children do you have?"))
    assert result.findings[0].suggested_text == "1 to 3"


# Audit 15: unrelated numeric phrases are not competing ranges.
def test_ranges_in_different_units_are_not_judged():
    result = run(answers.no_overlap, choice("A 1 to 2 day delivery", "A 1 to 2 year warranty",
                                            text="Which features do you want?", kind="multi_choice"))
    assert result.findings == []


def test_same_numbers_with_different_quantities_do_not_overlap():
    result = run(answers.no_overlap, choice("1 to 2 day delivery", "2 to 3 day shipping"))
    assert result.findings == []


def test_same_quantity_still_overlaps():
    result = run(answers.no_overlap, choice("1 to 2 day delivery", "2 to 3 day delivery"))
    assert len(result.findings) == 1 and result.fraction == 0.0


# Audit 5: unknown evidence is unknown, never full credit.
def unknown_image_survey(**media):
    return one_question_survey(question(media=[loaded(**media)]))


def test_7_3_without_any_dimensions_is_unassessed_not_full_credit():
    result = run(images.sharp_and_high_res, unknown_image_survey())
    assert result.assessed is False and result.fraction is None


def test_7_3_with_only_natural_size_is_unassessed():
    assert run(images.sharp_and_high_res, unknown_image_survey(natural_w=900, natural_h=900)).assessed is False


def test_7_3_keeps_findings_it_can_evaluate_but_not_the_clear():
    known = loaded(natural_w=400, natural_h=400, rendered_w=349, rendered_h=349)
    unknown = loaded()
    snapshot = one_question_survey(question(media=[known, unknown]))
    result = run(images.sharp_and_high_res, snapshot)
    assert result.assessed is False
    assert [f.headline for f in result.findings] == ["Image is too small to show full width"]


def test_7_3_with_full_evidence_is_still_assessed():
    result = run(images.sharp_and_high_res, unknown_image_survey(natural_w=1200, natural_h=1200,
                                                                 rendered_w=349, rendered_h=349))
    assert result.assessed and result.fraction == 1.0


def test_7_6_unknown_bytes_is_unassessed_even_with_alt_text():
    result = run(images.light_and_accessible, unknown_image_survey(alt="Synthetic product"))
    assert result.assessed is False and result.fraction is None


def test_7_6_still_reports_missing_alt_text_when_bytes_are_unknown():
    result = run(images.light_and_accessible, unknown_image_survey(alt=""))
    assert result.assessed is False
    assert [f.headline for f in result.findings] == ["Image has no alt text"]


def test_7_6_with_known_bytes_is_assessed():
    result = run(images.light_and_accessible, unknown_image_survey(bytes=90_000))
    assert result.assessed and result.fraction == 1.0


# Audit 14: display-size inequality comes from rendered size, never source resolution.
def image_choice(*dims):
    q = question(kind="image_choice", text="Pick an image", options=("A", "B")[:len(dims)])
    for option, (natural, rendered) in zip(q.options, dims):
        option.media = loaded(alt=option.label, natural_w=natural, natural_h=natural,
                              rendered_w=rendered, rendered_h=rendered, bytes=100_000)
    return one_question_survey(q)


def headlines(result):
    return [f.headline for f in result.findings]


def test_7_5_equal_display_with_different_source_resolution_is_fine():
    result = run(images.fair_image_choices, image_choice((1000, 150), (2000, 150)))
    assert "Image options differ a lot in size" not in headlines(result)
    assert result.assessed and result.fraction == 1.0


def test_7_5_unequal_rendered_size_is_flagged():
    result = run(images.fair_image_choices, image_choice((1000, 300), (1000, 150)))
    assert "Image options differ a lot in size" in headlines(result)


def test_7_5_missing_rendered_layout_is_unassessed_not_guessed():
    result = run(images.fair_image_choices, image_choice((1000, None), (2000, None)))
    assert result.assessed is False
    assert "Image options differ a lot in size" not in headlines(result)


def test_7_5_partial_rendered_layout_is_unassessed():
    result = run(images.fair_image_choices, image_choice((1000, 150), (2000, None)))
    assert result.assessed is False


def test_7_5_unrelated_problems_survive_when_layout_is_unknown():
    snapshot = image_choice((1000, None), (2000, None))
    snapshot.pages[1].questions[0].options[0].label = " "
    result = run(images.fair_image_choices, snapshot)
    assert "Image option has no label" in headlines(result) and result.assessed is False

