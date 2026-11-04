"""Persisted contextual decisions, including reordered requests against the real API."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def open_sample(browser, studio):
    context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#stage .phone-screen').wait_for()
    return context, page


def focus_finding(page, finding):
    page.evaluate("fingerprint => dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:fingerprint}))", finding['fingerprint'])
    assert page.locator('#coach h3.headline').inner_text() == finding['headline']


def finding_with(page, rewrite):
    # Workflow exposes detail before the dynamically loaded app registers navigation.
    page.locator('#coach h3.headline').wait_for()
    findings = page.evaluate('SC.workspaceDetail.review.findings')
    return next(f for f in findings if bool(f.get('suggested_text') or f.get('options')) == rewrite)


def keep_mine(page, reason):
    page.get_by_role('button', name='Keep as is', exact=True).click()
    page.get_by_role('button', name='Other…', exact=True).click()
    page.get_by_label('Reason for keeping', exact=False).fill(reason)
    page.get_by_role('button', name='Save reason').click()
    page.locator('#toast').wait_for()


def test_action_only_keeps_reason_without_claiming_verification(browser, studio):
    context, page = open_sample(browser, studio)
    finding = finding_with(page, False)
    focus_finding(page, finding)
    assert page.locator('#coach .use-change').count() == 0
    reason = 'Intentional research stimulus; keep full image.'
    keep_mine(page, reason)
    focus_finding(page, finding)
    assert 'not a verified fix' in page.locator('.accepted-risk').inner_text()
    page.reload()
    page.locator('#stage .phone-screen').wait_for()
    focus_finding(page, finding)
    assert page.get_by_label('Reason for keeping', exact=False).input_value() == reason
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    context.close()


def test_delayed_use_cannot_overwrite_newer_keep_after_navigation(browser, studio):
    context, page = open_sample(browser, studio)
    finding = finding_with(page, True)
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
    assert page.get_by_role('button', name='Keep as is', exact=True).is_disabled()
    page.evaluate("""async fp => {
      SC.decisionRevisions.set(fp, 2);
      const d = SC.workspaceDetail;
      const response = await fetch(`/api/surveys/${d.id}/versions/${d.version}/decisions/${fp}`, {
        method:'PUT', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'keep', reason:'Required wording', revision:2, client_id:SC.decisionClient})});
      if (!response.ok) throw Error('Newer decision failed');
      d.decisions[fp] = await response.json();
      dispatchEvent(new CustomEvent('surveycoach-decisions', {detail:d}));
    }""", finding['fingerprint'])
    response = pending[0].fetch()
    pending[0].fulfill(response=response)
    page.wait_for_timeout(100)
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged clipboard'
    page.reload()
    page.locator('#stage .phone-screen').wait_for()
    focus_finding(page, finding)
    assert page.get_by_label('Reason for keeping', exact=False).input_value() == 'Required wording'
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    assert page.locator('#copy-all').is_disabled()
    context.close()
