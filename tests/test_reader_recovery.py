"""Requirement-aware progression with synthetic uploads, never personal files."""
from test_reader_browser import zoo
import pytest
from surveycoach.reader import read_survey
from surveycoach.reader.requirements import UnmetRequirement, placeholder_png, synthetic_text


def test_generated_png_never_reuses_arbitrary_root_image(tmp_path):
    (tmp_path / 'private.png').write_bytes(b'private screenshot')
    image = placeholder_png(tmp_path / 'captures')
    assert image.name == 'surveycoach-test-placeholder.png'
    assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert (tmp_path / 'private.png').read_bytes() == b'private screenshot'


def test_conflicting_lengths_stop_without_inventing_a_valid_answer():
    with pytest.raises(UnmetRequirement):
        synthetic_text({'minlength': 20, 'maxlength': 8})


def test_hidden_photo_input_and_short_required_text_can_progress(zoo):
    result = read_survey(zoo[0] + '/photo-text', allow_test_local=True, participate=True)
    assert ('GET', '/thanks') in zoo[1]
    assert result.coverage.stop_reason == 'path_end'
    assert result.coverage.pages_captured == 2
    assert any('photo' in question.text.lower() for question in result.snapshot.all_questions())


def test_visible_validation_repairs_text_then_retries_same_page(zoo):
    result = read_survey(zoo[0] + '/server-text-rule', allow_test_local=True, participate=True)
    assert ('GET', '/thanks') in zoo[1]
    assert result.coverage.stop_reason == 'path_end'
    assert result.coverage.pages_captured == 2


def test_staged_upload_waits_then_commits_media_before_next(zoo):
    result = read_survey(zoo[0] + '/staged-photo', allow_test_local=True, participate=True)
    assert ('GET', '/thanks') in zoo[1]
    assert result.coverage.stop_reason == 'path_end'


def test_passive_mode_never_uploads(zoo):
    result = read_survey(zoo[0] + '/photo-text', allow_test_local=True)
    assert ('GET', '/thanks') not in zoo[1]
    assert result.coverage.stop_reason == 'unmet_requirement'


def test_validation_is_scoped_to_its_field(zoo):
    result = read_survey(zoo[0] + '/field-specific-rule', allow_test_local=True, participate=True)
    assert ('GET', '/thanks') in zoo[1]
    assert result.coverage.stop_reason == 'path_end'


def test_unresolvable_validation_stays_bounded(zoo):
    result = read_survey(zoo[0] + '/validation-only', allow_test_local=True, participate=True)
    assert result.coverage.pages_captured == 1
    assert result.coverage.stop_reason == 'blocked'
