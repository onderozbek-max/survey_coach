"""Sign off and Slack post (workstream 3C): ready, not ready with acknowledge, double click, failure and retry,
a new version, exact copy, links without tokens, developer flag, 390px. Intercepted synthetic reviews; offline."""
import re

import pytest
from playwright.sync_api import expect

from tests.signoff_helpers import earlier, open_signoff
from tests.test_site_e2e import base_url, browser


def reopen(page):
    page.reload()
    page.wait_for_function('SC.reviewReady === true')


def test_summary_card_has_the_facts_and_never_the_survey_address(browser, base_url):
    secret = 'https://tests.redjade.net/preview/synthetic?token=SECRET123#access=SECRET456'
    context, page, detail, posts, errors = open_signoff(browser, base_url, source_url=secret)
    card = page.locator('#review-card')
    facts = card.locator('dl').inner_text()
    assert detail['title'] in facts and 'v2' in facts and 'About 3½ minutes' in facts and 'Nov 5, 2026' in facts
    assert card.locator('.test-link').inner_text() == detail['share']['link'] == 'https://tests.redjade.net/preview/synthetic'
    assert card.locator('a').count() == 0     # plain text, never a live link
    assert 'Ready for sign-off' in card.locator('.state-chip').inner_text()
    assert 'Nothing open' in facts
    titles = [check['title'] for check in detail['overview']['you_check']]
    assert titles and all(title in card.inner_text() for title in titles)
    assert card.get_by_role('heading', name='Still to check', exact=False).count() == 0 and 'Done' in card.inner_text()   # ready: nothing left to check
    for text in (page.locator('body').inner_text(), page.locator('#chapter-share').inner_html()):
        assert 'SECRET' not in text and 'token=' not in text
    assert not posts and not errors
    context.close()


def test_slack_post_copies_exactly_and_announces_once(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, source_url='https://tests.redjade.net/p?token=SECRET123')
    assert page.locator('#slack-post').inner_text() == detail['share']['slack_post']
    assert page.locator('#chapter-share .btn-primary').all_inner_texts() == ['Copy Slack post']       # the one hero action
    page.get_by_role('button', name='Copy Slack post', exact=True).click()
    expect(page.locator('#toast')).to_have_text(re.compile('Copied'))
    assert page.evaluate('navigator.clipboard.readText()') == detail['share']['slack_post']
    assert 'SECRET' not in page.evaluate('navigator.clipboard.readText()')
    assert page.locator('[role=status], [aria-live]').filter(has_text='Copied').count() == 1
    assert page.locator('#download-summary').get_attribute('href') == '/api/surveys/synthetic/versions/2/summary?download=true'
    assert page.locator('#download-summary').inner_text() == 'Download summary'
    context.close()


