"""Regression guards around revisioned undo and absorbed findings, on the 2B fix card.

2D: the three plan tabs are gone, so test_refetched_detail_replaces_queue_membership (tab membership) is retired; its
replacement is tests/test_recommendation_ui_clarity.py::test_a_refetched_empty_queue_is_nothing_to_fix_never_all_zero_handled
and tests/test_final_fixes_ui.py::test_undo_resolves_refetched_fingerprint_not_array_index (a refetched list is honoured)."""
from tests.test_issue_loop_ui import focus, open_review, single_paste
from tests.test_site_e2e import base_url, browser


def test_undo_cannot_overwrite_newer_keep(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding, entry = single_paste(detail)
    focus(page, finding)
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    # Hold the old Undo button while the item is reopened and then kept: a newer choice exists.
    page.evaluate("window.oldUndo = document.querySelector('#undo')")
    focus(page, finding)
    page.locator('#undo-decision').click()
    page.locator('#keep-as-is').wait_for()                      # reopened: the item is open again
    page.locator('#keep-as-is').click()
    page.get_by_role('button', name='Owner decided', exact=True).click()
    page.locator('#keep-save').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Kept as is')")
    page.evaluate('oldUndo.click()')
    page.wait_for_timeout(300)
    assert [w['action'] for w in writes] == ['pick', 'open', 'keep']            # the stale Undo wrote nothing
    assert writes[-1]['revision'] == 3
    assert not errors
    context.close()


def test_undo_failed_restore_never_claims_restored(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding, entry = single_paste(detail)
    focus(page, finding)
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    total = detail['queue']['counts']['total']
    page.route('**/decisions/*', lambda r: r.fulfill(status=503, json={}))
    page.locator('#undo').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('could not be undone')")
    assert 'Back on your list' not in page.locator('#toast').inner_text()
    assert page.locator('#queue-progress').inner_text() == f'1 of {total} done'     # still handled: nothing was restored
    assert page.locator(f'[data-fk=fix-row-{entry["id"]}]').get_attribute('data-state') == 'done'
    assert not errors
    context.close()


def test_absorbed_finding_pin_is_not_rendered_and_screen_navigation_is_consumed(browser, base_url):
    """The server decides absorption (a lesser finding in the same place as a blocker); the phone shows one pin for the pair."""
    context, page, detail, writes, errors = open_review(browser, base_url)
    findings = detail['review']['findings']
    index, hidden = next((i, f) for i, f in enumerate(findings) if f.get('absorbed_by'))
    target = next(s for s in detail['screens'] if s['page_id'] == hidden['page_id']
                  or any(q['id'] == hidden.get('question_id') for q in s.get('questions', [])))
    page.evaluate("page_id => SC.goChapter('improve', {page_id})", target['page_id'])
    assert target['name'] in page.locator('#stage .phone-bar').inner_text()
    assert page.locator(f'#stage .phone-marker[data-pin="{index}"]').count() == 0
    assert not writes and not errors
    context.close()
