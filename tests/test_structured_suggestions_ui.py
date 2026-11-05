"""Structured recommendation presentation on the fix card; all payloads synthetic/intercepted.

2D: the card is the 2B fix card (After text first, Copy, Show changes, Add to my changes). Add saves a pick and never
copies; Copy is its own button, so exact-copy assertions press Copy. Presentation contracts are unchanged."""
import pytest

from tests.test_improve_ui import curated
from tests.test_issue_loop_ui import focus, open_review
from tests.test_site_e2e import base_url, browser

STEM = 'Which flavours would you try?'
OLD = ['Vanilla', 'Chocolate', 'Mint']
TEXT = 'Question: Which flavours would you buy?\nAnswer choices:\n- Vanilla\n- Chocolate\n- Neither of these'
COPY = {'name': 'Copy the new wording', 'exact': True}


def recommendation(detail, text=TEXT, structural=True, adding=False):
    finding = curated(detail)[0]
    question = next(q for p in detail['snapshot']['pages'] for q in p.get('questions', [])
                    if q.get('options'))
    question.update(text=STEM, kind='single_choice', options=[dict(id=str(i), label=t) for i, t in enumerate(OLD)])
    page = next(p for p in detail['snapshot']['pages'] if question in p.get('questions', []))
    finding.update(question_id=question['id'], page_id=page['id'], current_text=STEM,
                   structural=structural, suggested_text=text, options=[],
                   edit_kind='add_answer' if adding else None,
                   action_kind='paste', steps=[])         # the explicit action kind wins: this card pastes
    detail['_target'] = finding['fingerprint']
    return finding


def open_rec(browser, base_url, prepare, width=1280):
    """Open the review with the prepared recommendation as the open card (the fix list is no longer plan-ordered)."""
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, prepare=prepare)
    focus(page, next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['_target']))
    return context, page, detail, writes, errors


def copy_new_wording(page):
    page.get_by_role('button', **COPY).click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.startsWith('Copied')")


def show_changes(page):
    page.get_by_role('button', name='Show changes').click()
    return page.locator('#coach .changes')


@pytest.mark.parametrize('width', [1280, 390])
def test_bundle_has_semantic_labels_answers_and_discoverable_original(browser, base_url, width):
    context, page, detail, writes, errors = open_rec(browser, base_url, recommendation, width=width)
    box = page.locator('#coach .fix-paste')
    assert box.get_by_role('heading', name='Question', exact=True).count() == 1
    assert box.locator('.suggestion-question').inner_text() == 'Which flavours would you buy?'
    assert box.get_by_role('heading', name='Answer choices', exact=True).count() == 1
    assert box.get_by_role('list', name='Answer choices').locator('li').all_inner_texts() == ['Vanilla', 'Chocolate', 'Neither of these']
    assert box.locator('del, ins').count() == 0
    page.locator('#coach details.more summary').focus()
    page.keyboard.press('Enter')
    assert page.locator('#coach .issue-original blockquote').inner_text() == '\n'.join([STEM, *OLD])
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()


def test_alternative_keyboard_selection_updates_structure_and_copies_exact_text(browser, base_url):
    alternative = '  Question: Which flavours would you share?\r\nAnswer choices:\r\n- Vanilla\r\n- Mint\r\n- Neither  '
    def prepare(detail):
        finding = recommendation(detail)
        finding['options'] = [dict(label='Neutral', text=TEXT), dict(label='Friendlier', text=alternative)]
        detail['decisions'][finding['fingerprint']] = dict(action='open', stale_pick=True)
    context, page, detail, writes, errors = open_rec(browser, base_url, prepare)
    page.get_by_role('button', name='Friendlier', exact=True).focus()
    page.keyboard.press('Enter')
    assert page.locator('.suggestion-question').inner_text() == 'Which flavours would you share?'
    assert page.get_by_role('list', name='Answer choices').locator('li').all_inner_texts() == ['Vanilla', 'Mint', 'Neither']
    assert page.get_by_role('button', name='Friendlier', exact=True).get_attribute('aria-pressed') == 'true'
    assert page.get_by_role('button', name='Friendlier', exact=True).evaluate('e => e === document.activeElement')   # keyboard users keep their place
    assert not writes
    copy_new_wording(page)
    assert page.evaluate('navigator.clipboard.readText()') == alternative       # Copy gives the exact text, nothing normalised
    assert not writes                                                          # copying never saves a decision
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == alternative
    assert not errors
    context.close()


