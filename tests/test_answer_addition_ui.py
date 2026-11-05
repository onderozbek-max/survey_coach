"""Addition cards and clipboard describe authoring actions, not stem replacements (2D: on the 2B fix card)."""
from tests.test_issue_loop_ui import open_review, focus
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import go_to

LABEL = 'I did not shop this year'


def test_added_answer_card_copies_only_label_and_sheet_never_says_replace(browser, base_url):
    def prepare(detail):
        finding = next(f for f in detail['review']['findings'] if f.get('question_id') and not f.get('absorbed_by'))
        finding.update(edit_kind='add_answer', structural=True, suggested_text=LABEL, options=[],
                       explanation='Keep the question. Add this answer and make it exclusive.',
                       action_kind='paste', steps=[])         # the explicit action kind wins: this card pastes
        detail['_target'] = finding['fingerprint']
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['_target'])
    focus(page, finding)
    assert page.locator('#coach .fix-label').first.inner_text() == 'Add this answer'
    assert page.locator('#coach .fix-paste blockquote').inner_text() == LABEL        # only the new label is offered
    page.locator('#coach details.more > summary').click()
    assert page.locator('#coach details.more').get_by_text('Keep this question', exact=True).count() == 1
    assert 'Do not replace the question' in page.locator('#coach details.more').inner_text()
    assert not writes
    page.get_by_role('button', name='Copy the new wording', exact=True).click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.startsWith('Copied')")
    assert page.evaluate('navigator.clipboard.readText()') == LABEL
    page.get_by_role('button', name='Add to my changes', exact=True).click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == LABEL
    go_to(page, 'share')
    text = page.locator('#change-list').inner_text()
    assert f'Add answer option: {LABEL}' in text
    assert 'Replace with:' not in text
    assert not errors
    context.close()