def test_slack_copy_falls_back_to_a_textarea_when_the_clipboard_api_fails(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.evaluate("""() => {
      navigator.clipboard.writeText = () => Promise.reject(new Error('blocked'));
      window.__copied = [];
      const real = document.execCommand.bind(document);
      document.execCommand = command => {
        const shim = document.querySelector('.copy-shim');
        if (command !== 'copy' || !shim) return real(command);
        window.__copied.push(shim.value);
        return true;
      };
    }""")
    page.get_by_role('button', name='Copy Slack post', exact=True).click()
    expect(page.locator('#toast')).to_have_text(re.compile('Copied'))
    assert page.evaluate('window.__copied') == [detail['share']['slack_post']]
    context.close()


def test_a_ready_survey_signs_off_in_one_step_and_stays_calm(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.evaluate("localStorage.setItem('surveycoach-signoff-name', 'Priya N')")
    reopen(page)
    expect(page.locator('#signoff-name')).to_have_value('Priya N')                      # the last name used, from this browser
    assert page.locator('#signoff-ack').count() == 0
    page.get_by_role('button', name="I've reviewed this survey", exact=True).click()
    expect(page.locator('.signed-line')).to_have_text('Signed off by Priya N · Nov 5, 2026')
    assert posts == [{'name': 'Priya N', 'acknowledge_open': False}]
    assert page.locator('#signoff-form').count() == 0
    assert page.locator('canvas, .confetti, [class*=confetti]').count() == 0
    assert page.locator('#status').inner_text() == 'Signed off by Priya N.'               # one announcement
    page.get_by_role('button', name='Copy Slack post again').click()
    assert page.evaluate('navigator.clipboard.readText()') == detail['share']['slack_post']
    reopen(page)                                                                         # the record, not the form, after a reload
    expect(page.locator('.signed-line')).to_have_text('Signed off by Priya N · Nov 5, 2026')
    assert not errors
    context.close()


def test_the_name_is_remembered_locally_and_nowhere_else(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.locator('#signoff-name').fill('  Sam   Walton ')
    page.locator('#signoff-submit').click()
    page.locator('.signed-line').wait_for()
    assert posts == [{'name': 'Sam Walton', 'acknowledge_open': False}]                  # whitespace folded like the server does
    assert page.evaluate("localStorage.getItem('surveycoach-signoff-name')") == 'Sam Walton'
    context.close()


@pytest.mark.parametrize('name, message', [('', 'Enter your name.'), ('   ', 'Enter your name.'), ('x' * 81, 'Use 80 characters or fewer.')])
def test_name_errors_are_inline_and_nothing_is_sent(browser, base_url, name, message):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.locator('#signoff-name').fill(name)
    page.locator('#signoff-submit').click()
    expect(page.locator('#signoff-error')).to_have_text(message)
    expect(page.locator('#signoff-name')).to_have_attribute('aria-invalid', 'true')
    expect(page.locator('#signoff-name')).to_be_focused()
    assert 'signoff-error' in page.locator('#signoff-name').get_attribute('aria-describedby')
    page.locator('#signoff-name').fill('x' * 80)                                         # exactly 80 is allowed
    page.locator('#signoff-submit').click()
    page.locator('.signed-line').wait_for()
    assert posts == [{'name': 'x' * 80, 'acknowledge_open': False}]
    context.close()


def test_not_ready_needs_an_explicit_acknowledgement_and_keeps_the_counts(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=False)
    button = page.locator('#signoff-submit')
    assert button.inner_text() == 'Sign off with 3 open items'
    assert page.locator('label[for=signoff-ack]').inner_text() == 'I know 3 items are still open'
    assert page.locator('#signoff-open').inner_text() == 'Open now: 1 to fix · 1 to improve · 1 to check'
    page.locator('#signoff-name').fill('Priya N')
    button.click()                                                                       # not acknowledged: refused locally
    expect(page.locator('#signoff-error')).to_have_text('Tick the box to confirm 3 items are still open.')
    expect(page.locator('#signoff-ack')).to_be_focused()
    assert not posts
    page.locator('#signoff-ack').check()
    button.click()
    page.locator('.signed-line').wait_for()
    assert posts == [{'name': 'Priya N', 'acknowledge_open': True}]
    assert page.locator('#signoff-open').inner_text() == 'Open now: 1 to fix · 1 to improve · 1 to check'   # never hidden after signing
    assert 'Signed off with 3 open items.' in page.locator('.signoff-card').inner_text()
    assert page.locator('.open-at-signing li').count() == 3
    assert 'Q4 asks two things at once' in page.locator('.open-at-signing').inner_text()
    assert not errors
    context.close()


def test_a_ready_survey_never_sends_acknowledge_open_even_if_the_box_was_ticked_before(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=True)
    page.locator('#signoff-name').fill('Priya N')
    page.locator('#signoff-submit').click()
    page.locator('.signed-line').wait_for()
    assert posts[0]['acknowledge_open'] is False
    context.close()


def test_a_double_click_sends_one_request(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.route('**/api/surveys/*/versions/*/signoff', lambda route: (page.wait_for_timeout(300), route.fallback()))
    page.locator('#signoff-name').fill('Priya N')
    page.locator('#signoff-submit').dblclick()
    page.locator('.signed-line').wait_for()
    assert len(posts) == 1
    context.close()


def test_a_failed_sign_off_shows_the_error_and_retry_sends_it_again_by_hand(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    outcomes = [(500, {'detail': 'The disk is full.'})]
    fine = page.signoff_reply
    page.signoff_reply = lambda body: outcomes.pop(0) if outcomes else fine(body)
    page.locator('#signoff-name').fill('Priya N')
    page.locator('#signoff-submit').click()
    expect(page.locator('#signoff-error')).to_have_text('Sign-off was not saved. The disk is full.')
    expect(page.locator('#signoff-retry')).to_be_focused()
    page.wait_for_timeout(500)
    assert len(posts) == 1                                                               # no automatic retry
    expect(page.locator('#signoff-name')).to_have_value('Priya N')                       # nothing the user typed is lost
    assert page.locator('.signed-line').count() == 0
    page.locator('#signoff-retry').click()
    page.locator('.signed-line').wait_for()
    assert len(posts) == 2 and posts[0] == posts[1]
    assert page.locator('#signoff-retry').count() == 0
    context.close()


def test_a_new_version_is_unsigned_and_the_earlier_sign_off_is_listed_quietly(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, history=[earlier()])
    card = page.locator('.signoff-card')
    assert 'Version 2 has not been signed off yet.' in card.inner_text()
    assert page.locator('.signed-line').count() == 0 and page.locator('#signoff-form').count() == 1
    timeline = page.locator('.signoff-timeline li')
    assert timeline.all_inner_texts() == ['v1 signed off by Priya N · Nov 4, 2026 · with items open']
    page.locator('#signoff-submit').click()
    expect(page.locator('#signoff-error')).to_have_text('Enter your name.')
    context.close()


def test_after_signing_a_new_version_the_older_record_stays_in_the_timeline(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, history=[earlier()])
    page.locator('#signoff-name').fill('Lee')
    page.locator('#signoff-submit').click()
    expect(page.locator('.signed-line')).to_have_text('Signed off by Lee · Nov 5, 2026')
    assert page.locator('.signoff-timeline li').all_inner_texts() == ['v1 signed off by Priya N · Nov 4, 2026 · with items open']
    context.close()


def test_a_version_one_review_has_no_empty_comparison_and_no_stray_digits(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, version=1)
    text = page.locator('#chapter-share').inner_text()
    assert '0000' not in text and 'First version' not in text and 'no longer flagged' not in text
    assert page.locator('.round-timeline').count() == 0 and page.locator('#version-changes').inner_text().strip() == ''
    context.close()


def test_the_version_timeline_is_a_timeline_not_a_row_of_buttons(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, version=2)
    current = page.locator('.round-timeline [aria-current=page]')
    assert current.inner_text() == 'Version 2'
    for link in page.locator('.round-timeline a').all():
        style = link.evaluate('el => { const s = getComputedStyle(el); return [s.backgroundColor, s.borderTopWidth]; }')
        assert style == ['rgba(0, 0, 0, 0)', '0px']                                      # nothing that looks like a primary button
    context.close()


def test_the_snapshot_import_is_hidden_unless_the_page_has_the_developer_flag(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.locator('#check-again').click()
    assert page.locator('.advanced-recheck').is_hidden() and 'snapshot' not in page.locator('#recheck-dialog').inner_text().lower()
    context.close()
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.add_init_script('window.SURVEYCOACH_DEVELOPER = true;')
    reopen(page)
    page.locator('#check-again').click()
    assert page.locator('.advanced-recheck').is_visible()
    context.close()


def test_the_test_link_line_is_once_next_to_the_link_field_and_in_the_brief_words(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url)
    page.route('**/api/reader/mode', lambda route: route.fulfill(json={'notice': 'This reader blocks answer writes.'}))
    reopen(page)
    page.locator('#check-again').click()
    line = 'We open your test link like a member would. RedJade may record this as a test response. Exclude test responses before analysis.'
    assert page.locator('#reader-mode').inner_text() == line
    assert page.locator('body').inner_text().count('Exclude test responses before analysis.') == 1
    assert 'reader-mode' in page.locator('#survey-link').get_attribute('aria-describedby')
    context.close()


@pytest.mark.parametrize('ready', [True, False])
def test_sign_off_fits_a_phone_without_sideways_scrolling(browser, base_url, ready):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=ready, width=390, history=[earlier()])
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    for selector in ('#copy-slack', '#download-summary', '#signoff-submit', '#signoff-name'):
        assert page.locator(selector).bounding_box()['height'] >= 44, selector
    page.locator('#signoff-name').fill('Priya N')
    if not ready:
        page.locator('#signoff-ack').check()
    page.locator('#signoff-submit').click()
    page.locator('.signed-line').wait_for()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()


def test_sign_off_is_reachable_and_operable_by_keyboard_alone(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=False)
    page.locator('#signoff-name').focus()
    page.keyboard.type('Priya N')
    page.keyboard.press('Tab')
    expect(page.locator('#signoff-ack')).to_be_focused()
    page.keyboard.press('Space')
    page.keyboard.press('Tab')
    expect(page.locator('#signoff-submit')).to_be_focused()
    page.keyboard.press('Enter')
    page.locator('.signed-line').wait_for()
    expect(page.locator('#signoff-h')).to_be_focused()                                   # focus lands on the result, not nowhere
    assert posts == [{'name': 'Priya N', 'acknowledge_open': True}]
    context.close()
