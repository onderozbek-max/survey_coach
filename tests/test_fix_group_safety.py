"""A grouped fix card (one item, several members) keeps the old pattern-panel safety rules, against the real server.

Replaces test_pattern_individual_writes_and_undo_restores_prior_objects, test_pattern_partial_save_never_claims_all_success
and test_pattern_superseded_earlier_row_stops_before_later_write_or_copy: one PUT per member in order, a partial save never
says everything worked, a newer choice stops the batch before any later write, and Undo only rolls back what its own save wrote,
restoring each member's prior decision object (reason, manual_done) rather than blanking it."""
import pytest

from tests.fixflow_helpers import detail_of, flow, open_flow  # noqa: F401  (flow is a fixture)
from tests.test_improve_ui import hold_puts
from tests.test_site_e2e import browser  # noqa: F401


def open_group(browser, flow):
    context, page, errors = open_flow(browser, flow)
    group = next(e for e in detail_of(page)['queue']['items'] if e['action_kind'] == 'paste' and e['count'] > 1)
    page.locator('#fix-queue .fix-row', has_text=group['title']).first.click()
    return context, page, errors, group


def test_group_add_writes_each_member_and_undo_restores_prior_objects(browser, flow):
    context, page, errors, group = open_group(browser, flow)
    first, *rest = group['fingerprints']
    puts = []
    page.on('request', lambda r: puts.append(r.post_data_json) if r.method == 'PUT' and '/decisions/' in r.url else None)
    page.evaluate("fp => { SC.workspaceDetail.decisions[fp] = {action:'keep', reason:'Tracker', manual_done:true, keep_reason:'intentional'}; }", first)
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.includes('(3)')")
    assert [p['action'] for p in puts] == ['pick'] * 3
    page.locator('#undo').click()
    page.wait_for_function('n => true', timeout=1000)
    page.wait_for_timeout(500)
    assert len(puts) == 6
    assert puts[3]['action'] == 'keep' and puts[3]['reason'] == 'Tracker' and puts[3]['manual_done'] is True     # the prior object, not a blank one
    assert [p['action'] for p in puts[4:]] == ['open', 'open']
    assert not errors
    context.close()


def test_group_partial_save_never_claims_all_success_and_undo_only_undoes_what_saved(browser, flow):
    context, page, errors, group = open_group(browser, flow)
    puts = []
    page.on('request', lambda r: puts.append(r.post_data_json) if r.method == 'PUT' and '/decisions/' in r.url else None)
    failing = group['fingerprints'][1]
    page.route(f'**/decisions/{failing}', lambda r: r.fulfill(status=503, json={}))
    page.evaluate("navigator.clipboard.writeText('unchanged')")
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('1 of 3 saved')")
    assert len([p for p in puts if p['action'] == 'pick']) == 2                 # the second one was tried once; the third never started
    assert 'Added to My changes' not in page.locator('#toast').inner_text()
    assert page.locator('#coach .fix-error').is_visible() and page.locator('#retry-save').is_visible()
    assert page.evaluate('navigator.clipboard.readText()') == 'unchanged'       # saving never touches the clipboard
    assert page.locator('#queue-progress').inner_text().startswith('0 of')       # the card is still open
    page.locator('#undo').click()
    page.wait_for_timeout(400)
    assert puts[-1]['action'] == 'open' and len(puts) == 3                      # only the member that saved is rolled back
    assert not errors
    context.close()


@pytest.mark.parametrize('changed_index, saved', [(0, 1), (2, 2)])
# (0, 1): the member already in flight is superseded, so its own save is discarded and nothing at all counts as saved.
# (2, 2): two members saved, then the third (not yet started) was superseded: the batch stops there, two are reported.
def test_group_batch_stops_when_a_newer_choice_arrives_and_never_writes_later_members(browser, flow, changed_index, saved):
    context, page, errors, group = open_group(browser, flow)
    hold_puts(page)
    page.locator('#use-change').click()
    page.wait_for_function('putCalls.length === 1')
    if saved == 2:
        page.evaluate('pendingPuts.shift()()')
        page.wait_for_function('putCalls.length === 2')
    fp = group['fingerprints'][changed_index]
    # An authoritative newer edit arrives from outside the locked card.
    page.evaluate("fp => { SC.decisionRevisions.set(fp, 9); SC.workspaceDetail.decisions[fp] = {action:'keep', reason:'Newer choice'}; }", fp)
    page.evaluate('pendingPuts.shift()()')
    if saved == 1:
        page.locator('#coach .fix-error').wait_for()
        page.wait_for_timeout(300)
        assert page.evaluate('putCalls.length') == 1 and page.locator('#undo').count() == 0     # nothing saved, nothing to undo
        assert page.evaluate('SC.workspaceDetail.decisions')[fp]['reason'] == 'Newer choice'
        context.close()
        return
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('2 of 3')")
    page.wait_for_timeout(300)
    assert page.evaluate('putCalls.length') == saved                            # nothing after the interruption was written
    page.locator('#undo').click()
    restores = saved - (changed_index < saved)                                  # a member with a newer choice is left alone
    for index in range(1, restores + 1):
        page.wait_for_function('n => putCalls.length === n', arg=saved + index)
        assert page.evaluate('putCalls.at(-1).action') == 'open'
        page.evaluate('pendingPuts.shift()()')
    page.wait_for_timeout(300)
    assert page.evaluate('putCalls.length') == saved + restores
    assert page.evaluate('SC.workspaceDetail.decisions')[fp]['reason'] == 'Newer choice'
    assert not errors
    context.close()
