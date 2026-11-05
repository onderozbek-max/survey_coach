"""Local member journey estimates are visible, inspectable and never empirical claims."""
import pytest

from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser
from tests.test_workflow_e2e import studio


def tools(page):
    if not page.locator('.preview-tools').evaluate('e => e.open'):
        page.locator('.preview-tools > summary').click()


@pytest.mark.parametrize('destination', ['overview', 'share'])
def test_playback_stops_on_chapter_exit_and_reentry_shows_play(browser, base_url, destination):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now() + 1000'))
    tools(page)
    page.get_by_role('button', name='Play as a member', exact=True).click()
    assert page.get_by_role('button', name='Pause walkthrough', exact=True).is_visible()
    screen = page.locator('#stage .phone-bar').inner_text()
    page.locator(f'[data-chapter={destination}]').click()
    page.clock.run_for(3_600_000)
    page.locator('[data-chapter=improve]').click()
    assert page.locator('#stage .phone-bar').inner_text() == screen
    tools(page)
    assert page.get_by_role('button', name='Play as a member', exact=True).is_visible()
    assert page.get_by_role('button', name='Pause walkthrough', exact=True).count() == 0
    page.clock.run_for(3_600_000)
    assert page.locator('#stage .phone-bar').inner_text() == screen
    # The displayed action must actually resume playback, not merely change its label.
    tools(page)
    page.get_by_role('button', name='Play as a member', exact=True).click()
    assert page.get_by_role('button', name='Pause walkthrough', exact=True).is_visible()
    page.clock.run_for(3_600_000)
    assert page.locator('#stage .phone-bar').inner_text() != screen
    tools(page)
    assert page.get_by_role('button', name='Play as a member', exact=True).is_visible()
    assert not writes and not errors
    context.close()


def test_uncertain_captured_walkthrough_qualifies_total_timing(browser, base_url):
    def prepare(detail):
        detail['overview']['energy']['path_uncertain'] = True
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    timing = page.locator('#stage .timing')
    assert 'Captured-screen walkthrough' in timing.inner_text()
    assert 'route uncertain' in timing.inner_text()
    assert 'Estimated time to this screen:' not in timing.inner_text()
    assert timing.locator('.timebar').count() == 0
    page.clock.install()
    page.clock.pause_at(page.evaluate('Date.now() + 1000'))
    tools(page)
    page.get_by_role('button', name='Play as a member', exact=True).click()
    page.clock.run_for(5000)
    assert 'route uncertain' in timing.inner_text()
    assert not writes and not errors
    context.close()


def test_journey_comparison_and_question_stem_visible(browser, studio):
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#chapter-nav [data-chapter=improve]').click()
    page.locator('#stage .phone-screen').first.wait_for()
    assert page.locator('#stage .phone-screen').first.evaluate('e => e.scrollTop') == 0
    assert page.locator('#all-screens').is_visible()
    assert page.get_by_role('navigation', name='Member effort by screen').count() == 0
    # Comparison is intentionally unavailable on screens without text changes.
    finding = page.evaluate("""() => {
      const d = SC.workspaceDetail;
      return d.review.findings.find(f => !f.absorbed_by && !f.structural && f.question_id &&
        SC.choicesOf(f).length && d.snapshot.pages.some(p => p.questions?.some(q =>
          q.id === f.question_id && q.text.includes(f.current_text))));
    }""")
    assert finding, 'Sample must provide a genuine question rewrite to compare'
    page.evaluate("fp => dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:fp}))", finding['fingerprint'])
    assert page.locator('#coach h3.headline').inner_text() == finding['headline']
    assert finding['current_text'] in page.locator('#stage .phone-screen').inner_text()
    tools(page)
    page.get_by_role('button', name='Compare wording', exact=True).click()
    assert not errors
    assert page.locator('.comparison-phones .phone').count() == 2
    assert page.get_by_text('Original', exact=True).count() >= 1
    assert 'Estimated' in page.locator('.comparison-note').inner_text()
    assert 'not reassessed' in page.locator('.comparison-note').inner_text()
    tools(page)
    page.get_by_role('button', name='Play as a member', exact=True).click()
    assert page.get_by_role('button', name='Pause walkthrough', exact=True).count() == 1
    page.get_by_role('button', name='Pause walkthrough', exact=True).click()
    page.get_by_role('button', name='Close comparison', exact=True).click()
    assert page.locator('#stage .phone').count() == 1
    page.set_viewport_size({'width':390,'height':844})
    tools(page)
    page.get_by_role('button',name='Compare wording',exact=True).click()
    phones=page.locator('.comparison-phones .phone')
    assert phones.count()==2
    first,second=phones.nth(0).bounding_box(),phones.nth(1).bounding_box()
    assert second['y'] > first['y']
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.close()
