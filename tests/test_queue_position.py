"""Position is navigation, not the number of decisions saved."""
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


def test_position_follows_selected_item_and_tier(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=tiers)
    selected = page.locator('#queue-tabs [aria-selected=true]')
    assert selected.inner_text() == 'Must-fix 1/3'
    assert page.locator('#queue-progress').inner_text() == '0 of 3 handled'
    for name, label in [('must_fix', 'Must-fix'), ('quick_wins', 'Quick wins'), ('more', 'More ideas')]:
        items = detail['plan'][name]
        assert items
        fp = items[-1]['fingerprints'][0]
        finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == fp)
        focus(page, finding)
        assert selected.inner_text() == f'{label} {len(items)}/{len(items)}'
        assert page.locator('#coach h3').inner_text() == items[-1]['headline']
    assert not writes and not errors
    context.close()


def test_save_advances_position_but_undo_restores_position_and_progress(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    page.locator('#use-change').click()
    page.locator('#undo').wait_for()
    assert page.locator('#queue-tabs [aria-selected=true]').inner_text() == 'Must-fix 2/3'
    assert page.locator('#queue-progress').inner_text() == '1 of 3 handled'
    page.locator('#undo').click()
    page.wait_for_function("document.querySelector('#queue-progress').textContent === '0 of 3 handled'")
    assert page.locator('#queue-tabs [aria-selected=true]').inner_text() == 'Must-fix 1/3'
    assert not errors
    context.close()
