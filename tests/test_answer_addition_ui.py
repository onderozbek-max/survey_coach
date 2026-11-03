"""Addition cards and clipboard describe authoring actions, not stem replacements."""
from tests.test_issue_loop_ui import open_review, focus
from tests.test_site_e2e import base_url, browser


def test_added_answer_card_copies_only_label_and_sheet_never_says_replace(browser, base_url):
    context,page,detail,writes,errors=open_review(browser,base_url)
    finding=next(f for f in detail['review']['findings'] if f.get('question_id'))
    finding.update(edit_kind='add_answer',structural=True,
                   suggested_text='I did not shop this year',options=[],
                   explanation='Keep the question. Add this answer and make it exclusive.')
    page.reload(); page.locator('#coach .card-head').wait_for()
    focus(page,finding)
    assert page.locator('#coach').get_by_role('heading',name='Add answer option',exact=True).count()==1
    assert page.locator('#coach').get_by_text('Keep this question',exact=True).count()==1
    assert not writes
    page.get_by_role('button',name='Use this answer option',exact=True).click()
    page.wait_for_function("document.querySelector('.issue-save-status').textContent.includes('Copied')")
    assert page.evaluate('navigator.clipboard.readText()')=='I did not shop this year'
    page.locator('.change-sheet > summary').click()
    text=page.locator('.change-sheet pre').inner_text()
    assert 'Add answer option: I did not shop this year' in text
    assert 'Replace with:' not in text
    assert not errors
    context.close()
