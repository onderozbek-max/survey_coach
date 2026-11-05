"""UI clarity regressions: synthetic fixture only; no live review or persistence."""
import pytest

from tests.test_issue_loop_ui import open_review, focus
from tests.test_improve_ui import curated
from tests.test_site_e2e import base_url, browser


def select_screen(page, page_id):
    page.evaluate("id => dispatchEvent(new CustomEvent('surveycoach-screen', {detail:id}))", page_id)


def test_action_only_recommendation_is_visible_not_a_missing_rewrite(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if not f.get('suggested_text') and not f.get('options'))
    focus(page, finding)
    assert page.locator('#coach .suggested h4').inner_text() == 'Recommended action'
    assert page.locator('#coach .suggested').get_by_text(finding['explanation'], exact=True).is_visible()
    assert 'Make this change in RedJade using the details below.' not in page.locator('#coach').inner_text()
    assert page.locator('#coach details.more').get_by_text(finding['explanation'], exact=True).count() == 0
    assert page.locator('#use-change').count() == 0
    assert not writes and not errors
    context.close()


def isolated(detail):
    picks = curated(detail)
    page_id = detail['screens'][0]['page_id']
    for f in detail['review']['findings']:
        f['page_id'] = 'elsewhere'
        f['question_id'] = None
        f.pop('absorbed_by', None)
        f.pop('also_affects', None)
    return picks, page_id


def test_screen_without_findings_reports_checks_not_zero_handled(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=isolated)
    select_screen(page, detail['screens'][0]['page_id'])
    assert page.locator('#coach h3').inner_text() == 'Nothing to fix on this screen'
    assert 'Our checks found nothing here' in page.locator('#coach').inner_text()
    assert 'handled' not in page.locator('#coach h3').inner_text()
    assert not writes and not errors
    context.close()


def test_zero_category_is_not_all_handled(browser, base_url):
    def prepare(detail):
        isolated(detail)
        detail['plan']['must_fix'] = []
        detail['plan']['counts']['must_fix'] = 0
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    assert page.locator('#coach h3').inner_text() == 'No must-fixes in this review'
    assert 'All 0' not in page.locator('#coach').inner_text()
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('reference', ['also_affects', 'absorbed_by', 'question_id'])
def test_screen_matches_related_findings_across_categories(browser, base_url, reference):
    def prepare(detail):
        picks, page_id = isolated(detail)
        root = picks[0]
        related = next(f for f in detail['review']['findings'] if f not in picks)
        related['page_id'] = page_id
        if reference == 'also_affects':
            root['also_affects'] = [related['fingerprint']]
        elif reference == 'absorbed_by':
            related['absorbed_by'] = root['fingerprint']
        else:
            detail['screens'][0]['questions'] = [dict(id='synthetic-question', label='Q1')]
            root['question_id'] = 'synthetic-question'
        detail['plan']['quick_wins'] = [detail['plan']['must_fix'].pop(0)]
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    select_screen(page, detail['screens'][0]['page_id'])
    assert page.locator('#coach h3').inner_text() == detail['plan']['quick_wins'][0]['headline']
    assert page.locator('[data-fk=queue-quick_wins]').get_attribute('aria-selected') == 'true'
    assert not writes and not errors
    context.close()


def test_scoped_empty_filter_is_not_screen_clear_or_all_decided(browser, base_url):
    def prepare(detail):
        picks, page_id = isolated(detail)
        picks[0]['page_id'] = page_id
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    page.evaluate("o => SC.goChapter('improve', o)", dict(page_id=detail['screens'][0]['page_id'], fingerprints=[]))
    assert page.locator('#coach h3').inner_text() == 'Nothing more in this view'
    assert 'outside this filter' in page.locator('#coach').inner_text()
    page.get_by_role('button', name='Show all recommendations', exact=True).focus()
    page.keyboard.press('Enter')
    assert page.locator('#coach .card').is_visible()
    assert not writes and not errors
    context.close()


