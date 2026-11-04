"""Regression guards around revisioned undo, filters and absorbed plan membership."""
from tests.test_issue_loop_ui import open_review, focus
from tests.test_improve_ui import curated
from tests.test_site_e2e import base_url, browser


def test_undo_cannot_overwrite_newer_keep(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['plan']['must_fix'][0]['fingerprints'][0])
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    # Hold the old Undo callback while the UI creates a newer keep toast.
    page.evaluate("window.oldUndo = document.querySelector('#undo')")
    focus(page, finding)
    page.locator('#keep-as-is').click()
    page.get_by_role('button', name='Stakeholder requirement', exact=True).click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Kept on purpose')")
    page.evaluate('oldUndo.click()')
    assert len(writes) == 2 and writes[-1]['action'] == 'keep'
    assert writes[-1]['revision'] == 2
    assert not errors
    context.close()


def test_undo_failed_restore_never_claims_restored(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    page.route('**/decisions/*', lambda r: r.fulfill(status=503, json={}))
    page.locator('#undo').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('could not be restored')")
    assert page.locator('#queue-tabs [role=tab]').first.inner_text() == 'Must-fix 2/3'
    assert page.locator('#queue-progress').inner_text() == '1 of 3 handled'
    assert not errors
    context.close()


def test_refetched_detail_replaces_queue_membership(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    page.evaluate("""() => {
      const d = structuredClone(SC.workspaceDetail);
      d.plan.must_fix = []; d.plan.counts.must_fix = 0;
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:d}));
    }""")
    assert page.locator('#queue-tabs [role=tab]').first.inner_text() == 'Must-fix 0'
    assert page.locator('#coach h3').inner_text() == 'All 0 must-fixes handled'
    assert not writes and not errors
    context.close()


def test_same_chapter_options_are_consumed_and_absorbed_pin_is_not_rendered(browser, base_url):
    def prepare(detail):
        picks = curated(detail)
        hidden = detail['review']['findings'][-1]
        hidden.update(absorbed_by=picks[0]['fingerprint'], page_id=picks[0].get('page_id'), question_id=picks[0].get('question_id'))
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    target = detail['screens'][3]
    page.evaluate("page_id => SC.goChapter('improve', {page_id})", target['page_id'])
    assert target['name'] in page.locator('#stage .phone-bar').inner_text()
    focus(page, next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['plan']['must_fix'][0]['fingerprints'][0]))
    hidden = detail['review']['findings'][-1]
    assert page.locator(f'#stage .phone-marker[data-pin="{len(detail["review"]["findings"]) - 1}"]').count() == 0
    assert not writes and not errors
    context.close()
