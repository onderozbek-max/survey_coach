"""The fix flow (workstream 2B) against a real server holding the synthetic concept survey. Offline."""
import re

from tests.fixflow_helpers import detail_of, flow, open_flow  # noqa: F401  (flow is a fixture)
from tests.test_site_e2e import browser  # noqa: F401

STATES = ['Fix before launch', 'Worth improving', 'You check']
KEEP = ['Intentional', 'Owner decided', 'Not applicable', 'Other']


def watch_puts(page):
    puts = []
    page.on('request', lambda r: puts.append(r.post_data_json) if r.method == 'PUT' and '/decisions/' in r.url else None)
    return puts


def select_kind(page, kind):
    """Click list rows until the card shows an item of this action kind."""
    rows = page.locator('#fix-queue .fix-row')
    for index in range(rows.count()):
        rows.nth(index).click()
        if page.locator(f'#coach .fix-card[data-action={kind}]').count():
            return page.locator('#coach .fix-card')
    raise AssertionError(f'no {kind} item in the list')


def visible_words(card):
    """Words in the card body: why it matters plus the one action (pasted wording and Details are not body)."""
    text = card.evaluate("""c => [...c.querySelectorAll('.why, .fix-steps li, .check-question')].map(e => e.textContent).join(' ')""")
    return len(text.split())


# --- the list ------------------------------------------------------------------------------------

def test_one_ordered_list_one_progress_and_no_tabs(browser, flow):
    context, page, errors = open_flow(browser, flow)
    queue = detail_of(page)['queue']
    rows = page.locator('#fix-queue .fix-row')
    assert rows.count() == queue['counts']['total'] == len(queue['items'])
    assert page.get_by_role('tab').count() == 0
    assert [rows.nth(i).locator('.fix-row-title').inner_text() for i in range(rows.count())] == [e['title'] for e in queue['items']]
    first_states = [rows.nth(i).locator('.fix-row-state').inner_text() for i in range(rows.count())]
    assert first_states == sorted(first_states, key=lambda s: STATES.index(s))
    assert rows.first.locator('.screen-chip').inner_text().startswith('Screen')
    assert page.locator('#queue-progress').inner_text() == f"0 of {queue['counts']['total']} done"
    assert page.locator('.progress-ring').count() == 1 and page.locator('[aria-live=polite]:has-text("of")').count() >= 1
    assert page.locator('#queue-progress').evaluate("e => e.getAttribute('aria-live')") == 'polite'
    assert not errors
    context.close()


def test_filter_chips_and_the_verdict_state_param(browser, flow):
    context, page, errors = open_flow(browser, flow)
    page.locator('.fix-filters').get_by_role('button', name=re.compile('^You check')).click()
    titles = page.locator('#fix-queue .fix-row-state').all_inner_texts()
    assert titles and set(titles) == {'You check'}
    page.locator('.fix-filters').get_by_role('button', name=re.compile('^You check')).click()      # pressing again shows everything
    assert len(set(page.locator('#fix-queue .fix-row-state').all_inner_texts())) > 1
    # The Verdict tiles route here with a state.
    page.evaluate("SC.goChapter('overview')")
    page.evaluate("SC.goChapter('improve', {state:'worth_improving'})")
    assert set(page.locator('#fix-queue .fix-row-state').all_inner_texts()) == {'Worth improving'}
    assert page.locator('#coach .fix-card .state-chip').inner_text() == 'Worth improving'
    assert not errors
    context.close()


# --- the card ------------------------------------------------------------------------------------

def test_every_card_has_the_same_anatomy(browser, flow):
    context, page, errors = open_flow(browser, flow)
    seen = set()
    rows = page.locator('#fix-queue .fix-row')
    for index in range(rows.count()):
        rows.nth(index).click()
        card = page.locator('#coach .fix-card')
        kind = card.get_attribute('data-action')
        seen.add(kind)
        assert card.locator('.state-chip').count() == 1
        assert card.locator('h3.headline').inner_text() == page.locator('.fix-row').nth(index).locator('.fix-row-title').inner_text()
        assert card.locator('details.more').evaluate('d => !d.open')
        assert card.get_by_role('button', name='Mark done in RedJade').count() == 1
        assert card.get_by_role('button', name='Keep as is…').count() == 1
        assert (card.get_by_role('button', name='Add to my changes').count() == 1) == (kind == 'paste')
        fixes = card.locator('.fix-paste, .fix-steps, .fix-check').count()
        assert fixes == 1, kind
        assert visible_words(card) <= 45
        for old in ('Use this change', 'Skip for now', 'Must-fix', 'Quick win'):
            assert old not in card.inner_text()
    assert seen == {'paste', 'steps', 'you_check'} or seen == {'paste', 'you_check'}
    assert not errors
    context.close()


