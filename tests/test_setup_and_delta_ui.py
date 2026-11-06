"""The setup confirmation card and the "Since last version" card on the Verdict (workstream 3B). All writes intercepted."""
from tests.journey_helpers import add_setup, confirm_type_on_patch, delta, open_verdict, reward_endpoint
from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)

CARD = '#setup-card'


def words(locator):
    return ' '.join(locator.inner_text().split())


def open_setup(browser, base_url, *, confirmed=False, reward=None, fail_reward=0, width=1280):
    context, page, detail, writes, errors = open_verdict(browser, base_url, width=width,
                                                         prepare=lambda d: add_setup(d, confirmed=confirmed, reward=reward))
    confirm_type_on_patch(page, detail, writes)
    calls = reward_endpoint(page, detail, writes, fail_times=fail_reward)
    return context, page, detail, writes, errors, calls


def test_two_quick_checks_never_block_the_verdict(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url)
    card = page.locator(CARD)
    assert 'Two quick checks so the verdict is right' in card.inner_text()
    assert 'Looks like a concept test' in words(card) and 'Medium confidence' in card.locator('.setup-chip').inner_text()
    assert card.get_by_role('button', name='Confirm', exact=True).is_visible() and card.locator('#setup-type-change').is_visible()
    assert card.get_by_role('group', name='Does this survey offer a reward?').is_visible()
    assert page.locator('#overview-h').is_visible() and page.locator('#start-improving').is_enabled()       # the verdict is shown and usable
    assert page.locator('#survey-style').count() == 0
    assert not writes and not errors
    context.close()


def test_confirm_saves_the_detected_type_with_the_existing_endpoint_and_refetches(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url)
    gets = []
    page.on('request', lambda r: gets.append(r.url) if r.method == 'GET' and '/api/surveys/synthetic' in r.url else None)
    page.locator('#setup-confirm').click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Survey type saved'")
    assert writes == [{'survey_type': 'services_concept'}]
    assert gets                                                              # the verdict (and its time line) was refetched
    assert 'Survey type: Concept test' in words(page.locator(CARD))
    assert page.locator('#setup-confirm').count() == 0
    assert not errors
    context.close()


def test_change_offers_the_five_existing_types_and_saves_the_pick(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url)
    page.locator('#setup-type-change').click()
    labels = page.locator('#survey-style label').all_text_contents()
    assert [l.strip() for l in labels] == ['Community & fun', 'Product test', 'Home-use test', 'Concept or services', 'Market research']
    assert page.get_by_label('Concept or services', exact=True).is_checked()           # the detected type is preselected
    page.get_by_label('Home-use test', exact=True).click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Survey type saved'")
    assert writes == [{'survey_type': 'ihut'}]
    assert 'Survey type: Home-use test' in words(page.locator(CARD))
    context.close()


def test_a_failed_type_save_shows_the_error_with_retry_and_no_duplicate_write(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url)
    fail = {'on': True}

    def flaky(route):
        if route.request.method == 'PATCH' and fail['on']:
            return route.fulfill(status=503, json={'detail': 'Type not saved'})
        return route.fallback()
    page.route('**/api/surveys/synthetic', flaky)
    page.locator('#setup-confirm').click()
    page.locator('#setup-card .setup-error').wait_for()
    assert 'Type not saved' in page.locator('.setup-error').inner_text() and not writes
    assert page.locator('#setup-confirm').is_visible()                      # nothing was recorded; still unconfirmed
    fail['on'] = False
    page.locator('#setup-retry').click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Survey type saved'")
    assert writes == [{'survey_type': 'services_concept'}]
    context.close()


def test_reward_no_saves_false_and_both_answers_collapse_to_one_line(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url)
    page.locator('#setup-confirm').click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Survey type saved'")
    page.get_by_label('No', exact=True).click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Reward answer saved'")
    assert writes[-1] == {'has_reward': False, 'text': ''}
    line = page.locator(f'{CARD} .setup-line')
    assert ' '.join(line.inner_text().split()) == 'Survey type: Concept test · Reward: none Change'
    assert page.locator('#setup-h').count() == 0
    page.locator('#setup-change').click()                                     # Change opens both questions again
    assert page.locator('#survey-style').is_visible() and page.get_by_label('No', exact=True).is_checked()
    page.locator('#setup-done').click()
    assert page.locator(f'{CARD} .setup-line').is_visible()
    assert not errors
    context.close()


