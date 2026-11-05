"""Small helpers for the header: the overflow menu, the step menu (collapsed at 390px) and the Check again dialog."""


def open_how_we_check(page):
    """Open the 'How we check' dialog through the header overflow menu, the only way in."""
    if page.locator('#header-menu-button').get_attribute('aria-expanded') != 'true':
        page.locator('#header-menu-button').click()
    page.locator('#about-review').click()


def go_to(page, chapter):
    """Follow a step link, opening the step menu first when the header has collapsed it."""
    link = page.locator(f'#chapter-nav [data-chapter={chapter}]')
    if not link.is_visible():
        page.locator('#steps-button').click()
    link.click()


def open_recheck(page):
    """Open the Check again dialog from the always-available header button."""
    page.locator('#check-again').click()
    page.locator('#recheck-dialog').wait_for(state='visible')