def test_paste_card_shows_after_text_first_then_changes_and_copies(browser, flow):
    context, page, errors = open_flow(browser, flow)
    card = select_kind(page, 'paste')
    order = card.locator('.fix-paste').evaluate("e => [...e.children].map(c => c.className || c.tagName)")
    assert order[1] in ('after-text', 'suggestion-bundle', 'suggestion-answer') or 'after' in order[1]
    after = card.locator('.after-text').inner_text()
    assert card.locator('.field-hints li').first.inner_text().startswith('RedJade > ')
    assert card.locator('.changes').is_hidden()
    toggle = card.get_by_role('button', name='Show changes')
    toggle.click()
    assert toggle.get_attribute('aria-expanded') == 'true' and card.locator('.changes .diff').is_visible()
    card.get_by_role('button', name='Copy the new wording').click()
    page.locator('#toast').wait_for()
    assert page.locator('#toast').inner_text().startswith('Copied')
    assert page.evaluate('navigator.clipboard.readText()') == after
    assert not errors
    context.close()


def test_add_to_my_changes_applies_to_the_whole_group_and_fills_the_tray(browser, flow):
    context, page, errors = open_flow(browser, flow)
    puts = watch_puts(page)
    detail = detail_of(page)
    group = next(e for e in detail['queue']['items'] if e['action_kind'] == 'paste' and e['count'] > 1)
    page.locator('#fix-queue .fix-row', has_text=group['title']).first.click()
    card = page.locator('#coach .fix-card')
    assert card.locator('> .location').inner_text() == 'Applies to Q4, Q6 and Q8 (screens 5, 7 and 9)'
    assert page.locator('#tray-toggle').inner_text().startswith('My changes (0)')
    page.locator('#tray-toggle').click()
    assert page.locator('#tray-panel').inner_text().strip() == 'Nothing added yet'
    card.get_by_role('button', name='Add to my changes').click()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.includes('(3)')")
    assert [p['action'] for p in puts] == ['pick'] * 3 and len({p['picked_text'] for p in puts}) == 1
    my = detail_of(page)['my_changes']
    assert my['count'] == 3
    page.locator('#tray-copy-all').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.startsWith('Copied')")
    assert page.evaluate('navigator.clipboard.readText()') == my['copy_all_text']
    page.locator('.tray-copy').nth(1).click()
    page.wait_for_function('text => navigator.clipboard.readText().then(c => c === text)', arg=my['items'][1]['copy_text'])
    row = page.locator('#fix-queue .fix-row', has_text=group['title']).first
    assert 'Added to My changes' in row.inner_text()
    assert page.locator('#queue-progress').inner_text().startswith('1 of ')
    assert not errors
    context.close()


def test_mark_done_and_keep_with_a_reason_chip(browser, flow):
    context, page, errors = open_flow(browser, flow)
    puts = watch_puts(page)
    card = select_kind(page, 'paste')
    title = card.locator('h3').inner_text()
    card.get_by_role('button', name='Mark done in RedJade').click()
    page.wait_for_function("document.querySelector('#toast') !== null")
    assert puts[-1]['action'] == 'done'
    assert 'Marked done, not checked yet' in page.locator('#fix-queue .fix-row', has_text=title).first.inner_text()
    other = page.locator('#coach .fix-card')
    other.get_by_role('button', name='Keep as is…').click()
    save = other.get_by_role('button', name='Keep as is', exact=True)
    assert save.is_disabled()
    assert [b.inner_text() for b in other.locator('.reason-chip').all()] == KEEP
    assert other.locator('#keep-note').get_attribute('maxlength') == '200'
    other.get_by_role('button', name='Owner decided').click()
    other.locator('#keep-note').fill('Priya signed off')
    save.click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Kept')")
    assert puts[-1]['action'] == 'keep' and puts[-1]['keep_reason'] == 'owner_decided' and puts[-1]['reason'] == 'Priya signed off'
    assert not errors
    context.close()