def test_reward_yes_takes_up_to_120_characters_and_shows_them_as_text(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url, confirmed=True)
    page.get_by_label('Yes', exact=True).click()
    box = page.locator('#reward-text')
    assert box.get_attribute('maxlength') == '120'
    box.fill('<img src=x onerror="window.injected=true">' + 'x' * 200)
    assert len(box.input_value()) == 120
    box.fill('<b>50 points</b>')
    page.locator('#reward-save').click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Reward answer saved'")
    assert writes == [{'has_reward': True, 'text': '<b>50 points</b>'}]
    assert 'Reward: <b>50 points</b>' in page.locator(CARD).inner_text()      # text, never markup
    assert page.locator(f'{CARD} b').count() == 0 and not page.evaluate('Boolean(window.injected)')
    context.close()


def test_a_failed_reward_save_reverts_shows_retry_and_retry_saves_once(browser, base_url):
    context, page, detail, writes, errors, calls = open_setup(browser, base_url, confirmed=True, fail_reward=1)
    page.get_by_label('No', exact=True).click()
    page.locator('.setup-error').wait_for()
    assert 'Reward not saved. Try again.' in page.locator('.setup-error').inner_text()
    assert not page.get_by_label('No', exact=True).is_checked() and not writes          # the optimistic answer was put back
    assert page.locator('#setup-h').is_visible()                                        # and the card is still asking
    page.locator('#setup-retry').click()
    page.wait_for_function("document.querySelector('#status').textContent === 'Reward answer saved'")
    assert writes == [{'has_reward': False, 'text': ''}] and calls['n'] == 2
    assert page.locator('.setup-error').count() == 0
    context.close()


def test_a_double_activation_sends_one_request(browser, base_url):
    context, page, detail, writes, errors, calls = open_setup(browser, base_url, confirmed=True)
    page.get_by_label('Yes', exact=True).click()
    page.locator('#reward-text').fill('Earn 50 points')
    page.evaluate("() => { const b = document.querySelector('#reward-save'); b.click(); b.click(); }")
    page.wait_for_function("document.querySelector('#status').textContent === 'Reward answer saved'")
    assert calls['n'] == 1 and len(writes) == 1
    context.close()


def test_when_both_are_answered_the_card_starts_collapsed(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url, confirmed=True, reward={'has_reward': True, 'text': 'Earn 50 points'})
    line = page.locator(f'{CARD} .setup-line')
    assert ' '.join(line.inner_text().split()) == 'Survey type: Concept test · Reward: Earn 50 points Change'
    assert page.locator('#setup-confirm, #reward-save, #survey-style').count() == 0
    context.close()


def test_without_the_setup_fields_there_is_no_card(browser, base_url):
    """The sample data now carries the fields, so "the server did not send them" is made explicit here."""
    context, page, detail, writes, errors = open_verdict(
        browser, base_url, prepare=lambda d: [d.pop(field, None) for field in ('survey_type_detection', 'reward')])
    assert page.locator(CARD).count() == 0
    context.close()


def test_the_verdict_keeps_one_primary_button_whatever_the_setup_card_is_asking(browser, base_url):
    """Start fixing is the one primary action (board-redesign contract). The setup card's Confirm and Save are quiet."""
    context, page, detail, writes, errors, _ = open_setup(browser, base_url)
    page.get_by_label('Yes', exact=True).click()
    assert page.locator('#reward-save').is_visible() and page.locator('#setup-confirm').is_visible()
    primaries = page.locator('#chapter-overview .btn-primary')
    assert primaries.count() == 1 and primaries.first.get_attribute('id') == 'start-improving'
    context.close()


def test_setup_card_is_usable_at_390_without_page_scroll(browser, base_url):
    context, page, detail, writes, errors, _ = open_setup(browser, base_url, width=390)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    for control in ('#setup-confirm', '#setup-type-change'):
        assert page.locator(control).bounding_box()['height'] >= 44
    page.get_by_label('Yes', exact=True).click()
    assert page.locator('#reward-text').bounding_box()['height'] >= 44
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()


