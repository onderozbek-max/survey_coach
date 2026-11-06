"""Final accessibility sweep (workstream 3D): the same rules on every main surface at 1440 and 390 CSS px.

Surfaces: Home, Verdict (with its journey strip), Fix, Sign off, and the Play-as-a-member dialog.
Rules (brief section 11, WCAG 2.2 AA): no sideways page scroll, every control has an accessible name, one H1,
no duplicated live regions, state never by colour alone, hit areas of at least 24x24 CSS px (primary 44),
a visible focus indicator on every keyboard stop, and no motion when it is reduced.
Synthetic data, intercepted writes, computed styles only (no screenshots, no axe), offline."""
import pytest

from tests.fixflow_helpers import detail_of, flow, open_flow  # noqa: F401  (flow is a fixture)
from tests.journey_helpers import open_verdict
from tests.signoff_helpers import open_signoff
from tests.test_home_how_it_works import home
from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser  # noqa: F401  (fixtures)

WIDTHS = (1440, 390)
MIN_TARGET, PRIMARY_TARGET = 24, 44
INTERACTIVE = ('a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], '
               '[role=tab], [role=checkbox], [role=radio], [tabindex]:not([tabindex="-1"])')


def open_home(browser, base_url, width):
    context, page, errors = home(browser, base_url, width=width)
    return context, page, errors


def open_verdict_page(browser, base_url, width):
    context, page, detail, writes, errors = open_verdict(browser, base_url, width=width)
    page.locator('#overview-h').wait_for()
    return context, page, errors


def open_fix(browser, base_url, width):
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, chapter='improve')
    page.locator('#coach h3').first.wait_for()
    return context, page, errors


def open_sign_off(browser, base_url, width):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=False, width=width)
    page.locator('#signoff-form').wait_for()
    return context, page, errors


def open_member_dialog(browser, base_url, width):
    context, page, errors = open_verdict_page(browser, base_url, width)
    page.locator('#preview-member').focus()
    page.keyboard.press('Enter')                        # opened by keyboard, so the first focus ring is a keyboard one
    page.get_by_role('dialog', name='Play it as a member').wait_for()
    return context, page, errors


SURFACES = {'home': open_home, 'verdict': open_verdict_page, 'fix': open_fix, 'signoff': open_sign_off,
            'member-dialog': open_member_dialog}
CASES = [pytest.param(name, width, id=f'{name}-{width}') for name in SURFACES for width in WIDTHS]

# One pass in the page: everything that needs no keyboard. Returns plain data so each rule asserts separately.
SURVEY_JS = """(selector) => {
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[hidden], [inert]'); };
  const text = id => document.getElementById(id)?.textContent.trim() || '';
  const nameOf = el => {
    const labelled = (el.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean).map(text).join(' ').trim();
    const viaLabel = el.labels ? [...el.labels].map(l => l.textContent.trim()).join(' ').trim() : '';
    const alt = el.tagName === 'IMG' ? el.getAttribute('alt') : '';
    const value = el.tagName === 'INPUT' && ['submit', 'button'].includes(el.type) ? el.value : '';
    const inner = el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' ? '' : el.textContent.trim();
    const img = el.querySelector('img[alt]:not([alt=""]), svg[aria-label], [role=img][aria-label]');
    return (el.getAttribute('aria-label') || labelled || viaLabel || alt || value || inner || (img && (img.getAttribute('alt') || img.getAttribute('aria-label'))) || el.getAttribute('title') || '').trim();
  };
  const describe = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
  const controls = [...document.querySelectorAll(selector)].filter(visible);
  const live = [...document.querySelectorAll('[aria-live]:not([aria-live=off]), [role=status], [role=alert], [role=log]')];
  const liveText = live.map(el => el.textContent.trim()).filter(Boolean);
  const chips = [...document.querySelectorAll('.state-chip')].filter(visible);
  const icons = [...document.querySelectorAll('.state-icon')].filter(visible);
  return {
    overflow: document.documentElement.scrollWidth - innerWidth,
    h1: [...document.querySelectorAll('h1')].filter(visible).length,
    unnamed: controls.filter(el => !nameOf(el)).map(describe),
    liveIds: live.map(el => el.id).filter(Boolean),
    liveNested: live.filter(el => el.parentElement && el.parentElement.closest('[aria-live]:not([aria-live=off]), [role=status], [role=alert], [role=log]')).map(describe),
    liveDuplicateText: liveText.filter((t, i) => liveText.indexOf(t) !== i),
    chipsWithoutText: chips.filter(el => !el.textContent.trim()).map(describe),
    iconsWithoutText: icons.filter(el => !(el.closest('button, a, li, p, dd, td, summary, label, h2, h3, h4') || el.parentElement).textContent.trim())
      .map(el => describe(el.parentElement) + ' > ' + describe(el)),
    small: controls.filter(el => !el.closest('p, li > span, dd') || el.matches('button, .btn'))
      .filter(el => { const r = el.getBoundingClientRect(); return r.width < %(min)d || r.height < %(min)d; })
      .map(el => describe(el) + ' ' + Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height)),
    primarySmall: controls.filter(el => el.matches('.btn-primary'))
      .filter(el => el.getBoundingClientRect().height < %(primary)d)
      .map(el => describe(el) + ' ' + Math.round(el.getBoundingClientRect().height)),
  };
}""" % {'min': MIN_TARGET, 'primary': PRIMARY_TARGET}