def test_you_check_needs_the_checkbox_before_done(browser, flow):
    context, page, errors = open_flow(browser, flow)
    card = select_kind(page, 'you_check')
    done = card.get_by_role('button', name='Mark done in RedJade')
    assert done.is_disabled()
    card.get_by_label('I checked').check()
    assert done.is_enabled()
    assert not errors
    context.close()


# --- safety: no duplicate submit, clear error and retry, no wrong advance -------------------------

def test_a_slow_save_is_submitted_once_and_moves_on_only_from_its_own_item(browser, flow):
    context, page, errors = open_flow(browser, flow)
    puts = watch_puts(page)
    card = select_kind(page, 'paste')
    title = card.locator('h3').inner_text()
    held = []
    page.route('**/decisions/*', lambda route: held.append(route) if not held else route.continue_())
    card.get_by_role('button', name='Add to my changes').click()
    page.wait_for_function("document.querySelector('#coach .issue-save-status').textContent === 'Saving…'")
    assert page.locator('#coach .decision-actions button, #coach .fix-handled button').evaluate_all('bs => bs.every(b => b.disabled)')
    page.locator('#coach .fix-handled button, #coach .decision-actions button').first.click(force=True)    # a second click goes nowhere
    page.locator('#fix-queue .fix-row').nth(1).click()           # the user moves on to another item
    other = page.locator('#coach h3.headline').inner_text()
    assert other != title
    held[0].continue_()
    page.wait_for_function("document.querySelector('#toast') !== null")
    page.wait_for_timeout(300)
    assert page.locator('#coach h3.headline').inner_text() == other     # the late save did not drag the user back or forward
    assert len([p for p in puts if p['action'] == 'pick']) >= 1
    assert not errors
    context.close()


def test_a_failed_save_says_so_keeps_the_item_open_and_retries_only_on_request(browser, flow):
    context, page, errors = open_flow(browser, flow)
    puts = watch_puts(page)
    card = select_kind(page, 'paste')
    title = card.locator('h3').inner_text()
    page.route('**/decisions/*', lambda route: route.fulfill(status=503, json={'detail': 'Unavailable'}))
    card.get_by_role('button', name='Add to my changes').click()
    alert = page.locator('#coach .fix-error')
    alert.wait_for()
    page.wait_for_timeout(300)
    assert len(puts) == 1                                               # nothing retried by itself
    assert 'Not saved' in alert.inner_text() or 'saved' in alert.inner_text().lower()
    assert page.locator('#coach h3.headline').inner_text() == title       # no advance
    assert page.locator('#queue-progress').inner_text().startswith('0 of')
    assert page.locator('#tray-toggle').inner_text().startswith('My changes (0)')
    page.unroute('**/decisions/*')
    page.locator('#retry-save').click()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.includes('(3)')")
    assert not errors
    context.close()


# --- end states ----------------------------------------------------------------------------------

def test_a_screen_with_nothing_to_fix_shows_a_compact_row_and_the_next_item(browser, flow):
    context, page, errors = open_flow(browser, flow)
    detail = detail_of(page)
    covered = {p for e in detail['queue']['items'] for p in e['pages']}
    free = next(s for s in detail['screens'] if s['page_id'] not in covered)
    page.evaluate("pageId => dispatchEvent(new CustomEvent('surveycoach-screen', {detail:pageId}))", free['page_id'])
    row = page.locator('#coach .nothing-here')
    assert row.locator('h3').inner_text() == 'Nothing to fix on this screen'
    assert row.locator('svg').count() == 1
    nxt = row.get_by_role('button', name=re.compile(r'^Next item: .+ →$'))
    assert page.locator('#fix-queue .fix-row[aria-current=true]').count() == 1       # the user keeps their place in the list
    boxes = row.evaluate("e => [...e.children].map(c => c.getBoundingClientRect()).map(r => [r.left, r.top, r.right, r.bottom])")
    for a, b in zip(boxes, boxes[1:]):
        assert a[2] <= b[0] + 1 or a[3] <= b[1] + 1, 'children of the row overlap'
    nxt.click()
    assert page.locator('#coach .fix-card').count() == 1
    assert not errors
    context.close()


