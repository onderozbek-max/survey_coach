"""Chapter routing on intercepted synthetic reviews only; no saved data touched."""
import pytest

from tests.test_issue_loop_ui import open_review, open_overview, focus
from tests.test_site_e2e import base_url, browser


def assert_chapter(page, name):
    for chapter in ('overview', 'improve', 'share'):
        assert page.locator(f'#chapter-{chapter}').is_visible() == (chapter == name)
    assert page.locator('#chapter-nav [aria-current="step"]').get_attribute('data-chapter') == name
    assert page.evaluate('SC.currentChapter()') == name


def test_default_overview_navigation_back_forward_and_focus(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='')
    assert_chapter(page, 'overview')
    assert page.locator('#stage .phone-screen').count() == 0  # Improve is lazy.
    assert page.locator('#overview-h').evaluate('(el) => el === document.activeElement')
    page.locator('[data-chapter=improve]').click()
    assert page.url.endswith('#improve')
    assert_chapter(page, 'improve')
    assert page.locator('#improve-h').evaluate('(el) => el === document.activeElement')
    page.evaluate("document.querySelector('#stage .phone-screen').dataset.retained = 'yes'")
    page.go_back()
    assert_chapter(page, 'overview')
    page.go_forward()
    assert_chapter(page, 'improve')
    assert page.locator('#stage .phone-screen').get_attribute('data-retained') == 'yes'
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('chapter', ['overview', 'improve', 'share', 'unknown', 'constructor'])
def test_direct_and_invalid_hashes(browser, base_url, chapter):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter=chapter)
    assert_chapter(page, chapter if chapter in ('overview', 'improve', 'share') else 'overview')
    assert not writes and not errors
    context.close()


def test_hashchange_api_event_once_and_no_duplicate_history(browser, base_url):
    context, page, detail, writes, errors = open_overview(browser, base_url)
    page.evaluate("window.changes=[]; addEventListener('surveycoach-chapter', e => changes.push(e.detail))")
    page.evaluate("location.hash='share'")
    page.wait_for_function("SC.currentChapter() === 'share' && !document.querySelector('#chapter-share').hidden")
    assert_chapter(page, 'share')
    assert page.locator('#share-h').evaluate('(el) => el === document.activeElement')
    page.evaluate("SC.goChapter('improve', {source:'test'})")
    page.evaluate("SC.goChapter('improve'); SC.goChapter('invalid')")
    assert page.evaluate('changes') == [
        {'name': 'share', 'options': {}}, {'name': 'improve', 'options': {'source': 'test'}}]
    page.go_back()
    assert_chapter(page, 'share')
    assert page.evaluate('changes.length') == 3  # popstate + hashchange must not double-dispatch
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('chapter', ['improve', 'share'])
@pytest.mark.parametrize('shell', ['review', 'sample'])
def test_keyboard_skip_keeps_current_chapter_and_focuses_workspace(browser, base_url, chapter, shell):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter=chapter)
    if shell == 'sample':
        page.goto(base_url + f'index.html#{chapter}')
        page.wait_for_function('SC.reviewReady === true')
    before = page.url
    history_length = page.evaluate('history.length')
    page.evaluate("window.changes=[]; addEventListener('surveycoach-chapter', e => changes.push(e.detail))")
    skip = page.get_by_role('link', name='Skip to review', exact=True)
    skip.focus()
    page.keyboard.press('Enter')
    assert_chapter(page, chapter)
    assert page.url == before
    assert page.evaluate('history.length') == history_length
    assert page.locator('#workspace').evaluate('(el) => el === document.activeElement')
    assert page.locator('#workspace').bounding_box()['y'] >= 0
    assert page.evaluate('changes') == []
    assert not writes and not errors
    context.close()


def test_focus_finding_enters_improve_without_losing_selection(browser, base_url):
    context, page, detail, writes, errors = open_overview(browser, base_url)
    finding = detail['review']['findings'][-1]
    focus(page, finding)
    assert_chapter(page, 'improve')
    assert page.url.endswith('#improve')
    assert finding['headline'] in page.locator('#coach .card').inner_text()
    assert page.locator('#improve-h').evaluate('(el) => el === document.activeElement')
    assert not writes and not errors
    context.close()


def test_mobile_nav_help_and_reduced_motion(browser, base_url):
    context, page, detail, writes, errors = open_overview(browser, base_url, width=390)
    page.emulate_media(reduced_motion='reduce')
    page.evaluate("window.scrolls=[]; window.scrollTo = options => scrolls.push(options)")
    for chapter in ('improve', 'share', 'overview'):
        page.locator(f'[data-chapter={chapter}]').click()
        assert_chapter(page, chapter)
        assert page.locator('#about-review').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('#chapter-nav').evaluate('(el) => el.scrollWidth <= el.clientWidth')
    scrolls = page.evaluate('scrolls.filter(item => item && item.behavior)')
    assert len(scrolls) == 3
    assert all(item['behavior'] == 'instant' for item in scrolls)
    assert page.locator('#chapter-nav a').first.evaluate('(el) => el.getBoundingClientRect().height') >= 44
    assert not writes and not errors
    context.close()


def test_static_sample_uses_shell_and_redirect_keeps_query_and_hash(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + 'index.html')
    assert_chapter(page, 'overview')
    page.locator('[data-chapter=improve]').click()
    assert page.locator('#stage .phone-screen').is_visible()
    assert page.locator('#rail, .toolbar, .journey').count() == 0
    page.goto(base_url + 'index.html?id=synthetic&version=2#share')
    page.wait_for_url('**/review.html?id=synthetic&version=2#share')
    assert_chapter(page, 'share')
    context.close()
