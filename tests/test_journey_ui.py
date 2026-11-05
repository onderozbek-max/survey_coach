"""The journey strip on the Verdict and in the Fix header (brief 4.4, D11, D12): one encoding, nothing skipped, keyboard operable."""
import pytest

from tests.fixflow_helpers import detail_of, flow  # noqa: F401  (fixture)
from tests.journey_helpers import add_journey, open_flow_verdict, open_verdict
from tests.site_helpers import go_to
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)

FLOOR = 28           # css --journey-min on a mouse device


def segments(page):
    return page.locator('#journey button[data-page]')


def test_width_is_the_only_encoding_and_is_proportional_to_seconds(browser, flow):
    context, page, errors = open_flow_verdict(browser, flow, width=1440)
    detail = detail_of(page)
    journey = detail['presentation']['journey']
    assert segments(page).count() == len(journey) == len(detail['screens'])
    sections = page.evaluate("""() => [...document.querySelectorAll('#journey .journey-section')].map(s => ({
      width: s.getBoundingClientRect().width, seconds: Number(s.style.getPropertyValue('--sec')),
      segments: [...s.querySelectorAll('button[data-page]')].map(b => ({width: b.getBoundingClientRect().width,
        seconds: Number(b.closest('li').style.getPropertyValue('--sec'))}))}))""")
    widths = [seg['width'] for s in sections for seg in s['segments']]
    longest = max(sections, key=lambda s: s['seconds'])
    rate = longest['width'] / longest['seconds']          # the longest section is never held up by a floor
    proportional = [s for s in sections if s['width'] / s['seconds'] == pytest.approx(rate, rel=0.04)]
    assert len(sections) >= 6 and len(proportional) >= 3
    # A floor (a whole section label, a tappable segment) may widen a short section; nothing is ever narrower than its time.
    assert all(s['width'] >= rate * s['seconds'] * 0.96 for s in sections)
    free = [seg for s in proportional for seg in s['segments'] if seg['width'] > FLOOR * 1.5]
    assert len(free) >= 3
    for seg in free:
        assert seg['width'] / seg['seconds'] == pytest.approx(rate, rel=0.05), seg          # width = time, nothing else
    assert all(w >= FLOOR - 1 for w in widths)                             # a short screen stays visible and clickable
    fills = page.evaluate("""() => [...document.querySelectorAll('#journey button[data-page]')]
      .filter(b => !b.matches('[aria-current=step]')).map(b => getComputedStyle(b).backgroundColor)""")
    assert len(set(fills)) == 1                                            # no blue/yellow/red load colouring
    assert page.locator('.energy-bar, .energy-map, .energy-legend, .energy-fill').count() == 0
    assert 'Estimated load' not in page.locator('#chapter-overview').inner_text()
    assert not errors
    context.close()


def test_every_segment_is_labelled_including_the_last_and_sections_are_served_labels(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url, width=1440)
    journey = detail['presentation']['journey']
    numbers = page.locator('#journey .journey-num')
    assert numbers.all_text_contents() == [str(s['screen']) for s in journey]
    last = numbers.last
    assert last.is_visible() and last.bounding_box()['x'] + last.bounding_box()['width'] <= 1440
    served = [s['label'] for s in detail['presentation']['journey_sections']]
    assert page.locator('#journey .journey-label').all_text_contents() == served
    clipped = page.evaluate("[...document.querySelectorAll('#journey .journey-label')].filter(l => l.scrollWidth > l.clientWidth + 1).map(l => l.textContent)")
    assert clipped == []                                                   # D11: no label cut off
    assert page.locator('#journey [aria-label=\"Screens in order\"]').count() == 1
    group = page.locator('#journey [role=group]')
    assert f'{len(journey)} screens' in group.get_attribute('aria-label')
    assert not writes and not errors
    context.close()


def test_a_neutral_fallback_label_is_drawn_exactly_as_served(browser, base_url):
    def neutral(detail):
        pres = detail['presentation']
        for seg in pres['journey']:
            seg.update(section='s1', section_label='Screens 1-13')
        pres['journey_sections'] = [{'id': 's1', 'label': 'Screens 1-13', 'kind': 'screens', 'start_screen': 1, 'end_screen': 13, 'running': 0, 'seconds': 266}]
    context, page, detail, writes, errors = open_verdict(browser, base_url, prepare=neutral, derived=False)
    assert page.locator('#journey .journey-label').all_text_contents() == ['Screens 1-13']
    context.close()


def test_pins_use_the_four_state_chips_with_text_never_colour_alone(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url)
    pinned = [s for s in detail['presentation']['journey'] if s['state']]
    assert pinned
    for seg in pinned:
        button = page.locator(f'#journey button[data-page={seg["page_id"]}]')
        assert button.locator('.journey-pin svg').count() == 1
        name = button.inner_text()
        assert seg['tooltip'] in name and {'fix_before_launch': 'Fix before launch', 'worth_improving': 'Worth improving', 'you_check': 'You check'}[seg['state']] in name
    unpinned = [s for s in detail['presentation']['journey'] if not s['state']]
    for seg in unpinned:
        assert page.locator(f'#journey button[data-page={seg["page_id"]}] .journey-pin').count() == 0
    context.close()