def test_handling_everything_ends_in_the_completion_moment(browser, flow):
    context, page, errors = open_flow(browser, flow)
    total = detail_of(page)['queue']['counts']['total']
    for _ in range(total):
        card = page.locator('#coach .fix-card')
        if card.get_by_label('I checked').count():
            card.get_by_label('I checked').check()
        card.get_by_role('button', name='Mark done in RedJade').click()
        page.wait_for_function("document.querySelector('#toast') !== null")
        page.wait_for_timeout(150)
    heading = page.locator('#coach .completion h3')
    assert heading.inner_text() == f'All {total} handled. Check your updated survey to confirm.'
    assert page.locator('#queue-progress').inner_text() == f'{total} of {total} done'
    assert page.locator('.celebrate-mark').evaluate("e => getComputedStyle(e).backgroundImage") == 'none'
    page.get_by_role('button', name='Check again').last.click()
    page.locator('#recheck-dialog').wait_for(state='visible')
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Go to Sign off').click()
    page.wait_for_function("location.hash === '#share'")
    assert not errors
    context.close()


def test_the_celebration_stands_still_when_motion_is_reduced(browser, flow):
    context, page, errors = open_flow(browser, flow)
    page.emulate_media(reduced_motion='reduce')
    page.evaluate("document.body.append(Object.assign(document.createElement('div'), {className:'celebrate-mark', id:'probe'}))")
    assert page.locator('#probe').evaluate("e => getComputedStyle(e).animationName") == 'none'
    assert page.locator('.progress-ring').evaluate("e => getComputedStyle(e).transitionDuration") in ('0s', '0.001s')
    context.close()


# --- the toggle and the drawers ---------------------------------------------------------------------

def test_with_my_changes_is_disabled_until_there_is_one(browser, flow):
    context, page, errors = open_flow(browser, flow)
    toggle = page.get_by_role('button', name='With my changes (0)')
    assert toggle.is_disabled() and toggle.get_attribute('title')
    select_kind(page, 'paste').get_by_role('button', name='Add to my changes').click()
    page.get_by_role('button', name='With my changes (3)').wait_for()
    page.get_by_role('button', name='With my changes (3)').click()
    line = page.locator('.preview-effect').inner_text().lower()
    assert not any(word in line for word in ('hypothetical', 'accepted', 'saved'))
    assert not errors
    context.close()


def test_all_screens_drawer_is_labelled_flagged_from_the_queue_and_keyboard_safe(browser, flow):
    context, page, errors = open_flow(browser, flow)
    page.locator('#all-screens').focus()
    page.keyboard.press('Enter')
    drawer = page.locator('#screen-drawer')
    assert page.get_by_label('Search screens', exact=True).count() == 1
    assert 'Q label' not in drawer.inner_text() and drawer.locator('#screen-search').get_attribute('placeholder') is None
    close = drawer.get_by_role('button', name='Close all screens')
    assert close.locator('svg').count() == 1 and close.inner_text().strip() == ''
    queue = detail_of(page)['queue']['items']
    first = drawer.locator('.screen-row').first
    assert first.locator('.state-chip').inner_text().strip()               # icon plus words, never colour alone
    welcome = next(r for r in drawer.locator('.screen-row').all() if 'Welcome' in r.inner_text())
    expected = sum(1 for e in queue if 'p0' in e['pages'])
    assert (expected == 0) == ('Nothing to fix' in welcome.inner_text())
    for _ in range(12):                                                   # focus never leaves the modal drawer
        page.keyboard.press('Tab')
        assert page.evaluate("!!document.activeElement.closest('#screen-drawer')")
    page.keyboard.press('Escape')
    assert not page.locator('#screen-drawer').is_visible()
    assert page.evaluate("document.activeElement.id") == 'all-screens'
    assert not errors
    context.close()


