"""Computed-style checks use synthetic static localhost content only."""
from tests.test_site_e2e import base_url, browser


def test_home_focus_is_visible_on_light_surface(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    page.route('**/api/**', lambda route: route.fulfill(json={'surveys': []}))
    page.goto(base_url + 'local.html')
    page.keyboard.press('Tab')
    style = page.locator('.skip').evaluate('element => {const s = getComputedStyle(element); return [s.outlineColor, s.outlineWidth]}')
    assert style == ['rgb(0, 103, 160)', '3px']
    context.close()


def test_base_components_and_reduced_motion(browser, base_url):
    context = browser.new_context(reduced_motion='reduce')
    page = context.new_page()
    page.goto(base_url + 'data.js')
    page.set_content('''<link rel="stylesheet" href="styles.css"><link rel="stylesheet" href="design-system.css">
      <button class="btn btn-primary">Primary</button><button class="btn btn-secondary">Secondary</button>
      <button class="btn btn-text">Text</button><article class="card">Card</article>
      <span class="pill" data-tone="positive">Ready</span>''')
    page.wait_for_function("getComputedStyle(document.body).fontSize === '16px'")
    result = page.evaluate('''() => {
      const style = selector => getComputedStyle(document.querySelector(selector));
      return {primary:[style('.btn-primary').backgroundColor, style('.btn-primary').color],
        secondary:style('.btn-secondary').borderTopColor, text:style('.btn-text').borderTopWidth,
        radius:style('.btn').borderRadius, card:[style('.card').padding, style('.card').borderRadius],
        positiveIcon:getComputedStyle(document.querySelector('.pill'), '::before').content,
        motion:style('.btn').transitionDuration, padding:getComputedStyle(document.documentElement).scrollPaddingTop};
    }''')
    assert result == {'primary': ['rgb(0, 103, 160)', 'rgb(255, 255, 255)'],
                      'secondary': 'rgb(116, 133, 154)', 'text': '0px', 'radius': '12px',
                      'card': ['24px', '20px'], 'positiveIcon': '""',
                      'motion': '0s', 'padding': '136px'}
    # A border-drawn check keeps the positive icon independent of emoji fonts.
    assert page.locator('.pill').evaluate("el => getComputedStyle(el, '::before').borderBottomWidth") == '2px'
    context.close()
