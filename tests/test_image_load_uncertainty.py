"""A capture observation is not evidence of a vendor or member-network defect."""
from builders import context, image, one_question_survey, question
from surveycoach.checks.images import cannot_see_image, phone_friendly_shape


def test_unloaded_image_is_scoped_to_reader_and_has_conditional_action():
    snapshot = one_question_survey(question(media=[image(loaded=False, natural=(0, 0))]))
    finding = cannot_see_image(context(snapshot)).findings[0]
    assert 'reader' in finding.headline.lower()
    assert 'verify' in finding.headline.lower()
    assert 'phone' in finding.explanation.lower()
    assert 'if' in finding.explanation.lower()
    assert 're-upload' in finding.explanation.lower()
    assert 'smaller' in finding.explanation.lower()
    assert 'readable' in finding.explanation.lower()
    assert 'meaningless' not in finding.member_impact.lower()
    result = cannot_see_image(context(snapshot))
    assert finding.severity == 'worth_improving'
    assert result.assessed is False
    from surveycoach.scoring import score
    from surveycoach.rubric import load_rubric
    card = score(load_rubric(), {'B7': result})
    assert 'B7' not in card.open_blockers
    assert 'B7' in card.pending_blockers


def test_failed_source_dimensions_do_not_create_shape_finding():
    media = image(loaded=False, natural=(0, 0), rendered=(349, 50))
    result = phone_friendly_shape(context(one_question_survey(question(media=[media]))))
    assert not result.findings
    assert result.applies is False