def test_scoped_all_decided_is_distinct_from_no_findings(browser, base_url):
    def prepare(detail):
        picks, page_id = isolated(detail)
        picks[0]['page_id'] = page_id
        detail['decisions'][picks[0]['fingerprint']] = dict(action='keep', reason='Tracker')
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    page.evaluate("o => SC.goChapter('improve', o)", dict(page_id=detail['screens'][0]['page_id']))
    page.locator('#skip').click()
    assert page.locator('#coach h3').inner_text() == 'All recommendations for this screen handled'
    assert 'not verified fixes' in page.locator('#coach').inner_text()
    assert not writes and not errors
    context.close()


def test_other_category_open_finding_prevents_screen_completion(browser, base_url):
    def prepare(detail):
        picks, page_id = isolated(detail)
        for f in picks[:2]:
            f['page_id'] = page_id
        detail['decisions'][picks[0]['fingerprint']] = dict(action='keep', reason='Tracker')
        detail['plan']['quick_wins'] = [detail['plan']['must_fix'].pop(1)]
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    page.evaluate("o => SC.goChapter('improve', o)", dict(page_id=detail['screens'][0]['page_id'], tab='must_fix'))
    page.locator('#skip').click()
    assert page.locator('#coach h3').inner_text() == 'Nothing more in this view'
    assert 'outside this category' in page.locator('#coach').inner_text()
    assert not writes and not errors
    context.close()


def test_unqueued_screen_finding_is_not_falsely_handled(browser, base_url):
    def prepare(detail):
        picks, page_id = isolated(detail)
        picks[0]['page_id'] = page_id
        detail['decisions'][picks[0]['fingerprint']] = dict(action='keep', reason='Tracker')
        unqueued = next(f for f in detail['review']['findings'] if f not in picks)
        unqueued['page_id'] = page_id
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    select_screen(page, detail['screens'][0]['page_id'])
    page.locator('#skip').click()
    assert page.locator('#coach h3').inner_text() == 'Nothing more in this view'
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('width', [320, 390, 1280])
def test_compact_energy_legend_navigation_and_mobile_layout(browser, base_url, width):
    context, page, detail, writes, errors = open_review(browser, base_url, width=width)
    energy = page.locator('#improve-bar .energy-map')
    assert energy.is_visible()
    caption = energy.locator('.energy-quick-guide')
    assert caption.is_visible()
    assert 'Height = screen effort' in caption.inner_text()
    assert 'Color = accumulated effort' in caption.inner_text()
    guide = energy.locator('details.energy-guide')
    assert guide.get_attribute('open') is None
    legend = energy.locator('.energy-legend')
    assert legend.is_visible()
    assert legend.inner_text().splitlines() == ['Estimated load:', 'Low', 'Building', 'High']
    assert not energy.locator('.energy-explanation').is_visible()
    summary = guide.get_by_text('Effort guide', exact=True)
    summary.focus()
    page.keyboard.press('Enter')
    assert guide.get_attribute('open') is not None
    assert legend.is_visible()
    assert legend.inner_text().splitlines() == ['Estimated load:', 'Low', 'Building', 'High']
    explanation = energy.locator('.energy-explanation')
    assert explanation.is_visible()
    text = explanation.inner_text()
    for phrase in ['Height: estimated effort per screen', 'Color: accumulated effort', 'an estimate',
                   'not severity', 'measured time or fatigue', 'Blue outline: selected screen']:
        assert phrase in text
    summary.focus()
    page.keyboard.press('Enter')
    assert guide.get_attribute('open') is None
    assert caption.is_visible()
    assert legend.is_visible()
    bars = energy.locator('.energy-bar')
    target_id = bars.nth(1).get_attribute('data-page')
    assert 'estimated load' in bars.nth(1).get_attribute('aria-label')
    bars.nth(1).focus()
    page.keyboard.press('Enter')
    selected = energy.locator('[aria-current=step]')
    assert selected.get_attribute('data-page') == target_id
    assert selected.evaluate('e => e === document.activeElement')
    assert selected.evaluate('e => getComputedStyle(e).outlineStyle') != 'none'
    assert selected.bounding_box()['height'] >= 44
    assert selected.bounding_box()['width'] >= 24
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()
