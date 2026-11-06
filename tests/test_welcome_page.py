"""The public front door: a landing page that explains SurveyCoach and leads to the sample review.

A visitor from the shared link must learn what this is before landing in the middle of a review. The landing page is
static (no server, no survey data): the pitch, how it works, an interactive example, and one clear way in. It never
offers a link input it cannot honour, and it only links the team tool when a plain https address is configured.
"""
import re

import pytest

from tests.test_copy_banned_words import BANNED_RE
from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)

TEAM = 'window.SURVEYCOACH_LOCAL = false; window.SURVEYCOACH_TEAM_URL = "https://surveycoach.example.com/start";'


def open_welcome(browser, base_url, environment_js=None, width=1280):
    context = browser.new_context(viewport={'width': width, 'height': 900})
    page = context.new_page()
    errors, api_calls = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: api_calls.append(request.url) if '/api/' in request.url else None)
    if environment_js is not None:
        page.route('**/environment.js', lambda route: route.fulfill(
            status=200, content_type='text/javascript', body=environment_js))
    page.goto(base_url + 'welcome.html')
    page.locator('#how-steps li').first.wait_for()
    return context, page, errors, api_calls


def test_landing_explains_the_product_and_leads_to_the_sample(browser, base_url):
    context, page, errors, api_calls = open_welcome(browser, base_url)
    assert page.locator('h1').count() == 1
    assert 'members' in page.locator('h1').inner_text().lower()
    sample = page.get_by_role('link', name=re.compile('Open the sample review'))
    assert sample.count() == 1 and sample.first.get_attribute('href') == 'index.html'   # the build maps it to sample.html
    assert page.locator('#how-steps li').count() == 3                                    # How it works
    assert page.locator('#example').is_visible()
    assert page.locator('#sample-note').is_visible()
    assert 'fictional' in page.locator('#sample-note').inner_text().lower()
    assert errors == [] and api_calls == []                                              # static: never talks to a server
    context.close()


def test_landing_never_offers_a_link_input_it_cannot_honour(browser, base_url):
    context, page, _, _ = open_welcome(browser, base_url)
    assert page.locator('input, form, textarea').count() == 0
    assert 'Paste a RedJade' not in page.locator('main').inner_text().split('How it works')[0]
    context.close()


def test_without_a_team_address_the_landing_says_how_to_get_access(browser, base_url):
    context, page, _, _ = open_welcome(browser, base_url)
    access = page.locator('#own-survey')
    assert 'ask the SurveyCoach owner' in access.inner_text() and access.locator('a').count() == 0
    context.close()


def test_a_configured_team_address_becomes_a_safe_link(browser, base_url):
    context, page, _, _ = open_welcome(browser, base_url, TEAM)
    link = page.locator('#own-survey a')
    assert link.count() == 1 and link.get_attribute('href') == 'https://surveycoach.example.com/start'
    assert 'noopener' in link.get_attribute('rel') and 'noreferrer' in link.get_attribute('rel')
    assert 'ask the SurveyCoach owner' not in page.locator('#own-survey').inner_text()
    context.close()


@pytest.mark.parametrize('bad', ['javascript:alert(1)', 'http://insecure.example.com', '//evil.example.com', '  '])
def test_only_plain_https_team_addresses_are_ever_linked_on_the_landing(browser, base_url, bad):
    context, page, errors, _ = open_welcome(browser, base_url, f'window.SURVEYCOACH_LOCAL = false; window.SURVEYCOACH_TEAM_URL = {bad!r};')
    assert page.locator('#own-survey a').count() == 0 and errors == []
    context.close()


def test_the_example_still_works_by_keyboard(browser, base_url):
    context, page, _, _ = open_welcome(browser, base_url)
    page.locator('#demo-use').focus()
    page.keyboard.press('Enter')
    assert 'taste?' in page.locator('#demo-question').inner_text() and 'price' not in page.locator('#demo-question').inner_text()
    page.locator('#demo-reset').focus()
    page.keyboard.press('Enter')
    assert 'taste and price' in page.locator('#demo-question').inner_text()
    context.close()


@pytest.mark.parametrize('width', [1440, 390])
def test_landing_fits_every_width_and_uses_plain_words(browser, base_url, width):
    context, page, _, _ = open_welcome(browser, base_url, TEAM, width=width)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    text = page.locator('body').inner_text()
    assert not BANNED_RE.search(text), BANNED_RE.search(text).group(0)
    shown = [control for control in page.locator('a[href], button').all() if control.is_visible()]
    assert len(shown) >= 4                                                                # skip, sample, team, Use
    for control in shown:
        box = control.bounding_box()
        assert box['height'] >= 24 and box['width'] >= 24
        assert (control.inner_text().strip() or control.get_attribute('aria-label') or control.get_attribute('title'))
    primary = page.get_by_role('link', name=re.compile('Open the sample review')).first.bounding_box()
    assert primary['height'] >= 44
    context.close()
