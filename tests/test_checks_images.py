import pytest
from builders import context, image, intro, one_question_survey, page, question, survey, thank_you
from PIL import Image, ImageFilter

from surveycoach.checks import images
from surveycoach.findings import CheckResult
from surveycoach.imageio import analyze_image
from surveycoach.rubric import load_rubric
from surveycoach.scoring import score
from surveycoach.snapshot import Option


def run(fn, snapshot):
    return fn(context(snapshot))


def with_image(media, **q_extra):
    return one_question_survey(question(media=[media], **q_extra))


# "applies" flag
def test_not_applicable_is_excluded_from_earned_and_unchecked_points_and_strengths():
    results = {"7.2": CheckResult(criterion_id="7.2", applies=False)}
    card = score(load_rubric(), results)
    assert card.score == 0 and card.unchecked_points == 100 - 3
    assert card.not_applicable_points == 3 and card.checked_points == 0
    assert card.provisional  # Other criteria still await assessment.
    assert "Phone-friendly shape" not in card.strengths


# 7.2 shape
@pytest.mark.parametrize("natural,expected", [((1000, 1000), 1.0), ((800, 1000), 1.0), ((1000, 1250), 1.0),
                                              ((1200, 1000), 1 / 3), ((1000, 1500), 1 / 3),
                                              ((1600, 900), 0.0), ((1000, 700), 0.0)])
def test_7_2_shape_bands(natural, expected):
    result = run(images.phone_friendly_shape, with_image(image(natural=natural, rendered=(349, 349))))
    assert result.fraction == pytest.approx(expected)


def test_7_2_is_scored_on_worst_shape_but_requires_mobile_review_not_auto_crop():
    good, bad = image(natural=(1000, 1000)), image(natural=(1600, 900))
    snapshot = survey(intro(), page(1, question(media=[good]), ), page(2, question("b", media=[bad])), thank_you())
    result = run(images.phone_friendly_shape, snapshot)
    assert result.fraction == 0.0
    finding = result.findings[0]
    assert "potential" in finding.headline.lower()
    assert "mobile device" in finding.explanation
    assert "does not prove" in finding.explanation
    assert "Crop it" not in finding.explanation


def test_7_2_not_applicable_without_images():
    assert run(images.phone_friendly_shape, one_question_survey(question())).applies is False


# 7.3 sharp and high resolution
def test_7_3_flags_low_resolution_full_width_images():
    assert run(images.sharp_and_high_res, with_image(image(natural=(500, 500), rendered=(349, 349)))).fraction == 0.0


def test_7_3_flags_stretched_images_but_not_deliberate_crops():
    stretched = image(natural=(1000, 1000), rendered=(349, 200))
    assert run(images.sharp_and_high_res, with_image(stretched)).fraction == 0.0
    cropped = image(natural=(1000, 1000), rendered=(349, 200), object_fit="cover")
    assert run(images.sharp_and_high_res, with_image(cropped)).fraction == 1.0


def test_7_3_passes_a_crisp_image():
    assert run(images.sharp_and_high_res, with_image(image(natural=(1200, 1200), rendered=(349, 349)))).fraction == 1.0


def test_7_3_uses_the_blur_score_when_the_file_is_available(tmp_path):
    sharp = Image.effect_noise((600, 600), 80).convert("RGB")
    sharp_path, blurry_path = tmp_path / "sharp.png", tmp_path / "blurry.png"
    sharp.save(sharp_path)
    sharp.filter(ImageFilter.GaussianBlur(12)).save(blurry_path)
    assert analyze_image(sharp_path).blur_score > analyze_image(blurry_path).blur_score * 5
    blurry = image(natural=(1200, 1200), asset_path=str(blurry_path))
    assert run(images.sharp_and_high_res, with_image(blurry)).fraction == 0.0
    crisp = image(natural=(1200, 1200), asset_path=str(sharp_path))
    assert run(images.sharp_and_high_res, with_image(crisp)).fraction == 1.0


def test_analyze_image_reads_facts(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGBA", (40, 20), (255, 0, 0, 0)).save(path)
    facts = analyze_image(path)
    assert (facts.width, facts.height, facts.has_alpha, facts.format) == (40, 20, True, "PNG")
    assert facts.bytes > 0


# 7.5 fair image choices
def choice_with_images(*media, labels=None):
    options = [Option(id=f"o{i}", label=(labels[i] if labels else f"Option {i}"), media=m) for i, m in enumerate(media)]
    return one_question_survey(question("c", "Which pack do you prefer?", "image_choice", options=()).model_copy(
        update={"options": options}))


def test_7_5_flags_mismatched_shapes_missing_labels_and_too_many_options():
    a, b = image(natural=(1000, 1000)), image(natural=(1600, 900))
    assert run(images.fair_image_choices, choice_with_images(a, b)).fraction == 0.0
    same = [image(natural=(1000, 1000)) for _ in range(2)]
    assert run(images.fair_image_choices, choice_with_images(*same, labels=["", "Pack B"])).fraction == 0.0
    seven = [image(natural=(1000, 1000)) for _ in range(7)]
    assert run(images.fair_image_choices, choice_with_images(*seven)).fraction == 0.0


def test_7_5_passes_matched_labeled_options():
    same = [image(natural=(1000, 1000)) for _ in range(4)]
    assert run(images.fair_image_choices, choice_with_images(*same)).fraction == 1.0


def test_7_5_not_applicable_without_image_choices():
    assert run(images.fair_image_choices, with_image(image())).applies is False


# 7.6 light and accessible
def test_7_6_flags_heavy_images_missing_alt_and_heavy_surveys():
    assert run(images.light_and_accessible, with_image(image(bytes=700_000))).fraction < 1.0
    assert run(images.light_and_accessible, with_image(image(alt=None))).fraction < 1.0
    heavy = survey(intro(), *[page(i + 1, question(f"q{i}", media=[image(bytes=450_000)])) for i in range(12)], thank_you())
    assert any("5 MB" in f.explanation for f in run(images.light_and_accessible, heavy).findings)


def test_7_6_passes_light_described_images():
    assert run(images.light_and_accessible, with_image(image(bytes=120_000, alt="Boxer briefs, navy"))).fraction == 1.0


# B7 members can't see what they judge
def test_b7_unloaded_capture_is_unverified_not_a_confirmed_blocker():
    snapshot = with_image(image(loaded=False))
    checked = run(images.cannot_see_image, snapshot)
    assert [f.severity for f in checked.findings] == ["worth_improving"]
    assert checked.assessed is False


def test_b7_flags_images_too_small_to_judge_in_image_choice():
    tiny = [image(natural=(1000, 1000), rendered=(60, 60)) for _ in range(2)]
    assert run(images.cannot_see_image, choice_with_images(*tiny)).findings


def test_b7_passes_normal_images():
    assert run(images.cannot_see_image, with_image(image())).findings == []
