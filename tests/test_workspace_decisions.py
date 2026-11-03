"""Persisted contextual decisions, including reordered requests against the real API."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def open_sample(browser, studio):
    context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('.phone-screen').wait_for()
    return context, page


def focus_finding(page, finding):
    page.evaluate("fingerprint => dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:fingerprint}))", finding['fingerprint'])
    assert page.locator('#coach .card-head').inner_text() == finding['headline']


def finding_with(page, rewrite):
    # Workflow exposes detail before the dynamically loaded app registers navigation.
    page.locator('#coach .card-head').wait_for()
    findings = page.evaluate('SC.workspaceDetail.review.findings')
    return next(f for f in findings if bool(f.get('suggested_text') or f.get('options')) == rewrite)


def keep_mine(page, reason):
    page.get_by_role('button', name='Keep mine', exact=True).click()
    page.get_by_label('Reason for keeping', exact=False).fill(reason)
    page.get_by_role('button', name='Save reason & keep mine').click()
    page.locator('.accepted-risk').wait_for()


def test_action_only_keeps_reason_without_claiming_verification(browser, studio):
    context, page = open_sample(browser, studio)
    finding = finding_with(page, False)
    focus_finding(page, finding)
    assert page.locator('#coach .issue-rewrite').count() == 0
    reason = 'Intentional research stimulus; keep full image.'
    keep_mine(page, reason)
    assert 'not a verified fix' in page.locator('.accepted-risk').inner_text()
    page.reload()
    page.locator('.phone-screen').wait_for()
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
    page.locator('#coach .issue-rewrite .btn').first.click()
    page.wait_for_timeout(100)
    assert pending
    # A new contextual card lets the researcher change their mind during the save.
    focus_finding(page, finding)
    keep_mine(page, 'Required wording')
    response = pending[0].fetch()
    pending[0].fulfill(response=response)
    page.wait_for_timeout(100)
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged clipboard'
    page.reload()
    page.locator('.phone-screen').wait_for()
    focus_finding(page, finding)
    assert page.get_by_label('Reason for keeping', exact=False).input_value() == 'Required wording'
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    assert page.locator('#copy-all').is_disabled()
    context.close()
