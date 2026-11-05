"""The fix flow (workstream 2B) against a real server holding the synthetic concept survey. Offline."""
import re

from tests.fixflow_helpers import detail_of, flow, open_flow  # noqa: F401  (flow is a fixture)
from tests.test_site_e2e import browser  # noqa: F401

STATES = ['Fix before launch', 'Worth improving', 'You check']
KEEP = ['Intentional', 'Owner decided', 'Not applicable', 'Other']


def put_count(puts):
    return len(puts)


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
    card = select_kind(page, 'steps') if page.locator('.fix-card[data-action=steps]').count() else select_kind(page, 'paste')
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
