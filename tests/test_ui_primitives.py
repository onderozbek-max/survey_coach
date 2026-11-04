"""Shared primitives on isolated blank pages: no API, stored reviews or live data."""
from pathlib import Path

import pytest

from tests.test_site_e2e import browser

SITE = Path(__file__).parent.parent / 'site'
ICONS = ['check', 'alert', 'clock', 'sparkle', 'lock', 'copy', 'undo',
         'arrow-right', 'eye', 'play', 'pause', 'chevron-down', 'list',
         'share', 'download', 'text-size', 'dot', 'minus']


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.route('**/*', lambda route: route.abort())
    page.clock.install()
    page.clock.pause_at('2030-01-01T00:00:00')
    for name in ('dom.js', 'icons.js', 'diff.js', 'toast.js'):
        path = SITE / name
        if path.exists():
            page.add_script_tag(path=path)
    yield page
    context.close()


def require(page, name):
    assert page.evaluate(f'typeof SC.{name}') == 'function', f'SC.{name} is missing'


def test_word_diff_required_taste_and_price(page):
    require(page, 'wordDiff')
    assert page.evaluate('''SC.wordDiff(
        'How satisfied are you with the taste and price?',
        'How satisfied are you with the taste?')''') == [
        {'type': 'same', 'text': 'How satisfied are you with the taste'},
        {'type': 'del', 'text': ' and price'}, {'type': 'same', 'text': '?'}]


def test_word_diff_appended_sentence_is_one_insertion(page):
    require(page, 'wordDiff')
    assert page.evaluate('''SC.wordDiff('...celebrated!',
        '...celebrated! This takes about 14 minutes.')''') == [
        {'type': 'same', 'text': '...celebrated!'},
        {'type': 'ins', 'text': ' This takes about 14 minutes.'}]


@pytest.mark.parametrize(('before', 'after', 'expected'), [
    ('', '', []),
    (None, 'New!', [{'type': 'ins', 'text': 'New!'}]),
    ('Old?', None, [{'type': 'del', 'text': 'Old?'}]),
    ('a  b\n', 'a  b\n', [{'type': 'same', 'text': 'a  b\n'}]),
    ('a b', 'b a', [{'type': 'del', 'text': 'a '},
                      {'type': 'same', 'text': 'b'}, {'type': 'ins', 'text': ' a'}]),
    ('Hi, there!?', 'Hi; there:', [{'type': 'same', 'text': 'Hi'},
        {'type': 'del', 'text': ','}, {'type': 'ins', 'text': ';'},
        {'type': 'same', 'text': ' there'}, {'type': 'del', 'text': '!?'},
        {'type': 'ins', 'text': ':'}]),
])
def test_word_diff_empty_whitespace_punctuation_and_deterministic_ties(page, before, after, expected):
    require(page, 'wordDiff')
    for _ in range(2):
        assert page.evaluate('([a, b]) => SC.wordDiff(a, b)', [before, after]) == expected


def test_word_diff_large_input_falls_back_without_losing_text(page):
    require(page, 'wordDiff')
    before, after = 'old ' * 101, 'new ' * 101
    assert page.evaluate('([a, b]) => SC.wordDiff(a, b)', [before, after]) == [
        {'type': 'del', 'text': before}, {'type': 'ins', 'text': after}]


def diff_with_allocations(page, before, after):
    """Count real DP row allocations, restoring the browser constructor even on failure."""
    return page.evaluate('''([before, after]) => {
        const original = window.Uint16Array;
        let rows = 0, cells = 0;
        window.Uint16Array = new Proxy(original, {
            construct(target, args) {
                rows++;
                cells += args[0];
                return Reflect.construct(target, args);
            }
        });
        try {
            return {segments:SC.wordDiff(before, after), rows, cells};
        } finally {
            window.Uint16Array = original;
        }
    }''', [before, after])


@pytest.mark.parametrize('empty', ['', None])
@pytest.mark.parametrize('reverse', [False, True])
def test_word_diff_empty_side_never_allocates_dp(page, empty, reverse):
    text = 'word, \n' * 10000
    before, after = (text, empty) if reverse else (empty, text)
    result = diff_with_allocations(page, before, after)
    assert result['segments'] == [{'type': 'del' if reverse else 'ins', 'text': text}]
    assert result['rows'] == result['cells'] == 0


def test_word_diff_both_empty_never_allocates_dp(page):
    assert diff_with_allocations(page, '', None) == {'segments': [], 'rows': 0, 'cells': 0}


@pytest.mark.parametrize(('before', 'after'), [
    ('x', 'x ' * 10000),
    ('x ' * 10000, 'x'),
    ('x ' * 99 + 'x', 'x ' * 100),
    ('x ' * 100, 'x ' * 99 + 'x'),
])
def test_word_diff_bounds_actual_table_cells_without_allocating(page, before, after):
    result = diff_with_allocations(page, before, after)
    assert result['segments'] == [
        {'type': 'del', 'text': before}, {'type': 'ins', 'text': after}]
    assert result['rows'] == result['cells'] == 0


def test_word_diff_at_cell_limit_keeps_exact_lcs_behavior(page):
    text = 'x ' * 99 + 'x'  # 199 tokens: (199 + 1) ** 2 == 40,000 cells.
    assert diff_with_allocations(page, text, text) == {
        'segments': [{'type': 'same', 'text': text}], 'rows': 200, 'cells': 40000}