def test_plain_question_keeps_wording_diff(browser, base_url):
    context, page, detail, writes, errors = open_rec(browser, base_url,
        lambda d: recommendation(d, 'Which flavours would you buy?', structural=False))
    changes = show_changes(page)
    assert changes.locator('.diff del').inner_text() == 'try'
    assert changes.locator('.diff ins').inner_text() == 'buy'
    assert page.locator('#coach .fix-paste ul.alternatives, #coach .fix-paste .suggestion-bundle').count() == 0
    assert not writes and not errors
    context.close()


def test_add_answer_is_labelled_without_replacing_the_question(browser, base_url):
    context, page, detail, writes, errors = open_rec(browser, base_url,
        lambda d: recommendation(d, 'Neither of these', adding=True))
    box = page.locator('#coach .fix-paste')
    assert box.get_by_role('heading', name='Answer choice', exact=True).count() == 1
    assert box.locator('blockquote').inner_text() == 'Neither of these'
    assert box.get_by_role('heading', name='Question', exact=True).count() == 0
    assert box.locator('del, ins').count() == 0
    copy_new_wording(page)
    assert page.evaluate('navigator.clipboard.readText()') == 'Neither of these'
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == 'Neither of these'
    assert not errors
    context.close()


@pytest.mark.parametrize('text,structural', [
    ('Consider the following.\nThis explains the proposal.\nMore explanatory prose.', True),
    ('Which flavours?\n\nVanilla\nChocolate', True),
    ('Which flavours?\nVanilla\nChocolate', False),
    (STEM + '\nPlease shorten the question and keep the existing answers.', True),
    ('Consider these changes.\nVanilla\nExplain that respondents may skip this question.', True),
    ('Which flavours?\nVanilla\nExplain that respondents may skip this question.', True),
    ('Which flavours?\nVanilla\nChocolate\nNeither of these', True),
    ('Question: Which flavours?\nAnswer choices:\nVanilla\nPlease keep existing answers.', True),
    ('Question: Which flavours?\nAnswer choices:\n- Vanilla\nExplain that respondents may skip.', True),
])
def test_ambiguous_or_unmarked_text_is_not_guessed_into_a_bundle(browser, base_url, text, structural):
    context, page, detail, writes, errors = open_rec(browser, base_url,
        lambda d: recommendation(d, text, structural=structural))
    box = page.locator('#coach .fix-paste')
    assert box.locator('ul[aria-label="Answer choices"]').count() == 0
    if structural:
        assert box.locator('blockquote').inner_text() == text
    else:
        assert show_changes(page).locator('.diff').count() == 1
    assert not writes and not errors
    context.close()


def test_grounded_unlabelled_bundle_requires_complete_captured_answers(browser, base_url):
    text = '\n'.join(['Which flavours would you buy?', *OLD])
    context, page, detail, writes, errors = open_rec(browser, base_url,
        lambda d: recommendation(d, text))
    assert page.locator('.suggestion-question').inner_text() == 'Which flavours would you buy?'
    assert page.get_by_role('list', name='Answer choices').locator('li').all_inner_texts() == OLD
    assert not writes and not errors
    context.close()


def test_mixed_alternative_single_line_uses_question_diff_not_answer_bundle(browser, base_url):
    plain = 'Which flavours would you buy?'
    def prepare(detail):
        finding = recommendation(detail)
        finding['options'] = [dict(label='Bundle', text=TEXT), dict(label='Question only', text=plain)]
    context, page, detail, writes, errors = open_rec(browser, base_url, prepare)
    page.get_by_role('button', name='Question only', exact=True).focus()
    page.keyboard.press('Enter')
    box = page.locator('#coach .fix-paste')
    changes = show_changes(page)
    assert changes.locator('.diff').count() == 1
    assert changes.locator('.diff del').inner_text() == 'try'
    assert changes.locator('.diff ins').inner_text() == 'buy'
    assert 'Vanilla' not in box.inner_text()
    copy_new_wording(page)
    assert page.evaluate('navigator.clipboard.readText()') == plain
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == plain
    assert not errors
    context.close()


def test_structured_text_is_escaped_and_raw_copy_is_unchanged(browser, base_url):
    text = 'Question: Which <img src=x onerror=alert(1)> flavours?\nAnswer choices:\n- Vanilla\n- <script>window.pwned=1</script>\n- Chocolate & mint'
    context, page, detail, writes, errors = open_rec(browser, base_url,
        lambda d: recommendation(d, text))
    box = page.locator('#coach .fix-paste')
    assert box.get_by_role('list', name='Answer choices').locator('li').all_inner_texts() == ['Vanilla', '<script>window.pwned=1</script>', 'Chocolate & mint']
    assert box.locator('img, script').count() == 0
    assert page.evaluate('window.pwned') is None
    copy_new_wording(page)
    assert page.evaluate('navigator.clipboard.readText()') == text
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == text
    assert not errors
    context.close()
