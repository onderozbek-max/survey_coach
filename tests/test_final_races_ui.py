"""Delayed writes/clipboard cannot consume a replaced projection."""
import pytest
from tests.test_issue_loop_ui import open_review, focus
from tests.test_improve_ui import pattern, hold_puts
from tests.test_site_e2e import base_url, browser


def replace_projection(page):
    page.evaluate("""() => {
      const d = structuredClone(SC.workspaceDetail);
      d.survey_type = 'community_pulse';
      d.review.findings.reverse();
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:d}));
    }""")


@pytest.mark.parametrize('delay', ['write', 'clipboard'])
def test_projection_change_invalidates_delayed_batch(browser, base_url, delay):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=pattern)
    page.get_by_role('tab', name='More ideas', exact=True).click()
    if delay == 'write':
        hold_puts(page)
    else:
        page.evaluate("() => { navigator.clipboard.writeText = () => new Promise(resolve => { window.releaseCopy = resolve; }); }")
    page.locator('#use-all').click()
    page.wait_for_function('putCalls.length === 1' if delay == 'write' else 'Boolean(window.releaseCopy)')
    replace_projection(page)
    page.evaluate('pendingPuts.shift()()' if delay == 'write' else 'releaseCopy()')
    page.wait_for_function("document.querySelector('#toast') !== null")
    text = page.locator('#toast').inner_text()
    assert ('Nothing copied' in text) if delay == 'write' else ('Clipboard request already started' in text)
    if delay == 'write':
        assert page.evaluate('putCalls.length') == 1
    assert not errors
    context.close()


@pytest.mark.parametrize('dismiss', ['Escape', 'button', 'expiry'])
def test_dismiss_toast_never_leaves_focus_on_body(browser, base_url, dismiss):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('#keep-as-is').click()
    page.get_by_role('button', name='Stakeholder requirement', exact=True).click()
    page.locator('#undo').wait_for()
    if dismiss == 'expiry':
        page.clock.install()
    page.locator('#undo').focus()
    if dismiss == 'Escape':
        page.keyboard.press('Escape')
    elif dismiss == 'button':
        page.get_by_role('button', name='Dismiss notification').click()
    else:
        # Timer was created before clock install; use a fresh notification timer.
        page.evaluate("SC.toast('Synthetic notification', {undo:()=>{}})")
        page.locator('#undo').focus()
        page.clock.run_for(6001)
    assert page.evaluate("document.activeElement.isConnected && document.activeElement !== document.body")
    assert not errors
    context.close()


def test_metadata_failure_after_review_fetch_has_shared_visible_error(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview')
    page.route('**/api/metadata', lambda r: r.fulfill(status=503, json={'detail':'Metadata unavailable'}))
    page.reload()
    page.wait_for_function("document.querySelector('#review-status').textContent.includes('unavailable')")
    assert page.locator('#review-status').is_visible()
    assert not errors
    context.close()


def test_failed_new_job_keeps_previous_review_available(browser, base_url):
    def prepare(detail):
        detail['job'] = {'id':'job', 'status':'failed', 'error':'Synthetic recheck failure'}
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview', prepare=prepare)
    assert 'previous completed review' in page.locator('#review-status').inner_text()
    assert page.locator('#overview-headline').is_visible()
    assert not errors
    context.close()
