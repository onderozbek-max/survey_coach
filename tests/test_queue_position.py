"""Progress is the number of decisions saved ("N of M done"), never the position of the open item."""
from tests.test_issue_loop_ui import open_review, focus
from tests.test_improve_ui import curated
from tests.test_site_e2e import base_url, browser


def tiers(detail):
    curated(detail)
    findings = detail['review']['findings']
    remaining = [f for f in findings if f['fingerprint'] not in {
        fp for item in detail['plan']['must_fix'] for fp in item['fingerprints']}]
    for name, selected in [('quick_wins', remaining[:3]), ('more', remaining[3:5])]:
        detail['plan'][name] = [dict(id=f['fingerprint'], fingerprints=[f['fingerprint']],
            headline=f['headline'], count=1, tier=name, screen=1, decided=False) for f in selected]
        detail['plan']['counts'][name] = len(selected)


def test_progress_counts_saved_decisions_not_the_open_item(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=tiers)
    tabs = page.locator('#queue-tabs [role=tab]')
    expected = ['Fix before launch\n0 of 3 done', 'Worth improving\n0 of 3 done', 'More ideas\n0 of 2 done']
    assert tabs.all_inner_texts() == expected
    assert page.locator('#queue-progress').inner_text() == '0 of 8 done'
    for name in ('must_fix', 'quick_wins', 'more'):
        fp = detail['plan'][name][-1]['fingerprints'][0]
        focus(page, next(f for f in detail['review']['findings'] if f['fingerprint'] == fp))
        assert tabs.all_inner_texts() == expected
        assert page.locator('#queue-progress').inner_text() == '0 of 8 done'
    # A filtered inspection never changes the numbers either.
    third = detail['plan']['must_fix'][-1]
    page.evaluate("o => SC.goChapter('improve', o)", {'fingerprints': third['fingerprints']})
    assert tabs.all_inner_texts() == expected
    page.evaluate("o => SC.goChapter('improve', o)", {'fingerprints': []})
    assert tabs.all_inner_texts() == expected
    assert not writes and not errors
    context.close()


def test_save_advances_and_undo_restores_progress(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    assert page.locator('#queue-tabs [role=tab]').first.inner_text() == 'Fix before launch\n1 of 3 done'
    assert page.locator('#queue-progress').inner_text() == '1 of 3 done'
    page.locator('#undo').click()
    page.wait_for_function("document.querySelector('#queue-progress').textContent === '0 of 3 done'")
    assert page.locator('#queue-tabs [role=tab]').first.inner_text() == 'Fix before launch\n0 of 3 done'
    assert not errors
    context.close()