# ---- Since last version -------------------------------------------------------------------

def open_delta(browser, base_url, payload, version=2, width=1280):
    def prepare(detail):
        detail['version'] = version
        detail['version_delta'] = payload
    return open_verdict(browser, base_url, width=width, prepare=prepare)


def test_version_one_has_no_delta_card_at_all(browser, base_url):
    context, page, detail, writes, errors = open_delta(browser, base_url, None, version=1)
    assert page.locator('#version-delta').count() == 0
    assert 'Since last version' not in page.locator('#chapter-overview').inner_text()
    assert 'First version' not in page.locator('#chapter-overview').inner_text()
    context.close()


def test_version_two_shows_the_served_summary_caveat_and_every_bucket(browser, base_url):
    context, page, detail, writes, errors = open_delta(browser, base_url, delta((4, 1, 0, 1)))
    card = page.locator('#version-delta')
    assert card.get_by_role('heading', name='Since last version').is_visible()
    assert card.locator('.delta-summary').inner_text() == "4 fixed · 1 still open · 0 new · 1 couldn't compare"
    assert 'Fixed = no longer flagged by our checks.' in card.inner_text()
    assert card.locator('.delta-fixed-item').count() == 4
    assert card.locator('[data-bucket=still]').inner_text().startswith('Still open (1)')
    assert card.locator('[data-bucket=new]').count() == 0                      # an empty bucket draws nothing
    assert page.locator('#chapter-overview > :nth-child(2)').get_attribute('id') == 'version-delta'       # it leads, right after the hero
    context.close()


def test_a_fixed_item_expands_to_before_and_after_and_names_a_rewrite(browser, base_url):
    context, page, detail, writes, errors = open_delta(browser, base_url, delta((2, 0, 0, 0)))
    items = page.locator('#version-delta .delta-fixed-item')
    first = items.nth(0)
    assert not first.get_attribute('open') and not first.locator('blockquote').first.is_visible()
    first.locator('summary').click()
    snippets = first.locator('.delta-snippet')
    assert snippets.nth(0).inner_text().split('\n')[0].upper() == 'BEFORE' and 'Before 0' in snippets.nth(0).inner_text()
    assert 'After 0' in snippets.nth(1).inner_text()
    assert 'Fixed with your rewrite' in first.inner_text()
    items.nth(1).locator('summary').click()
    assert 'No longer flagged' in items.nth(1).inner_text()
    context.close()


def test_a_missing_before_or_after_is_left_out_not_invented(browser, base_url):
    payload = delta((1, 0, 0, 0))
    payload['fixed'][0].update(before=None)
    context, page, detail, writes, errors = open_delta(browser, base_url, payload)
    item = page.locator('#version-delta .delta-fixed-item').first
    item.locator('summary').click()
    assert item.locator('.delta-snippet').count() == 1 and 'After 0' in item.inner_text() and 'Before' not in item.inner_text()
    context.close()


def test_couldnt_compare_is_always_visible_when_there_is_one(browser, base_url):
    context, page, detail, writes, errors = open_delta(browser, base_url, delta((0, 0, 0, 2)))
    box = page.locator('#version-delta .delta-uncertain')
    assert box.is_visible() and "2 items we couldn't compare" in box.inner_text()
    assert box.locator('li').count() == 2 and box.locator('li').first.is_visible()      # no click needed
    assert 'Not verified' in box.inner_text()
    context.close()


def test_no_uncertain_box_when_everything_compared(browser, base_url):
    context, page, detail, writes, errors = open_delta(browser, base_url, delta((3, 0, 0, 0)))
    assert page.locator('#version-delta .delta-uncertain').count() == 0
    context.close()


def test_delta_text_is_escaped_and_the_card_fits_390(browser, base_url):
    payload = delta((1, 0, 0, 1))
    payload['fixed'][0].update(before='<img src=x onerror="window.injected=true">', headline='<b>bold</b>')
    context, page, detail, writes, errors = open_delta(browser, base_url, payload, width=390)
    page.locator('#version-delta .delta-fixed-item summary').click()
    assert page.locator('#version-delta img, #version-delta b').count() == 0
    assert not page.evaluate('Boolean(window.injected)')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()
