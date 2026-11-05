"""Progress is the number of decisions saved ("N of M done"), never the position of the open item (2D: one fix list)."""
from tests.test_issue_loop_ui import focus, open_review, single_paste
from tests.test_site_e2e import base_url, browser


def test_progress_counts_saved_decisions_not_the_open_item(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    total = detail['queue']['counts']['total']
    expected = f'0 of {total} done'
    assert page.locator('#queue-progress').inner_text() == expected
    for entry in (detail['queue']['items'][0], detail['queue']['items'][-1]):
        page.locator(f'[data-fk="fix-row-{entry["id"]}"]').click()
        assert page.locator('#queue-progress').inner_text() == expected
    # A filtered inspection never changes the numbers either.
    for options in ({'fingerprints': detail['queue']['items'][-1]['fingerprints']}, {'fingerprints': []}):
        page.evaluate("o => SC.goChapter('improve', o)", options)
        assert page.locator('#queue-progress').inner_text() == expected
    assert not writes and not errors
    context.close()


def test_save_advances_and_undo_restores_progress(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    total = detail['queue']['counts']['total']
    finding, entry = single_paste(detail)
    focus(page, finding)
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    assert page.locator('#queue-progress').inner_text() == f'1 of {total} done'
    page.locator('#undo').click()
    page.wait_for_function(f"document.querySelector('#queue-progress').textContent === '0 of {total} done'")
    assert page.locator(f'[data-fk="fix-row-{entry["id"]}"]').get_attribute('data-state') != 'done'
    assert not errors
    context.close()