def test_keyboard_path_list_to_card_to_tray(browser, flow):
    context, page, errors = open_flow(browser, flow)
    row = page.locator('#fix-queue .fix-row').first
    row.focus()
    page.keyboard.press('Enter')
    assert page.evaluate("document.activeElement.id") == 'coach-h'         # the card takes focus
    page.locator('#coach .fix-card').get_by_role('button', name='Add to my changes').focus()
    page.keyboard.press('Enter')
    page.get_by_role('button', name=re.compile(r'^My changes \(\d+\)')).wait_for()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.includes('(3)')")
    page.locator('#tray-toggle').focus()
    page.keyboard.press('Space')
    assert page.locator('#tray-toggle').get_attribute('aria-expanded') == 'true'
    page.locator('#tray-copy-all').focus()
    page.keyboard.press('Enter')
    page.wait_for_function("document.querySelector('#toast')?.textContent.startsWith('Copied')")
    assert page.locator('#toast-region').get_attribute('aria-live') == 'polite'
    assert not errors
    context.close()


# --- responsive and accessible -----------------------------------------------------------------------

def test_layout_columns_drawer_and_no_horizontal_scroll(browser, flow):
    for width in (1440, 1024, 390):
        context, page, errors = open_flow(browser, flow, width=width)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        list_box = page.locator('#fix-queue').bounding_box()
        stage = page.locator('#stage').bounding_box()
        card = page.locator('#coach').bounding_box()
        if width >= 1024:
            assert list_box['x'] < stage['x'] < card['x']                   # list, phone, card
            assert not page.locator('#fix-list-open').is_visible()
        else:
            assert not page.locator('#fix-queue').is_visible()
            assert stage['y'] < card['y']                                   # phone, then card
            page.locator('#fix-list-open').click()
            assert page.locator('#fix-drawer .fix-row').count() == detail_of(page)['queue']['counts']['total']
            page.locator('#fix-drawer .fix-row').nth(2).click()
            assert not page.locator('#fix-drawer').is_visible()
            assert page.evaluate("document.activeElement.id") == 'coach-h'
        context.close()


def test_targets_are_44px_and_state_is_never_colour_alone(browser, flow):
    context, page, errors = open_flow(browser, flow)
    select_kind(page, 'paste')
    small = page.evaluate("""() => [...document.querySelectorAll('#coach button, #fix-queue button, .fix-filters button, .queue-tools button, #tray-toggle')]
      .filter(b => b.offsetParent && b.getBoundingClientRect().height < 43.5).map(b => b.textContent.trim())""")
    assert small == []
    for state in page.locator('#fix-queue .fix-row').all():
        assert state.locator('svg').count() >= 1 and state.locator('.fix-row-state').inner_text().strip()
    page.locator('#coach-h').focus()
    page.keyboard.press('Tab')                                            # keyboard focus must be visible
    ring = page.evaluate("() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, parseFloat(s.outlineWidth)]; }")
    assert ring[0] != 'none' and ring[1] >= 2
    context.close()


def test_the_tray_never_hides_the_last_list_rows(browser, flow):
    """3E: the fixed My changes tray sat on top of the bottom of the list. The list pads itself by the tray's own height."""
    context, page, errors = open_flow(browser, flow, width=1440, height=560)       # a short window, so the list scrolls
    tray, queue = page.locator('.my-changes'), page.locator('#fix-queue')
    padding = "() => Math.abs(parseFloat(getComputedStyle(document.querySelector('#fix-queue .fix-rows')).paddingBottom) - document.querySelector('.my-changes').getBoundingClientRect().height) <= 1"

    def last_row_clear_of_tray():
        page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')           # the list is pinned (sticky) at the bottom of the page
        queue.evaluate('e => { e.scrollTop = e.scrollHeight; }')
        last, bar = page.locator('#fix-queue .fix-row').last.bounding_box(), tray.bounding_box()
        return last['y'] + last['height'] <= bar['y'] + 1, (last, bar)

    assert queue.evaluate('e => e.scrollHeight > e.clientHeight')
    page.wait_for_function(padding)
    assert last_row_clear_of_tray()[0], last_row_clear_of_tray()
    page.locator('#tray-toggle').click()                                           # opening the tray makes it taller; the padding follows
    page.wait_for_function(padding)
    assert tray.bounding_box()['height'] > 60 and last_row_clear_of_tray()[0], last_row_clear_of_tray()
    assert not errors
    context.close()