# Tab through the page: every stop must show a focus indicator (outline, or a box-shadow ring) on itself, or on the
# control it visually belongs to (a custom checkbox draws its ring on the label that wraps the input).
FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const ring = e => { const s = getComputedStyle(e);
    const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 && !/rgba\\(.*, 0\\)$/.test(s.outlineColor);
    const shadow = s.boxShadow !== 'none' && !/rgba\\(0, 0, 0, 0\\)/.test(s.boxShadow);
    return outline || shadow; };
  const owner = el.closest('label') || el.parentElement;
  return {id: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : ''),
          visible: ring(el) || (owner && ring(owner)),
          again: (() => { const seen = el.hasAttribute('data-sweep-seen'); el.setAttribute('data-sweep-seen', ''); return seen; })()};   // true on a second visit
}"""


@pytest.mark.parametrize('name, width', CASES)
def test_static_rules(browser, base_url, name, width):
    context, page, errors = SURFACES[name](browser, base_url, width)
    report = page.evaluate(SURVEY_JS, INTERACTIVE)
    assert report['overflow'] <= 0, f"page scrolls sideways by {report['overflow']}px"
    assert report['h1'] == 1, f"{report['h1']} H1 headings"
    assert not report['unnamed'], f"controls without an accessible name: {report['unnamed']}"
    assert len(report['liveIds']) == len(set(report['liveIds'])), f"duplicate live region ids: {report['liveIds']}"
    assert not report['liveNested'], f"live region inside a live region: {report['liveNested']}"
    assert not report['liveDuplicateText'], f"the same announcement in two live regions: {report['liveDuplicateText']}"
    assert not report['chipsWithoutText'], f"state chips with no text: {report['chipsWithoutText']}"
    assert not report['iconsWithoutText'], f"state icons with no words beside them: {report['iconsWithoutText']}"
    assert not report['small'], f"hit areas under {MIN_TARGET}px: {report['small']}"
    assert not report['primarySmall'], f"primary controls under {PRIMARY_TARGET}px: {report['primarySmall']}"
    assert not errors
    context.close()


@pytest.mark.parametrize('name, width', CASES)
def test_every_keyboard_stop_shows_a_focus_indicator(browser, base_url, name, width):
    context, page, errors = SURFACES[name](browser, base_url, width)
    stops = []
    if page.locator('dialog[open]').count():           # a modal opens with focus already inside: that is the first stop
        stops.append(page.evaluate(FOCUS_JS))
    else:
        page.evaluate('document.activeElement && document.activeElement.blur()')
    for _ in range(250):
        page.keyboard.press('Tab')
        stop = page.evaluate(FOCUS_JS)
        if stop is None or stop['again']:              # left the page, or wrapped round (dialogs trap focus)
            break
        stops.append(stop)
    assert len(stops) >= 2, 'the page has no keyboard path'
    assert [s['id'] for s in stops if not s['visible']] == [], 'tab stops without a visible focus indicator'
    assert not errors
    context.close()


@pytest.mark.parametrize('width', WIDTHS)
def test_motion_is_off_when_reduced_on_every_surface(browser, base_url, width):
    """Every surface runs under prefers-reduced-motion: no CSS animation is running and no transition has a duration."""
    for name, opener in SURFACES.items():
        context, page, errors = opener(browser, base_url, width)
        page.emulate_media(reduced_motion='reduce')
        page.evaluate("""document.body.append(...['celebrate-mark', 'celebrate-dot', 'progress-ring'].map(c =>
          Object.assign(document.createElement('div'), {className: c, 'data-probe': ''})))""")
        report = page.evaluate("""() => ({
          running: document.getAnimations().filter(a => a.playState === 'running' && a.effect?.getComputedTiming().duration > 1).length,
          animated: [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).animationName !== 'none').length,
          transitioned: [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).transitionDuration.split(',').some(d => parseFloat(d) > 0.001)).length,
          probes: [...document.querySelectorAll('[data-probe]')].map(e => getComputedStyle(e).animationName + '|' + getComputedStyle(e).transitionDuration)})""")
        assert report['running'] == 0 and report['animated'] == 0 and report['transitioned'] == 0, f'{name}: {report}'
        assert all(p.startswith('none|') and p.split('|')[1] in ('0s', '0.001s') for p in report['probes']), f'{name}: {report}'
        assert not errors
        context.close()


def test_the_real_completion_moment_does_not_move_when_motion_is_reduced(browser, flow):  # noqa: F811
    """The celebration that really shows after the last fix (real server), with motion reduced before it starts."""
    context, page, errors = open_flow(browser, flow)
    page.emulate_media(reduced_motion='reduce')
    for _ in range(detail_of(page)['queue']['counts']['total']):
        card = page.locator('#coach .fix-card')
        if card.get_by_label('I checked').count():
            card.get_by_label('I checked').check()
        card.get_by_role('button', name='Mark done in RedJade').click()
        page.wait_for_function("document.querySelector('#toast') !== null")
    page.locator('#coach .completion h3').wait_for()
    page.locator('.celebrate-mark').wait_for()
    moving = page.evaluate("""() => [...document.querySelectorAll('.celebrate-mark, .celebrate-dot, .progress-ring')]
      .filter(e => getComputedStyle(e).animationName !== 'none' || parseFloat(getComputedStyle(e).transitionDuration) > 0.001).length""")
    assert moving == 0
    assert page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length") == 0
    assert not errors
    context.close()
