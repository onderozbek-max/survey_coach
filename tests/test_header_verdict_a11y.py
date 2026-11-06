"""Header and Verdict accessibility (brief section 11): accessibility-tree snapshots, keyboard-only paths,
44px targets, state never by colour alone, one H1 per page. Intercepted synthetic review; offline."""
import pytest
from playwright.sync_api import expect

from tests.site_helpers import go_to, open_how_we_check
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser


def test_header_accessibility_tree(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=1280, chapter='overview')
    expect(page.locator('#app-header')).to_match_aria_snapshot('''
        - link "SurveyCoach home"
        - link "My surveys"
        - heading "Member's Mark Boxer Briefs Feedback Survey" [level=1]
        - button "Rename survey"
        - navigation "Review steps":
          - link "Verdict"
          - link "Fix"
          - link "Sign off"
        - button "Check again"
        - button "More options"
    ''')
    assert page.locator('#chapter-nav [aria-current=step]').inner_text().strip().endswith('Verdict')
    assert not errors
    context.close()


@pytest.mark.parametrize('chapter', ['overview', 'improve', 'share'])
def test_one_h1_equal_to_the_survey_name_on_every_page(browser, base_url, chapter):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter=chapter)
    headings = page.locator('h1')
    expect(headings).to_have_count(1)
    expect(headings).to_have_text(detail['title'])
    assert page.title() == f"{detail['title']} · SurveyCoach"
    assert page.locator('.version-chip').inner_text().startswith('v2 · checked ')   # exactly one version chip
    assert page.locator('.version-chip').count() == 1
    context.close()


