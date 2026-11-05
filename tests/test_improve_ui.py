"""Focused Improve contracts on the 2B fix card, intercepted synthetic payloads only.

2D port of the three-tab Improve tests. Retired because their whole premise is gone (replacement coverage in
.superpowers/sdd/impl-2d-integration.md): the Use all / pattern-row panel (one grouped card now: tests/test_fix_group_safety.py),
the per-tab completion section "All 3 must-fixes handled" and "Continue to quick wins" (one list, one completion moment:
tests/test_fix_flow_ui.py::test_handling_everything_ends_in_the_completion_moment), tab selection by signal route
(tests/test_fix_flow_ui.py::test_filter_chips_and_the_verdict_state_param) and per-row keyboard focus inside a pattern
panel (a group is one card; focus returns to the card heading: test_improve_navigation_ui.py, test_final_fixes_ui.py)."""
import pytest

from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from tests.test_issue_loop_ui import focus, open_review, single_paste
from tests.test_site_e2e import base_url, browser


def test_queue_saves_adds_advances_and_undo_reopens(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    assert page.get_by_role('tab').count() == 0                                   # one ordered list, no tabs
    assert page.locator('#rail, .journey, #review-toolbar, .next-issue').count() == 0
    assert page.locator('#coach .location').inner_text().split(' · ')[0] == page.locator('#stage .phone-bar').inner_text().split(' · ')[0]
    assert page.locator('#coach .state-chip').inner_text() == 'Fix before launch'
    assert page.locator('#coach details.more').count() == 1
    assert page.locator('#coach .card > :first-child').get_attribute('class') == 'fix-card-head'
    finding, entry = single_paste(detail)
    focus(page, finding)
    first = page.locator('#coach h3.headline').inner_text()
    total = detail['queue']['counts']['total']
    assert not writes
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['action'] == 'pick' and writes[-1]['revision'] == 1 and writes[-1]['client_id']
    assert page.locator('#coach h3.headline').inner_text() != first                 # moved on
    assert page.locator('#coach h3.headline').evaluate('e => e === document.activeElement')
    assert page.locator('#queue-progress').inner_text() == f'1 of {total} done'
    page.locator('#undo').click()
    page.wait_for_function(f"document.querySelector('#queue-progress').textContent === '0 of {total} done'")
    assert writes[-1]['action'] == 'open' and writes[-1]['revision'] == 2
    assert not errors
    context.close()


def test_keep_requires_a_reason_and_saves_only_on_save_and_drawer_searches_labels(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding, entry = single_paste(detail)
    focus(page, finding)
    first = page.locator('#coach h3.headline').inner_text()
    page.locator('#keep-as-is').click()
    assert not writes                                                         # opening the panel saves nothing
    assert page.locator('#keep-save').is_disabled()                           # and Save needs a reason
    page.get_by_role('button', name='Other', exact=True).click()
    page.get_by_label('Note (optional, up to 200 characters)').fill('Required for comparability')
    assert not writes
    page.locator('#keep-save').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Kept as is')")
    assert writes[-1]['action'] == 'keep' and writes[-1]['keep_reason'] == 'other' and writes[-1]['reason'] == 'Required for comparability'
    assert page.locator('#coach h3.headline').inner_text() != first
    page.locator('#fix-queue .fix-row').nth(2).click()                          # looking at another item saves nothing
    assert len(writes) == 1
    page.locator('#all-screens').click()
    drawer = page.get_by_role('dialog', name='All screens')
    assert drawer.is_visible()
    screen = detail['screens'][2]
    drawer.get_by_role('searchbox').fill(screen['name'])
    assert drawer.locator('.screen-row:visible').count() >= 1
    drawer.locator('.screen-row:visible').first.click()
    assert not drawer.is_visible()
    assert screen['name'] in page.locator('#stage .phone-bar').inner_text()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors
    context.close()


def test_clipboard_failure_is_honest_and_add_does_not_depend_on_it(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding, entry = single_paste(detail)
    focus(page, finding)
    page.evaluate("() => { navigator.clipboard.writeText = async () => {throw Error('denied')}; document.execCommand = () => false; }")
    page.get_by_role('button', name='Copy the new wording', exact=True).click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copy unavailable')")
    assert 'Copied' not in page.locator('#toast').inner_text()
    assert not writes                                                         # copying never saves, and failing to copy never fakes success
    page.locator('#use-change').click()                                       # Add to my changes needs no clipboard
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['action'] == 'pick' and writes[-1]['picked_text']
    assert page.locator('#undo').is_visible()
    assert not errors
    context.close()


def with_options(detail):
    finding = next(f for f in detail['review']['findings'] if f.get('question_id') and f.get('current_text')
                   and f.get('suggested_text') and not f.get('structural'))
    finding['options'] = [dict(text='New recommended', label='Precise'), dict(text='Short text')]
    finding.update(action_kind='paste', steps=[])
    detail['decisions'][finding['fingerprint']] = dict(action='open', stale_pick=True)
    detail['_target'] = finding['fingerprint']


def test_stale_pick_is_announced_and_a_new_alternative_saves_its_own_text(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=with_options)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['_target'])
    focus(page, finding)
    assert page.get_by_text('We improved this suggestion since you chose it. Choose again.', exact=True).is_visible()
    assert page.locator('.alternatives button').all_inner_texts() == ['Precise', 'Shorter']
    page.get_by_role('button', name='Shorter', exact=True).click()
    assert not writes                                                         # choosing is not saving
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == 'Short text'
    assert not errors
    context.close()


def test_a_route_with_fingerprints_opens_that_item_and_stays_scoped_to_its_screen(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    items = detail['queue']['items']
    target = next(e for e in items[3:] if e['page_id'])
    page.evaluate("o => SC.goChapter('improve', o)", dict(fingerprints=target['fingerprints']))
    assert page.locator('#coach h3').inner_text() == target['title']
    page.evaluate("o => SC.goChapter('improve', o)", dict(page_id=target['page_id']))
    expected = next(e for e in items if target['page_id'] in e['pages'])
    assert page.locator('#coach h3').inner_text() == expected['title']
    page.evaluate("o => SC.goChapter('improve', o)", dict(fingerprints=[]))        # an empty filter is never a dead end
    assert page.locator('#coach .fix-card').is_visible()
    assert not writes and not errors
    context.close()


def all_handled(detail):
    """Every fix-list item already decided (kept), so the list has nothing open."""
    for entry in enrich(detail, load_rubric())['queue']['items']:
        for fingerprint in entry['fingerprints']:
            detail['decisions'][fingerprint] = dict(action='keep', reason='Tracker', keep_reason='intentional')


def test_overview_with_everything_handled_routes_to_the_completion_moment(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview', prepare=all_handled)
    total = detail['queue']['counts']['total']
    assert detail['queue']['counts']['open'] == 0
    page.locator('#start-improving').click()
    page.wait_for_function("SC.currentChapter() === 'share'")                    # nothing left to fix: the way on is Sign off
    page.evaluate("SC.goChapter('improve')")
    assert page.locator('#coach h3').inner_text() == f'All {total} handled. Check your updated survey to confirm.'
    assert page.locator('#coach .card').count() == 0
    assert page.locator('#check-again-done').is_visible()
    assert page.get_by_role('button', name='Go to Sign off', exact=True).is_visible()
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('route', ['page', 'fingerprints', 'screen'])
def test_explicit_route_to_a_handled_item_still_allows_inspection(browser, base_url, route):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview', prepare=all_handled)
    entry = next(e for e in detail['queue']['items'] if e['page_id'])
    if route == 'screen':
        page.evaluate("SC.goChapter('improve')")
        page.evaluate("id => dispatchEvent(new CustomEvent('surveycoach-screen', {detail:id}))", entry['page_id'])
        expected = next(e for e in detail['queue']['items'] if entry['page_id'] in e['pages'])['title']
    else:
        options = dict(page_id=entry['page_id']) if route == 'page' else dict(fingerprints=entry['fingerprints'])
        page.evaluate("o => SC.goChapter('improve', o)", options)
        expected = next(e for e in detail['queue']['items'] if entry['page_id'] in e['pages'])['title'] if route == 'page' else entry['title']
    assert page.locator('#coach h3.headline').inner_text() == expected
    assert page.locator('#coach .fix-handled').is_visible()                      # handled, yet readable and undoable
    assert not writes and not errors
    context.close()


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


def test_pending_lock_survives_replacement_controls(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding, entry = single_paste(detail)
    focus(page, finding)
    hold_puts(page)
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#coach .issue-save-status').textContent === 'Saving…'")
    assert page.locator('#coach button').evaluate_all('bs => bs.length > 0 && bs.every(b => b.disabled)')     # the list ticked at once; every control is locked
    page.locator('#coach button').first.dispatch_event('click')                                           # a scripted second click
    page.locator('#fix-queue .fix-row').nth(1).click()                                                  # moving about re-renders the card
    page.locator(f'[data-fk="fix-row-{entry["id"]}"]').click()
    assert page.locator('#coach button:not([disabled])').count() == 0                                  # every control still locked
    assert page.evaluate('putCalls.length') == 1                                                       # still exactly one submit
    page.evaluate('pendingPuts.shift()()')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert page.evaluate('putCalls.length') == 1
    assert not errors
    context.close()
