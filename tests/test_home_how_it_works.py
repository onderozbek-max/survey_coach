"""Home (workstream 3C): the logo, the three-step row, the interactive example, no false "Checking…", 390px.
Static page with intercepted survey lists; offline."""
import re

import pytest
from playwright.sync_api import expect

from tests.test_site_e2e import base_url, browser

OLD = 'How satisfied are you with the taste and price?'
NEW = 'How satisfied are you with the taste?'


def home(browser, base_url, width=1280, surveys=(), reduced='no-preference'):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion=reduced)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/api/surveys', lambda route: route.fulfill(json={'surveys': list(surveys)}))
    page.goto(base_url + 'local.html')
    page.locator('#how-steps li').first.wait_for()
    return context, page, errors


def test_the_logo_has_one_accessible_name_on_home_and_in_the_review_header(browser, base_url):
    context, page, errors = home(browser, base_url)
    logo = page.get_by_role('img', name='SurveyCoach', exact=True)
    expect(logo).to_have_count(1)
    assert logo.evaluate('el => el.tagName.toLowerCase()') == 'svg' and logo.locator('path, rect').count() >= 4
    assert page.locator('.brand-mark').count() == 0                                       # the plain blue square is gone
    assert page.get_by_role('link', name='SurveyCoach home').count() == 1
    box = logo.bounding_box()
    assert box['width'] == 32 and box['height'] == 32
    for shape in logo.locator('.lm-phone, .lm-screen').all():
        assert shape.evaluate('el => getComputedStyle(el).stroke') == 'none'
    context.close()
    context = browser.new_context(viewport={'width': 390, 'height': 800})
    review = context.new_page()
    review.route('**/api/**', lambda route: route.fulfill(status=404, json={'detail': 'none'}))
    review.goto(base_url + 'review.html?id=x')
    expect(review.get_by_role('img', name='SurveyCoach', exact=True)).to_have_count(1)    # the word is hidden at 390; the mark is the name
    context.close()


def test_how_it_works_is_three_steps_with_real_micro_visuals_not_links(browser, base_url):
    context, page, errors = home(browser, base_url)
    steps = page.locator('#how-steps > li')
    assert steps.count() == 3
    assert page.locator('.how a, .how button').count() == 0                                # nothing that looks clickable but is not
    for kind in ('.mv-phone', '.mv-fix', '.mv-slack'):
        assert page.locator(f'.how {kind}').count() == 1
    assert page.locator('.how .mv-frame[aria-hidden=true]').count() == 3                   # the text carries the meaning
    assert 'Survey review: Holiday Snacks (v2)' in page.locator('.mv-slack').inner_text()
    assert page.locator('.mv-fix .state-chip').inner_text() == 'Fix before launch'
    assert 'See' not in page.locator('#how-steps').inner_text().split('\n')                # the old bare See/Improve/Share words
    assert not errors
    context.close()


def test_the_example_is_labelled_and_says_its_numbers_once(browser, base_url):
    context, page, errors = home(browser, base_url)
    example = page.locator('#example')
    assert 'example' in example.locator('.example-tag').inner_text().lower() and example.locator('.example-tag').is_visible()
    text = example.inner_text()
    assert text.lower().count('2 things to fix') == 1 and 'must-fix' not in text.lower()
    assert page.locator('.example-check, .example-stats').count() == 0
    color = page.locator('.after').evaluate('el => getComputedStyle(el).color')
    assert color == page.locator('body').evaluate('el => getComputedStyle(el).color')    # body ink on white, not pale green
    context.close()


def test_the_example_demo_works_by_keyboard_and_resets(browser, base_url):
    context, page, errors = home(browser, base_url)
    question, status = page.locator('#demo-question'), page.locator('#demo-status')
    assert question.inner_text() == OLD and 'line-through' in question.evaluate('el => getComputedStyle(el).textDecorationLine')
    page.locator('#demo-use').focus()
    page.keyboard.press('Enter')
    assert question.inner_text() == NEW
    assert 'line-through' not in question.evaluate('el => getComputedStyle(el).textDecorationLine')
    expect(status).to_have_text(f'Question 4 now reads: {NEW}')
    assert page.locator('#demo-chip').inner_text() == '1 thing to fix before launch'
    assert page.locator('#demo-suggestion').is_hidden()
    expect(page.locator('#demo-reset')).to_be_focused()                                    # focus follows the swap
    assert page.locator('[aria-live], [role=status]').filter(has_text='now reads').count() == 1
    page.keyboard.press('Space')
    assert question.inner_text() == OLD and page.locator('#demo-chip').inner_text() == '2 things to fix before launch'
    expect(page.locator('#demo-use')).to_be_focused()
    expect(status).to_have_text(f'Question 4 is back to: {OLD}')
    assert not errors
    context.close()


def test_home_has_one_primary_button_and_fits_a_phone(browser, base_url):
    context, page, errors = home(browser, base_url, width=390)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('.go:visible, .btn-primary:visible').count() == 1
    for selector in ('#demo-use', '.go', '#sample-start'):
        assert page.locator(selector).first.bounding_box()['height'] >= 44, selector
    boxes = [step.bounding_box() for step in page.locator('#how-steps > li').all()]
    assert len({round(b['x']) for b in boxes}) == 1                                        # stacked, one column
    page.locator('#demo-use').click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()


def survey(**fields):
    base = dict(id='one', title='Holiday snacks', version=1, created_at='2026-01-01 00:00:00', job=None, signals=[],
                verdict={'kind': 'fix_before_launch', 'tiles': {'fix': 2, 'improve': 1, 'you_check': 3}},
                tiles={'fix': 2, 'improve': 1, 'you_check': 3}, ready_to_share=False)
    return dict(base, **fields)


def test_checking_is_only_ever_shown_for_a_live_job_with_stage_data(browser, base_url):
    context, page, errors = home(browser, base_url, surveys=[
        survey(id='done', job={'status': 'completed', 'stage': 'checking'}),
        survey(id='old', job=None, ready_to_share=False),
        survey(id='queued', verdict=None, tiles=None, job={'status': 'queued', 'stage': None}),
        survey(id='running-no-stage', verdict=None, tiles=None, job={'status': 'running', 'stage': None}),
        survey(id='running', verdict=None, tiles=None, job={'status': 'running', 'stage': 'reading'})])
    page.locator('a.survey-card').first.wait_for()
    chips = page.locator('a.survey-card .state-chip').all_text_contents()
    assert chips == ['Fix before launch', 'Fix before launch', 'Queued', 'In progress', 'Checking…']
    assert 'Checking' not in page.locator('#how-steps').inner_text() + page.locator('#example').inner_text()
    context.close()
    context, page, errors = home(browser, base_url)
    assert 'Checking' not in page.locator('body').inner_text()                             # nothing is running: never claim it
    context.close()


def test_home_copy_avoids_the_banned_words_in_its_default_state(browser, base_url):
    from tests.test_copy_banned_words import offenders
    context, page, errors = home(browser, base_url)
    assert offenders(page) == []
    page.locator('#demo-use').click()
    assert offenders(page) == []
    context.close()
