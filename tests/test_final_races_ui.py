"""Delayed writes cannot consume a replaced projection; a dismissed toast never strands focus."""
import pytest
from tests.fixflow_helpers import flow, open_flow  # noqa: F401
from tests.test_fix_flow_ui import select_kind
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser


def replace_projection(page):
    page.evaluate("""() => {
      const d = structuredClone(SC.workspaceDetail);
      d.survey_type = 'community_pulse';
      d.review.findings.reverse();
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:d}));
    }""")


def hold_puts(page):
    page.evaluate("""() => {
      window.pendingPuts = []; window.putCalls = [];
      const original = window.fetch;
      window.fetch = (url, options) => {
        if (options?.method !== 'PUT') return original(url, options);
        putCalls.push(JSON.parse(options.body));
        return new Promise(resolve => pendingPuts.push(() => resolve(new Response(options.body, {status:200}))));
      };
    }""")


def test_projection_change_invalidates_delayed_batch(browser, flow):
    """2B: Add to my changes no longer copies, so only the delayed write is left to race. A grouped card saves one
    member at a time; if the survey is replaced mid-way, the remaining members are never written."""
    context, page, errors = open_flow(browser, flow)
    card = select_kind(page, 'paste')
    assert card.locator('> .location').inner_text().startswith('Applies to')      # a three-member group
    hold_puts(page)
    card.get_by_role('button', name='Add to my changes').click()
    page.wait_for_function('putCalls.length === 1')
    replace_projection(page)
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast') !== null")
    assert 'The rest were not' in page.locator('#toast').inner_text()
    page.wait_for_timeout(300)
    assert page.evaluate('putCalls.length') == 1
    assert not errors
    context.close()


@pytest.mark.parametrize('dismiss', ['Escape', 'button', 'expiry'])
def test_dismiss_toast_never_leaves_focus_on_body(browser, flow, dismiss):
    context, page, errors = open_flow(browser, flow)
    page.locator('#mark-done').click()
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
    # 1B: the verdict headline is the #overview-h heading (the old #overview-headline paragraph is gone).
    headline = page.locator('#overview-h')
    assert headline.is_visible() and headline.inner_text() == detail['overview']['headline']
    assert not errors
    context.close()
