"""Generation contract through grounding and UI, with synthetic judge output only."""
from surveycoach.findings import RewriteOption
from surveycoach.judge.batches import WORDING
from surveycoach.judge.grounding import ground
from surveycoach.judge.prompts import system_prompt
from surveycoach.judge.schemas import AiFinding, BatchOutput, Verdict
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import SurveySnapshot
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser
from tests.test_structured_suggestions_ui import OLD, STEM, recommendation

RUBRIC = load_rubric()


def grounded_finding(detail, text):
    target = recommendation(detail)
    raw = AiFinding(criterion_id='5.1', page_id=target['page_id'], question_id=target['question_id'],
        headline='Clarify the question and answers', evidence=STEM, explanation='Use neutral wording.',
        member_impact='Members can understand the choices.', current_text=STEM,
        suggested_text=text, options=[RewriteOption(label='Neutral', text=text)])
    result = ground(BatchOutput(verdicts=[Verdict(criterion_id='5.1', fraction=0.5)], findings=[raw]),
                    WORDING, SurveySnapshot.model_validate(detail['snapshot']), RUBRIC)
    assert not result.dropped
    kept = result.results['5.1'].findings[0].model_dump(mode='json')
    kept['fingerprint'] = target['fingerprint']
    target.clear()
    target.update(kept)
    return target


def test_prompt_bundle_survives_grounding_renders_and_copies_exactly(browser, base_url):
    text = 'Question: Which flavours would you try?\nAnswer choices:\n- Vanilla\n- Chocolate'
    assert text in system_prompt(WORDING, RUBRIC)
    text = text.replace('would you try?', 'would you buy?')
    def prepare(detail):
        kept = grounded_finding(detail, text)
        assert kept['structural'] is True
        assert kept.get('edit_kind') != 'add_answer'
        assert kept['suggested_text'] == text and kept['options'][0]['text'] == text
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    assert page.locator('.suggestion-question').inner_text() == 'Which flavours would you buy?'
    assert page.get_by_role('list', name='Answer choices').locator('li').all_inner_texts() == OLD[:2]
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert writes[-1]['picked_text'] == text
    assert page.evaluate('navigator.clipboard.readText()') == text
    assert not errors
    context.close()


def test_plain_generation_stays_nonstructural_and_keeps_word_diff(browser, base_url):
    text = 'Which flavours would you buy?'
    def prepare(detail):
        kept = grounded_finding(detail, text)
        assert kept['structural'] is False
        assert kept['suggested_text'] == text
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    assert page.locator('#coach .suggested .diff del').inner_text() == 'try'
    assert page.locator('#coach .suggested .diff ins').inner_text() == 'buy'
    assert not writes and not errors
    context.close()


def test_missing_answer_generation_still_becomes_add_answer(browser, base_url):
    text = '\n'.join([STEM, *OLD, 'Neither of these'])
    def prepare(detail):
        kept = grounded_finding(detail, text)
        assert kept['edit_kind'] == 'add_answer'
        assert kept['suggested_text'] == 'Neither of these'
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    assert page.locator('#coach .suggested blockquote').inner_text() == 'Neither of these'
    assert page.locator('#coach .suggestion-bundle').count() == 0
    assert not writes and not errors
    context.close()
