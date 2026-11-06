"""Sign off carries no second opinion (3E): no legacy open-count line that can contradict the verdict, no old
"Since version N" block with its jargon (the Verdict page's delta card is the one comparison, linked from here), and the
Kept on purpose list sits in the card beside the Slack post that says the same. Intercepted synthetic reviews; offline."""
import re

import pytest
from playwright.sync_api import expect

from tests.signoff_helpers import open_signoff
from tests.test_site_e2e import base_url, browser

JARGON = ('blanket verification', 'checks, paths or wording may have changed', 'no longer flagged ·', 'Since version', 'Not comparable / uncertain')


def delta(fixed=1, still=1, new=0, uncertain=1):
    item = lambda text, resolution: {'fingerprint': text, 'criterion_id': '3.1', 'headline': text, 'location': 'Q1 · Screen 2', 'resolution': resolution}
    return {'from_version': 1, 'to_version': 2, 'counts': {'fixed': fixed, 'still': still, 'new': new, 'uncertain': uncertain},
            'summary': f'{fixed} fixed · {still} still open · {new} new · {uncertain} couldn\'t compare',
            'caveat': 'Fixed = no longer flagged by our checks.',
            'fixed': [{**item('Reading level is high', 'No longer flagged'), 'before': 'Old', 'after': 'New', 'by_rewrite': False}][:fixed],
            'still': [item('Two things at once', 'Still flagged')][:still], 'new': [],
            'uncertain': [item('Path changed', 'Not verified: changed context')][:uncertain]}


def with_delta(detail):
    detail['version_delta'] = delta()


@pytest.mark.parametrize('ready', [True, False])
def test_the_change_list_makes_no_claim_about_what_is_open(browser, base_url, ready):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=ready, extra=with_delta)
    summary = page.locator('#share-summary').inner_text()
    assert re.fullmatch(r'\d+ changes? chosen', summary), summary
    block = page.locator('#share-changes').inner_text()
    assert 'still open' not in block and 'to fix before launch' not in block and 'kept on purpose' not in block.lower()
    assert page.locator('#kept-reasons').count() == 0              # replaced by the card's Kept on purpose list
    context.close()


def test_a_later_version_links_to_the_delta_card_and_carries_none_of_the_old_block(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=False, extra=with_delta)
    text = page.locator('#chapter-share').inner_text()
    for phrase in JARGON:
        assert phrase not in text, phrase
    assert page.locator('.round-comparison').count() == 0
    link = page.get_by_role('link', name='See what changed since v1', exact=True)
    assert link.count() == 1
    link.click()
    page.wait_for_function("location.hash === '#overview'")
    card = page.locator('#version-delta')
    expect(card).to_be_visible()
    expect(page.locator('#delta-h')).to_be_focused()
    body = card.inner_text()
    assert "1 item we couldn't compare" in body and 'Fixed (1)' in body and 'Still open (1)' in body     # four buckets, here only
    assert 'Fixed = no longer flagged by our checks.' in body
    assert not errors
    context.close()


def test_the_version_timeline_stays_so_other_versions_can_be_opened(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, extra=with_delta)
    assert page.locator('.round-timeline a').count() == 2
    assert page.locator('.round-timeline [aria-current=page]').inner_text() == 'Version 2'
    context.close()


def test_no_link_on_version_one_and_none_without_a_comparison(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, version=1)
    assert page.locator('#delta-link').count() == 0 and page.locator('#version-changes').inner_text().strip() == ''
    context.close()
    context, page, detail, posts, errors = open_signoff(browser, base_url, version=2)           # no version_delta on this payload
    assert detail.get('version_delta') in (None, {}) and page.locator('#delta-link').count() == 0
    text = page.locator('#chapter-share').inner_text()
    assert 'no longer flagged' not in text.lower() and 'claimed fixed' not in text.lower()
    for phrase in JARGON:
        assert phrase not in text, phrase
    context.close()


def keep_one(detail):
    item = detail['overview']['items'][0]
    item.update(open=False, handled_kind='keep')
    detail['decisions'][item['fingerprints'][0]] = {'action': 'keep', 'keep_reason': 'owner_decided', 'reason': 'Checked on my phone'}
    detail['_kept'] = item['headline']


def test_kept_on_purpose_is_in_the_card_and_the_post_with_the_same_reason(browser, base_url):
    context, page, detail, posts, errors = open_signoff(browser, base_url, ready=False, extra=keep_one)
    kept = page.locator('#review-card [aria-label="Kept on purpose"] li')
    assert kept.count() == 1
    assert detail['_kept'] in kept.inner_text() and 'Owner decided: Checked on my phone' in kept.inner_text()
    assert 'accepted risk, not verified fixes' in page.locator('#review-card').inner_text()
    post = page.locator('#slack-post').inner_text()
    assert f"{detail['_kept']} – Owner decided: Checked on my phone" in post
    context.close()
