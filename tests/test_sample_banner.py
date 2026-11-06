"""The public (GitHub Pages) sample says what it is, and never offers a link it cannot honour.

index.html is the static sample: fictional data, nothing saved or sent. A visitor must be told that, and
pointed to the team's real tool only when its address is configured (environment.js, which the private
server overrides). A configured address is only ever rendered as a link when it is plain https.
"""
import pytest

from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)

BANNER = '#sample-banner'


def open_static(browser, base_url, environment_js=None, width=1280):
    """Open the static sample; environment_js replaces /environment.js the way the private server does."""
    context = browser.new_context(viewport={'width': width, 'height': 900})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if environment_js is not None:
        page.route('**/environment.js', lambda route: route.fulfill(
            status=200, content_type='text/javascript', body=environment_js))
    page.goto(base_url + 'index.html')
    page.locator('#overview-h').wait_for()
    return context, page, errors


def test_static_sample_says_it_is_a_sample_and_where_real_use_lives(browser, base_url):
    context, page, errors = open_static(browser, base_url)
    banner = page.locator(BANNER)
    assert banner.is_visible()
    text = banner.inner_text()
    assert 'Sample review' in text and 'fictional' in text and 'nothing here is saved or sent' in text.lower()
    assert 'ask the SurveyCoach owner' in text            # no team address configured: say how to get access
    assert banner.locator('a').count() == 0               # ...and never a dead link
    assert banner.get_attribute('role') is None or banner.get_attribute('role') == 'note'
    assert banner.locator('h1, h2, h3').count() == 0      # the survey name stays the page's only H1
    assert page.locator('h1').count() == 1
    assert errors == []
    context.close()


def test_configured_team_address_becomes_a_safe_link(browser, base_url):
    env = 'window.SURVEYCOACH_LOCAL = false; window.SURVEYCOACH_TEAM_URL = "https://surveycoach.example.com/start";'
    context, page, errors = open_static(browser, base_url, env)
    link = page.locator(f'{BANNER} a')
    assert link.count() == 1
    assert link.get_attribute('href') == 'https://surveycoach.example.com/start'
    assert 'noopener' in (link.get_attribute('rel') or '') and 'noreferrer' in (link.get_attribute('rel') or '')
    assert 'Check your own survey' in link.inner_text()
    assert 'ask the SurveyCoach owner' not in page.locator(BANNER).inner_text()
    assert errors == []
    context.close()


@pytest.mark.parametrize('bad', ['javascript:alert(1)', 'http://insecure.example.com', '//evil.example.com', 'data:text/html,x', '  '])
def test_only_plain_https_team_addresses_are_ever_linked(browser, base_url, bad):
    env = f'window.SURVEYCOACH_LOCAL = false; window.SURVEYCOACH_TEAM_URL = {bad!r};'
    context, page, errors = open_static(browser, base_url, env)
    assert page.locator(f'{BANNER} a').count() == 0
    assert 'ask the SurveyCoach owner' in page.locator(BANNER).inner_text()
    assert errors == []
    context.close()


def test_the_private_server_never_shows_the_sample_banner(browser, base_url):
    context, page, _ = open_static(browser, base_url, 'window.SURVEYCOACH_LOCAL = true;')
    assert page.locator(BANNER).count() == 0
    context.close()


def test_banner_fits_a_phone_and_keeps_targets_usable(browser, base_url):
    env = 'window.SURVEYCOACH_LOCAL = false; window.SURVEYCOACH_TEAM_URL = "https://surveycoach.example.com/start";'
    context, page, _ = open_static(browser, base_url, env, width=390)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    box = page.locator(f'{BANNER} a').bounding_box()
    assert box['height'] >= 24 and box['width'] >= 24
    assert page.locator(BANNER).bounding_box()['width'] <= 390
    context.close()


def test_banner_shows_on_the_verdict_only_so_the_phone_stays_the_hero(browser, base_url):
    context, page, _ = open_static(browser, base_url, width=390)
    assert page.locator(BANNER).is_visible()                       # Verdict: the visitor is told what this is
    page.evaluate("window.location.hash = '#improve'")
    page.locator('#chapter-improve').wait_for(state='visible')
    assert not page.locator(BANNER).is_visible()                   # Fix: the phone must start in the top half
    page.evaluate("window.location.hash = '#share'")
    page.locator('#chapter-share').wait_for(state='visible')
    assert not page.locator(BANNER).is_visible()
    page.evaluate("window.location.hash = '#overview'")
    page.locator('#chapter-overview').wait_for(state='visible')
    assert page.locator(BANNER).is_visible()                       # and it comes back with the Verdict
    context.close()


def test_a_deep_link_into_fix_starts_without_the_banner(browser, base_url):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    page.goto(base_url + 'index.html#improve')
    page.locator('#chapter-improve').wait_for(state='visible')
    assert page.locator(BANNER).count() == 1 and not page.locator(BANNER).is_visible()
    context.close()
