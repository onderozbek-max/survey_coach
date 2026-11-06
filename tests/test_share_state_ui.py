"""Share must follow authoritative decisions, reset and history without writes."""
from tests.test_issue_loop_ui import open_review
from tests.test_share_ui import chosen
from tests.test_site_e2e import base_url, browser


def test_share_tracks_decision_reset_and_refetched_plan(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', prepare=chosen)
    assert page.locator('#share-summary').inner_text().startswith('2 changes chosen')
    page.evaluate("""() => {
      const d = structuredClone(SC.workspaceDetail);
      d.decisions = {};
      d.plan.must_fix = []; d.plan.counts.must_fix = 0;
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:d}));
    }""")
    assert page.locator('#share-summary').inner_text() == '0 changes chosen'
    assert page.locator('#copy-all').is_hidden()
    assert not writes and not errors
    context.close()


def test_share_uses_canonical_names_and_never_counts_open_items(browser, base_url):
    def prepare(detail):
        picks, keep = chosen(detail)
        screen = next(s for s in detail['screens'] if s['page_id'] == picks[0].get('page_id'))
        screen['name'] = 'Canonical study welcome'
        picks[0]['headline'] = '<img src=x onerror=alert(1)>'
        detail['decisions'][picks[0]['fingerprint']]['picked_text'] = '<script>not markup</script>'
        # A partially handled grouped item is still open, never two independent fixes.
        detail['plan']['must_fix'] = [{'id': 'mixed', 'fingerprints': [picks[0]['fingerprint'], picks[2]['fingerprint']]}]
        detail['plan']['counts']['must_fix'] = 1
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', prepare=prepare, derived=False)
    assert 'Canonical study welcome' in page.locator('#change-list h3').all_text_contents()
    assert page.locator('#share-summary').inner_text() == '2 changes chosen'      # what is still open is the verdict's to say (test_signoff_consistency)
    after = page.locator('#change-list .diff').evaluate("el => [...el.childNodes].filter(n => n.nodeName !== 'DEL').map(n => n.textContent).join('')")
    assert after == '<script>not markup</script>'
    assert page.locator('#change-list img, #change-list script').count() == 0
    assert not writes and not errors
    context.close()


def test_share_original_without_reason_is_open_and_unknown_comparison_honest(browser, base_url):
    def prepare(detail):
        picks, keep = chosen(detail)
        # 2A: a bare "original" is Mark done (handled, unverified). "Kept without a reason stays open" is now a keep
        # with no chip and no note. The plan is injected (derived=False): this tests how Share counts a given plan.
        detail['decisions'][keep['fingerprint']] = {'action': 'keep', 'reason': ''}
        detail['round_changes'] = None
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share', prepare=prepare, derived=False)
    assert page.locator('#share-summary').inner_text() == '2 changes chosen'
    assert 'fixed' not in page.locator('#version-changes').inner_text().lower() and page.locator('#delta-link').count() == 0   # no comparison, no claim
    page.locator('.round-timeline a').first.click()
    assert 'version=1#share' in page.url
    assert not writes and not errors
    context.close()