def test_hover_and_keyboard_focus_show_the_served_tooltip_and_escape_hides_it(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url)
    journey = detail['presentation']['journey']
    tip = page.locator('#journey .journey-tip')
    assert not tip.is_visible()
    segments(page).nth(3).hover()
    assert tip.is_visible() and tip.inner_text() == journey[3]['tooltip']
    page.mouse.move(0, 0)
    assert not tip.is_visible()
    page.keyboard.press('Tab')       # reach the strip with the keyboard
    for _ in range(30):
        if page.evaluate("document.activeElement.closest('#journey') !== null"):
            break
        page.keyboard.press('Tab')
    page.keyboard.press('ArrowRight')
    assert tip.is_visible() and tip.inner_text() == journey[1]['tooltip']
    page.keyboard.press('Escape')
    assert not tip.is_visible()
    assert not writes and not errors
    context.close()


def test_the_strip_is_one_tab_stop_with_arrows_home_end_and_enter_jumps_to_the_screen(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url)
    stops = page.evaluate("[...document.querySelectorAll('#journey button[data-page]')].filter(b => b.tabIndex === 0).length")
    assert stops == 1
    segments(page).first.focus()
    page.keyboard.press('ArrowRight'); page.keyboard.press('ArrowRight')
    assert segments(page).nth(2).evaluate('el => el === document.activeElement')
    page.keyboard.press('End')
    assert segments(page).last.evaluate('el => el === document.activeElement')
    page.keyboard.press('Home')
    assert segments(page).first.evaluate('el => el === document.activeElement')
    page.keyboard.press('ArrowRight'); page.keyboard.press('ArrowRight')
    page.keyboard.press('Enter')
    assert page.url.endswith('#improve')
    assert detail['screens'][2]['name'] in page.locator('#stage .phone-bar').inner_text()
    assert not writes and not errors
    context.close()


def test_a_click_opens_that_screen_in_the_fix_flow(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url)
    segments(page).nth(4).click()
    assert page.url.endswith('#improve')
    assert detail['screens'][4]['name'] in page.locator('#stage .phone-bar').inner_text()
    context.close()


def test_the_fix_header_shows_a_compact_strip_with_the_current_screen_outlined(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='improve', prepare=add_journey)
    strip = page.locator('#improve-bar .journey.compact')
    assert strip.count() == 1 and strip.locator('.journey-label').count() == 0
    current = strip.locator('button[aria-current=step]')
    assert current.count() == 1
    assert int(current.evaluate("el => parseFloat(getComputedStyle(el).outlineWidth)")) >= 2      # the selected segment is clearly outlined
    target = strip.locator('button[data-page]').nth(5)
    target.click()
    assert detail['screens'][5]['name'] in page.locator('#stage .phone-bar').inner_text()
    assert strip.locator('button[aria-current=step]').get_attribute('data-page') == detail['presentation']['journey'][5]['page_id']
    assert page.locator('#improve-bar .energy-bar').count() == 0
    # D12: the old toolbar chart is gone for good
    assert page.locator('.energy-fill, .energy-column').count() == 0
    context.close()


def test_keyboard_focus_survives_a_screen_change_in_the_fix_header(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='improve', prepare=add_journey)
    button = page.locator('#improve-bar .journey button[data-page]').nth(2)
    button.focus()
    page.keyboard.press('Enter')
    assert page.evaluate("document.activeElement.dataset.page") == detail['presentation']['journey'][2]['page_id']
    context.close()


def test_the_phone_timeline_uses_the_same_strip_and_keeps_its_plain_line(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='improve', prepare=add_journey)
    bar = page.locator('#stage .timebar')
    assert bar.get_attribute('aria-hidden') == 'true' and bar.locator('i').count() == 1
    assert bar.locator('b').count() == len(detail['presentation']['journey'])
    def current_index():
        pages = [s['page_id'] for s in detail['presentation']['journey']]
        return pages.index(page.locator('#improve-bar .journey button[aria-current=step]').get_attribute('data-page'))
    assert bar.locator('b.reached').count() == current_index() + 1       # filled up to the screen the phone shows
    before = current_index()
    page.locator('#stage [data-fk=next]').click()
    assert current_index() == before + 1 and bar.locator('b.reached').count() == before + 2
    context.close()


@pytest.mark.parametrize('width', [390, 1024])
def test_narrow_widths_scroll_the_strip_not_the_page_and_keep_every_label(browser, base_url, width):
    context, page, detail, writes, errors = open_verdict(browser, base_url, width=width)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    overflow = page.locator('#journey .journey-scroll').evaluate('el => el.scrollWidth > el.clientWidth + 1')
    hint = page.locator('#journey .journey-more')
    assert hint.is_visible() == overflow
    if width == 390:
        assert overflow and 'Scroll sideways' in hint.inner_text()
    assert page.locator('#journey .journey-num').count() == len(detail['screens'])
    segments(page).last.focus()
    assert segments(page).last.is_visible()
    box = segments(page).last.bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1       # focusing the last one scrolls it into view
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    context.close()


def test_a_text_list_is_the_alternative_to_the_strip(browser, base_url):
    context, page, detail, writes, errors = open_verdict(browser, base_url)
    fold = page.locator('#journey details.journey-list')
    assert not fold.get_attribute('open')
    fold.locator('summary').click()
    rows = fold.locator('li')
    assert rows.count() == len(detail['screens'])
    assert detail['presentation']['journey'][3]['tooltip'] in rows.nth(3).inner_text()
    context.close()


def test_without_a_journey_the_verdict_has_no_empty_strip(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview', derived=False,
                                                        prepare=lambda d: d['presentation'].pop('journey', None))
    assert page.locator('#journey, .journey').count() == 0
    assert page.get_by_role('heading', name='Member journey').count() == 0
    assert not errors
    context.close()
