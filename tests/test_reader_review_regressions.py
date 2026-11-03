"""Synthetic regressions discovered in the end-to-end reader self-review."""
from test_reader_browser import zoo  # shared loopback fixture
from surveycoach.reader import read_survey


def read(zoo, stage):
    return read_survey(zoo[0] + '/' + stage, allow_test_local=True, participate=True)


def test_confirmation_page_is_reported_as_path_end_not_unsupported(zoo):
    result = read(zoo, 'thanks')
    assert result.coverage.stop_reason == 'path_end'
    assert result.coverage.pages_captured == 1
    assert result.coverage.full_branching_coverage is False


def test_answer_enables_initially_disabled_next(zoo):
    result = read(zoo, 'disabled-next')
    assert ('GET', '/thanks') in zoo[1]
    assert result.coverage.pages_captured == 2


def test_eligibility_wording_in_question_is_not_terminal_screenout(zoo):
    result = read(zoo, 'eligibility-wording')
    assert ('GET', '/thanks') in zoo[1]
    assert result.snapshot.pages[0].kind == 'question'


def test_compound_dropdowns_preserve_every_label_and_choice(zoo):
    result = read(zoo, 'compound-selects')
    questions = result.snapshot.all_questions()
    assert [question.text for question in questions] == ['Household — Adults', 'Household — Children']
    assert [[option.label for option in question.options] for question in questions] == [
        ['One adult', 'Two adults'], ['No children', 'One child']]


def test_distinct_identical_wording_pages_are_both_read(zoo):
    result = read(zoo, 'identical-one')
    assert ('GET', '/thanks') in zoo[1]
    assert result.coverage.pages_captured == 3
    assert [question.id for question in result.snapshot.all_questions()] == [
        'q-identical-one', 'q-identical-two']


def test_validation_does_not_count_as_another_page(zoo):
    result = read(zoo, 'validation-only')
    assert result.coverage.pages_captured == 1
    assert result.coverage.stop_reason == 'blocked'