def test_render_diff_uses_semantic_elements_and_literal_text(page):
    require(page, 'renderDiff')
    result = page.evaluate('''() => {
        const diff = SC.renderDiff('Safe <img src=x onerror=alert(1)> old?',
                                   'Safe <img src=x onerror=alert(1)> new?');
        document.body.append(diff);
        return {tag:diff.tagName, cls:diff.className, del:diff.querySelector('del').textContent,
            ins:diff.querySelector('ins').textContent, images:diff.querySelectorAll('img').length,
            text:diff.textContent};
    }''')
    assert result == {'tag': 'P', 'cls': 'diff', 'del': 'old', 'ins': 'new',
                      'images': 0, 'text': 'Safe <img src=x onerror=alert(1)> oldnew?'}


@pytest.mark.parametrize('name', ICONS)
def test_icons_are_decorative_stroked_svg_nodes(page, name):
    require(page, 'icon')
    result = page.evaluate('''name => {
        const icon = SC.icon(name);
        return {tag:icon.localName, ns:icon.namespaceURI, hidden:icon.getAttribute('aria-hidden'),
            focusable:icon.getAttribute('focusable'), viewBox:icon.getAttribute('viewBox'),
            size:[icon.getAttribute('width'), icon.getAttribute('height')],
            stroke:icon.getAttribute('stroke'), width:icon.getAttribute('stroke-width'),
            cap:icon.getAttribute('stroke-linecap'), join:icon.getAttribute('stroke-linejoin'),
            fill:icon.getAttribute('fill'), count:icon.children.length,
            namespaces:[...icon.children].every(child => child.namespaceURI === icon.namespaceURI)};
    }''', name)
    assert result == {'tag': 'svg', 'ns': 'http://www.w3.org/2000/svg', 'hidden': 'true',
                      'focusable': 'false', 'viewBox': '0 0 24 24', 'size': ['18', '18'],
                      'stroke': 'currentColor', 'width': '1.75', 'cap': 'round', 'join': 'round',
                      'fill': 'none', 'count': result['count'], 'namespaces': True}
    assert result['count'] > 0


def test_icon_custom_size_and_each_call_returns_a_fresh_node(page):
    require(page, 'icon')
    assert page.evaluate('''() => {
        const a = SC.icon('check', {size:24}), b = SC.icon('check');
        return [a.getAttribute('width'), a.getAttribute('height'), a !== b];
    }''') == ['24', '24', True]


def test_toast_is_one_polite_region_with_safe_text_and_optional_undo(page):
    require(page, 'toast')
    page.evaluate("SC.toast('<img src=x onerror=alert(1)> Copied')")
    region = page.locator('#toast-region')
    assert region.get_attribute('role') == 'status'
    assert region.get_attribute('aria-live') == 'polite'
    assert page.locator('body > #toast-region > #toast').count() == 1
    assert page.locator('#toast img, #undo').count() == 0
    assert '<img src=x onerror=alert(1)> Copied' in region.inner_text()
    page.evaluate("SC.toast('Next')")
    assert page.locator('#toast-region, #toast').count() == 2
    assert 'Copied' not in region.inner_text()


def test_toast_undo_runs_once_even_for_detached_button(page):
    require(page, 'toast')
    page.evaluate('''() => {
        window.calls = 0;
        SC.toast('Copied', {undo:() => calls++});
        window.oldUndo = document.querySelector('#undo');
    }''')
    page.locator('#undo').click()
    page.evaluate('oldUndo.click()')
    assert page.evaluate('calls') == 1
    assert page.locator('#toast').count() == 0
    page.clock.run_for(6000)
    assert page.evaluate('calls') == 1


def test_toast_expires_at_six_seconds_without_undo(page):
    require(page, 'toast')
    page.evaluate("window.calls = 0; SC.toast('Copied', {undo:() => calls++})")
    page.clock.run_for(5999)
    assert page.locator('#toast').count() == 1
    page.clock.run_for(1)
    assert page.locator('#toast').count() == 0
    assert page.evaluate('calls') == 0


@pytest.mark.parametrize('dismiss', ['escape', 'button'])
def test_toast_escape_and_explicit_dismiss_invalidate_undo(page, dismiss):
    require(page, 'toast')
    page.evaluate('''() => {
        window.calls = 0;
        SC.toast('Copied', {undo:() => calls++});
        window.oldUndo = document.querySelector('#undo');
    }''')
    if dismiss == 'escape':
        page.keyboard.press('Escape')
    else:
        page.get_by_role('button', name='Dismiss notification', exact=True).click()
    page.evaluate('oldUndo.click()')
    assert page.locator('#toast').count() == 0
    assert page.evaluate('calls') == 0


def test_replaced_toast_ignores_old_timeout_and_old_undo(page):
    require(page, 'toast')
    page.evaluate('''() => {
        window.calls = 0;
        const original = window.setTimeout;
        window.setTimeout = (callback, delay) => {
            window.oldTimeout = callback;
            return original(callback, delay);
        };
        SC.toast('First', {undo:() => calls++});
        window.oldUndo = document.querySelector('#undo');
        window.setTimeout = original;
    }''')
    page.clock.run_for(3000)
    page.evaluate("SC.toast('Second'); oldTimeout(); oldUndo.click()")
    page.clock.run_for(3000)
    assert 'Second' in page.locator('#toast').inner_text()
    assert page.evaluate('calls') == 0
    page.clock.run_for(3000)
    assert page.locator('#toast').count() == 0


def test_undo_can_create_a_new_toast_without_old_cleanup_removing_it(page):
    require(page, 'toast')
    page.evaluate("SC.toast('Copied', {undo:() => SC.toast('Restored')})")
    page.locator('#undo').click()
    assert 'Restored' in page.locator('#toast').inner_text()
    page.keyboard.press('Escape')
    page.keyboard.press('Escape')
    assert page.locator('#toast').count() == 0
    assert page.locator('#toast-region').count() == 1
