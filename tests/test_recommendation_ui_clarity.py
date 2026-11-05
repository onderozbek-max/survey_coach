"""UI clarity regressions: synthetic fixture only; no live review or persistence.

2D: the fix flow replaced the three-tab, plan-scoped view. What stays true is tested here against the one ordered
fix list: a steps-only item is visible (not a missing rewrite), a screen with nothing to fix is a compact row and
never "All 0 handled", selecting a screen shows that screen's first open item, a filter that matches nothing is
never a dead end, and the compact effort guide (now inside "Play it as a member") stays keyboard-operable.
Retired with the three tabs (replacement coverage in the report .superpowers/sdd/impl-2d-integration.md):
test_screen_matches_related_findings_across_categories (also_affects / absorbed_by / question_id matching across
plan tabs: the server now builds one queue from overview.items, see tests/test_queue.py),
test_scoped_empty_filter_is_not_screen_clear_or_all_decided, test_scoped_all_decided_is_distinct_from_no_findings,
test_other_category_open_finding_prevents_screen_completion, test_unqueued_screen_finding_is_not_falsely_handled
(tests/test_fix_flow_ui.py: completion only when every item is handled, nothing-here row with next open item;
tests/test_queue.py: counts equal the verdict tiles, next_open_id never wraps)."""
import pytest

from tests.test_issue_loop_ui import open_review, focus
from tests.test_site_e2e import base_url, browser


def select_screen(page, page_id):
    page.evaluate("id => dispatchEvent(new CustomEvent('surveycoach-screen', {detail:id}))", page_id)


def test_steps_only_recommendation_is_visible_not_a_missing_rewrite(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    entry = next(e for e in detail['queue']['items'] if e['action_kind'] == 'steps' and len(e['fingerprints']) == 1)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == entry['fingerprints'][0])
    focus(page, finding)
    steps = page.locator('#coach .fix-steps')
    assert steps.locator('.fix-label').inner_text() == 'Do this'
    assert steps.locator('li').count() >= 1 and steps.locator('li').first.is_visible()
    assert 'Make this change in RedJade using the details below.' not in page.locator('#coach').inner_text()
    assert page.locator('#use-change').count() == 0                      # nothing to paste, so no Add button
    assert page.locator('#coach .after-text, #coach .fix-paste').count() == 0
    assert not writes and not errors
    context.close()


def isolated(detail):
    """Every finding points at a screen that does not exist, so the real screens have nothing to fix."""
    for f in detail['review']['findings']:
        f['page_id'] = 'elsewhere'
        f['question_id'] = None
        f.pop('absorbed_by', None)
        f.pop('also_affects', None)


def test_screen_without_findings_is_a_compact_row_not_zero_handled(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=isolated)
    select_screen(page, detail['screens'][0]['page_id'])
    assert page.locator('#coach h3').inner_text() == 'Nothing to fix on this screen'
    assert 'handled' not in page.locator('#coach').inner_text()
    assert page.locator('#coach .card').count() == 0
    assert not writes and not errors
    context.close()


def test_a_refetched_empty_queue_is_nothing_to_fix_never_all_zero_handled(browser, base_url):
    """Also the old 'refetched detail replaces queue membership': the list follows the latest detail, not the first."""
    context, page, detail, writes, errors = open_review(browser, base_url)
    assert page.locator('#fix-queue .fix-row').count() > 0
    page.evaluate("""() => {
      const d = structuredClone(SC.workspaceDetail);
      d.queue = {items: [], first_open_id: null, counts: {done: 0, total: 0, open: 0, unverified: 0, by_kind: {use: 0, done: 0, keep: 0}}};
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail: d}));
    }""")
    assert page.locator('#fix-queue .fix-row').count() == 0
    assert page.locator('#coach h3').inner_text() == 'Nothing to fix on this screen'
    assert 'All 0' not in page.locator('#coach').inner_text()
    assert page.locator('#coach .card').count() == 0
    assert page.locator('#go-signoff').is_visible()                      # no open item to point at, so the way on is Sign off
    assert not writes and not errors
    context.close()


def test_selecting_a_screen_opens_that_screens_first_open_item(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    entries = [e for e in detail['queue']['items'] if e['page_id']]
    target = entries[-1]
    expected = next(e for e in entries if target['page_id'] in e['pages'])
    select_screen(page, target['page_id'])
    assert page.locator('#coach h3').inner_text() == expected['title']
    assert page.locator('#fix-queue .fix-row[aria-current=true] .fix-row-title').inner_text() == expected['title']
    assert not writes and not errors
    context.close()


def test_a_filter_that_matches_nothing_is_never_a_dead_end(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.evaluate("o => SC.goChapter('improve', o)", dict(fingerprints=[]))
    assert page.locator('#coach .fix-card').is_visible()                 # something is open, so something is shown
    assert 'Nothing more in this view' not in page.locator('#coach').inner_text()
    assert not writes and not errors
    context.close()