def test_rename_by_keyboard_saves_through_the_existing_path_and_announces_once(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview')
    page.locator('#rename-survey').focus()
    page.keyboard.press('Enter')
    expect(page.locator('#survey-name')).to_be_focused()
    page.keyboard.type(' (round two)')
    page.keyboard.press('Escape')                                    # cancel puts focus back where it started
    expect(page.locator('#rename-survey')).to_be_focused()
    assert not writes and page.locator('h1').inner_text() == detail['title']
    page.keyboard.press('Enter')
    page.locator('#survey-name').fill('Round two')
    page.keyboard.press('Enter')
    page.wait_for_function("document.querySelector('#review-title').textContent === 'Round two'")
    assert writes == [{'title': 'Round two'}]
    expect(page.locator('#rename-survey')).to_be_focused()
    assert page.locator('[role=status], [aria-live]').filter(has_text='Name saved.').count() == 1
    context.close()


def test_rename_rejects_an_empty_name_without_writing(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview')
    page.locator('#rename-survey').click()
    page.locator('#survey-name').fill('   ')
    page.keyboard.press('Enter')
    expect(page.locator('.rename-status')).to_have_text('Enter a name.')
    assert not writes
    context.close()


def test_overflow_menu_is_keyboard_operable(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=1280, chapter='overview')
    button = page.locator('#header-menu-button')
    button.focus()
    page.keyboard.press('ArrowDown')
    expect(button).to_have_attribute('aria-expanded', 'true')
    expect(page.get_by_role('menuitem', name='How we check')).to_be_focused()
    page.keyboard.press('ArrowDown')                                 # a one-item menu wraps onto itself
    expect(page.get_by_role('menuitem', name='How we check')).to_be_focused()
    page.keyboard.press('Escape')
    expect(button).to_have_attribute('aria-expanded', 'false')
    expect(button).to_be_focused()
    button.press('Enter')
    expect(page.get_by_role('menuitem', name='How we check')).to_be_focused()
    page.keyboard.press('Enter')
    expect(page.get_by_role('dialog', name='How we check')).to_be_visible()
    context.close()


def test_the_390_header_collapses_to_name_and_step_menu_with_44px_targets(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390, chapter='overview')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('.hdr-mysurveys').is_hidden() and page.locator('#chapter-nav').is_hidden()
    for selector in ('.hdr-brand', '#steps-button', '#check-again', '#header-menu-button', '#rename-survey'):
        box = page.locator(selector).bounding_box()
        assert box['width'] >= 44 and box['height'] >= 44, selector
    page.locator('#steps-button').focus()
    page.keyboard.press('Enter')
    expect(page.locator('#steps-button')).to_have_attribute('aria-expanded', 'true')
    expect(page.get_by_role('link', name='Fix')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('#chapter-nav')).to_be_hidden()
    expect(page.locator('#steps-button')).to_be_focused()
    page.locator('#header-menu-button').click()                      # My surveys moves into the overflow menu
    expect(page.get_by_role('menuitem', name='My surveys')).to_be_visible()
    context.close()


def test_check_again_is_always_available_and_prefilled(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=1280, chapter='share')
    page.locator('#check-again').click()
    expect(page.get_by_role('dialog', name='Check again')).to_be_visible()
    expect(page.locator('#survey-link')).to_have_value(detail['snapshot']['source_url'])
    page.keyboard.press('Escape')
    expect(page.locator('#recheck-dialog')).to_be_hidden()
    expect(page.locator('#check-again')).to_be_focused()
    context.close()


def test_verdict_accessibility_tree_and_keyboard_path(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=1280, chapter='overview')
    tiles = detail['overview']['verdict']['tiles']
    expect(page.locator('.verdict-hero')).to_match_aria_snapshot(f'''
        - heading "{detail['overview']['headline']}" [level=2]
        - group "What is open":
          - 'button "Fix: {tiles['fix']} open"'
          - 'button "Improve: {tiles['improve']} open"'
          - 'button "You check: {tiles['you_check']} open"'
        - button /Start fixing \\(\\d+\\)/
        - button "Play it as a member"
    ''')
    # H1 survey > H2 verdict > H3 sections (the setup card comes first, then the member experience): no level is skipped
    assert 'Member experience' in page.locator('h3').all_inner_texts()
    levels = [int(tag[1]) for tag in page.locator('h1, h2, h3, h4, h5, h6').evaluate_all('els => els.map(e => e.tagName)')]
    assert levels[0] == 1 and all(b - a <= 1 for a, b in zip(levels, levels[1:])), levels
    page.locator('[data-tile=fix]').focus()
    page.keyboard.press('Enter')
    page.wait_for_function("SC.currentChapter() === 'improve'")
    assert not errors
    context.close()


def test_every_state_is_icon_plus_words_never_colour_alone(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview')
    chips = page.locator('.state-chip')
    assert chips.count() >= 7                                                   # verdict chip plus one per category card
    for index in range(chips.count()):
        chip = chips.nth(index)
        assert chip.locator('svg').count() == 1 and chip.inner_text().strip(), index
    shapes = {name: page.evaluate(f'SC.icon(SC.STATES.{name}.icon).innerHTML') for name in
              ('fix_before_launch', 'worth_improving', 'you_check', 'looks_good')}
    assert len(set(shapes.values())) == 4                                       # four states, four different shapes
    cards = page.locator('#signals > li')
    icons = [card.locator('.signal-name svg').inner_html() for card in cards.all()]
    assert len(set(icons)) == len(icons) == 6                                   # six categories, six different icons
    context.close()


def test_verdict_has_no_score_or_tiny_phone_and_tiles_open_the_fix_flow(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390, chapter='overview')
    text = page.locator('#chapter-overview').inner_text()
    assert not any(word in text for word in ('/100', 'Provisional', 'coverage', 'Your plan'))
    assert page.locator('#chapter-overview .phone, .overview-mini, .ring').count() == 0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    for selector in ('.verdict-tile:not(:disabled)', '#start-improving', '#preview-member'):
        box = page.locator(selector).first.bounding_box()
        assert box['height'] >= 44, selector
    page.locator('#start-improving').click()
    page.wait_for_function("SC.currentChapter() === 'improve'")
    context.close()
