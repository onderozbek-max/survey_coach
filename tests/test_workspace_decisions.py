"""Persisted contextual decisions, including reordered requests against the real API (fix flow: 2B selectors)."""
import re

from playwright.sync_api import expect

from tests.test_site_e2e import browser
from tests.site_helpers import go_to
from tests.test_workflow_e2e import studio


def open_sample(browser, studio):
    context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    go_to(page, 'improve')
    page.locator('#stage .phone-screen').wait_for()
    return context, page


def focus_finding(page, finding):
    """Open the card that holds this finding (a grouped card holds several; its Details list every member)."""
    page.evaluate("fingerprint => dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:fingerprint}))", finding['fingerprint'])
    page.locator(f'#coach .fix-card [data-fingerprint="{finding["fingerprint"]}"]').wait_for(state='attached')


def finding_with(page, rewrite):
    """A finding whose card pastes a rewrite (rewrite=True) or only gives steps (False); never part of a group."""
    page.locator('#coach h3.headline').wait_for()
    return page.evaluate("""rewrite => {
      const d = SC.workspaceDetail, kind = rewrite ? 'paste' : 'steps';
      const entry = d.queue.items.find(e => e.action_kind === kind && e.fingerprints.length === 1);
      return entry && d.review.findings.find(f => f.fingerprint === entry.fingerprints[0]);
    }""", rewrite)


def keep_mine(page, reason):
    page.get_by_role('button', name='Keep as is…', exact=True).click()
    page.get_by_role('button', name='Other', exact=True).click()
    page.locator('#keep-note').fill(reason)
    page.locator('#keep-save').click()
    page.locator('#toast').wait_for()


def handled_line(page):
    return page.locator('#coach .handled-line').inner_text()


def test_action_only_keeps_reason_without_claiming_verification(browser, studio):
    context, page = open_sample(browser, studio)
    finding = finding_with(page, False)
    assert finding, 'the sample must hold a steps-only item'
    focus_finding(page, finding)
    assert page.locator('#coach .use-change').count() == 0
    reason = 'Intentional research stimulus; keep full image.'
    keep_mine(page, reason)
    focus_finding(page, finding)
    assert 'Kept as is' in handled_line(page) and reason in handled_line(page)
    assert not re.search(r'verified|fixed|checked', handled_line(page), re.I)       # keeping is never claimed as a fix
    page.reload()
    page.locator('#stage .phone-screen').wait_for()
    focus_finding(page, finding)
    assert 'Kept as is' in handled_line(page) and reason in handled_line(page)       # the reason survives a reload
    context.close()


def test_delayed_use_cannot_overwrite_newer_keep_after_navigation(browser, studio):
    context, page = open_sample(browser, studio)
    finding = finding_with(page, True)
    assert finding, 'the sample must hold a single pasteable item'
    focus_finding(page, finding)
    pending = []

    def hold_first(route):
        if not pending:
            pending.append(route)
        else:
            route.continue_()
    page.route('**/decisions/*', hold_first)
    page.evaluate("navigator.clipboard.writeText('unchanged clipboard')")
    page.locator('#coach .use-change').first.click()
    page.wait_for_timeout(100)
    assert pending
    # UI serialization survives navigation. Retain the API revision-race guard
    # by delivering a newer authoritative decision outside the locked panel.
    focus_finding(page, finding)
    assert page.locator('#coach .fix-handled button, #coach .decision-actions button').evaluate_all('bs => bs.length > 0 && bs.every(b => b.disabled)')      # locked while the save is out
    page.evaluate("""async fp => {
      SC.decisionRevisions.set(fp, 2);
      const d = SC.workspaceDetail;
      const response = await fetch(`/api/surveys/${d.id}/versions/${d.version}/decisions/${fp}`, {
        method:'PUT', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'keep', keep_reason:'other', reason:'Required wording', revision:2, client_id:SC.decisionClient})});
      if (!response.ok) throw Error('Newer decision failed');
      await response.json();
      // Like the app after any save: refetch, so the queue reflects the server's decisions.
      const fresh = await (await fetch(`/api/surveys/${d.id}/versions/${d.version}`)).json();
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:fresh}));
    }""", finding['fingerprint'])
    older = pending[0].request.post_data_json
    assert older['revision'] == 1 and older['action'] == 'pick'
    assert older['client_id'] == page.evaluate('SC.decisionClient')
    response = pending[0].fetch()
    assert response.status == 200
    # The API rejects the late older pick by returning the authoritative keep,
    # not by accepting stale data and relying on the browser to hide it.
    authoritative = response.json()
    assert authoritative['revision'] == 2 and authoritative['action'] == 'keep'
    assert authoritative['client_id'] == older['client_id']
    assert authoritative['reason'] == 'Required wording'
    pending[0].fulfill(response=response)
    page.wait_for_function("document.querySelector('#coach .issue-save-status')?.textContent !== 'Saving…'")
    focus_finding(page, finding)
    expect(page.locator('#coach .handled-line')).to_contain_text('Required wording')
    assert 'Kept as is' in handled_line(page)
    assert page.locator('#coach .use-change').count() == 0           # the late pick did not reopen or replace the keep
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged clipboard'      # Add never copies
    page.reload()
    page.locator('#stage .phone-screen').wait_for()
    focus_finding(page, finding)
    assert 'Required wording' in handled_line(page)
    assert page.locator('#tray-toggle').inner_text().startswith('My changes (0)')       # the stale pick never reached the tray
    context.close()
