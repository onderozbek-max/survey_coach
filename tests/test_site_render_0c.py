"""Workstream 0C rendering contracts (D3, D4, D5, D9, D10). Synthetic data and intercepted API only."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_improve_ui import curated, pattern
from tests.test_issue_loop_ui import open_review
from tests.test_queue_position import tiers
from tests.test_site_e2e import base_url, browser

ROOT = Path(__file__).parent.parent
SITE = ROOT / 'site'
SOURCES = [path for path in sorted(SITE.glob('*.js')) + sorted(SITE.glob('*.html')) if path.name != 'data.js']
STRAY_DIGITS = """root => { const found = [], walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) if (/^\\s*\\d+\\s*$/.test(walk.currentNode.textContent)) found.push(walk.currentNode.textContent.trim());
  return found; }"""


# ---- D4: a zero length is never rendered as text ------------------------------------------------

def test_no_length_and_h_pattern_anywhere_in_site():
    offenders = [path.name for path in SOURCES if re.search(r'\.length\s*&&\s*h\(', path.read_text())]
    assert offenders == [], f"'.length && h(' renders a literal 0; use an explicit conditional: {offenders}"


def test_zero_count_round_shows_no_stray_digits(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share')
    assert detail['round_changes'] == {'fixed': [], 'still': [], 'new': [], 'uncertain': []}
    assert '0000' not in page.locator('#chapter-share').inner_text()
    assert page.locator('.round-comparison').evaluate(STRAY_DIGITS) == []
    assert not errors
    context.close()


def test_card_with_empty_also_affects_shows_no_stray_digit(browser, base_url):
    def prepare(detail):
        for finding in detail['review']['findings']:
            finding['also_affects'] = []
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    assert page.locator('#coach .card').count() == 1
    assert page.locator('#coach .card').evaluate(STRAY_DIGITS) == []
    assert not errors
    context.close()


# ---- D5: "Use all N" counts real suggestions, hides under two and explains itself -----------------

def suggestions_only(count):
    """A pattern item of three findings of which only `count` carry a suggestion."""
    def prepare(detail):
        pattern(detail)
        for fp in detail['plan']['more'][0]['fingerprints'][count:]:
            next(f for f in detail['review']['findings'] if f['fingerprint'] == fp).update(suggested_text=None, options=[])
    return prepare


def test_use_all_counts_every_applicable_suggestion(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=pattern)
    page.locator('[data-fk=queue-more]').click()
    assert page.locator('#use-all').inner_text() == 'Use all 3 suggestions'
    assert page.locator('#use-all-note').count() == 0
    assert not errors
    context.close()


def test_use_all_hides_when_only_one_finding_has_a_suggestion(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=suggestions_only(1))
    page.locator('[data-fk=queue-more]').click()
    assert page.locator('.pattern-row').count() == 3
    assert page.locator('#use-all').count() == 0
    assert not errors
    context.close()


def test_use_all_applies_to_applicable_suggestions_and_says_what_is_left(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=suggestions_only(2))
    page.locator('[data-fk=queue-more]').click()
    button = page.locator('#use-all')
    assert button.inner_text() == 'Use all 2 suggestions' and button.is_enabled()
    assert '1 finding here has no suggested wording' in page.locator('#use-all-note').inner_text()
    assert button.get_attribute('aria-describedby') == 'use-all-note'
    button.click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert len(writes) == 2 and all(w['action'] == 'pick' for w in writes)
    assert not errors
    context.close()


def test_use_all_is_disabled_with_a_reason_once_everything_is_chosen(browser, base_url):
    def prepare(detail):
        suggestions_only(2)(detail)
        for fp in detail['plan']['more'][0]['fingerprints'][:2]:
            finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == fp)
            text = finding.get('suggested_text') or finding['options'][0]['text']
            detail['decisions'][fp] = dict(action='pick', picked_text=text, reason='', manual_done=False)
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    page.locator('[data-fk=queue-more]').click()
    assert page.locator('#use-all').is_disabled()
    assert 'All 2 suggestions are already chosen.' in page.locator('#use-all-note').inner_text()
    assert not writes and not errors
    context.close()


# ---- D3: every button has the base component and is not dressed like an input ---------------------

def test_every_secondary_button_declares_the_base_class():
    pattern_ = re.compile(r"""class(?:=|:\s*)["']btn-secondary""")
    offenders = [path.name for path in SOURCES if pattern_.search(path.read_text())]
    assert offenders == [], f'btn-secondary without .btn: {offenders}'


def test_buttons_are_padded_rounded_and_unlike_inputs(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('[data-chapter=share]').click()
    page.locator('#about-review').click()
    page.keyboard.press('Escape')
    result = page.evaluate('''() => {
      const style = el => getComputedStyle(el);
      const bare = [...document.querySelectorAll('.btn-secondary, .btn:not(.btn-text)')].filter(el => {
        const s = style(el); return parseFloat(s.paddingLeft) < 8 || parseFloat(s.borderTopLeftRadius) < 8; })
        .map(el => el.outerHTML.slice(0, 80));
      const next = style(document.querySelector('#recheck-form button[type=submit]')), input = style(document.querySelector('#survey-link'));
      return {bare, checkAgain:document.querySelector('#check-again').className,
        count:document.querySelectorAll('.btn-secondary').length,
        sameFill:next.backgroundColor === input.backgroundColor, sameText:next.color === input.color,
        weight:[next.fontWeight, input.fontWeight]};
    }''')
    assert result['bare'] == [], result
    assert 'btn' in result['checkAgain'].split()
    assert result['count'] >= 3
    assert not (result['sameFill'] and result['sameText']), 'a button must not look like a text input'
    assert not errors
    context.close()


def test_dialog_close_buttons_are_real_buttons(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    closes = page.evaluate('''() => [...document.querySelectorAll('dialog > button.btn-secondary')]
      .map(el => [el.classList.contains('btn'), parseFloat(getComputedStyle(el).paddingLeft), el.textContent])''')
    assert len(closes) >= 2 and all(row[0] and row[1] >= 8 and row[2] == 'Close' for row in closes), closes
    assert not errors
    context.close()


# ---- D9: one "N of M done" model for tabs, toolbar line and drawer flags ---------------------------

def screen_of(detail, fingerprint):
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == fingerprint)
    return next(s for s in detail['screens'] if s['page_id'] == finding['page_id']
                or any(q['id'] == finding.get('question_id') for q in s.get('questions', [])))


def drawer_progress(page, name):
    page.locator('#all-screens').click()
    row = page.locator('#screen-drawer .screen-row').filter(has=page.locator('strong', has_text=re.compile(rf'^{re.escape(name)}$'))).first
    text = row.locator('.sr-only').inner_text()
    page.get_by_role('button', name='Close all screens').click()
    done, total = re.search(r'(\d+) of (\d+) done', text).groups()
    return int(done), int(total), text


def test_one_progress_model_everywhere(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=tiers)
    tabs = page.locator('#queue-tabs [role=tab]')
    sizes = [len(detail['plan'][name]) for name in ('must_fix', 'quick_wins', 'more')]
    assert tabs.all_inner_texts() == [f'Must-fix\n0 of {sizes[0]} done', f'Quick wins\n0 of {sizes[1]} done',
                                      f'More ideas\n0 of {sizes[2]} done']
    assert page.locator('#queue-progress').inner_text() == f'0 of {sum(sizes)} done'
    first = detail['plan']['must_fix'][0]
    done0, total0, _ = drawer_progress(page, screen_of(detail, first['fingerprints'][0])['name'])
    assert done0 == 0 and total0 >= 1
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert tabs.first.inner_text() == f'Must-fix\n1 of {sizes[0]} done'
    assert page.locator('#queue-progress').inner_text() == f'1 of {sum(sizes)} done'
    done1, total1, _ = drawer_progress(page, screen_of(detail, first['fingerprints'][0])['name'])
    assert (done1, total1) == (1, total0)
    assert not any('/' in text for text in tabs.all_inner_texts())
    assert not errors
    context.close()


def test_progress_ignores_which_item_is_open(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=tiers)
    before = page.locator('#queue-progress').inner_text()
    for name in ('quick_wins', 'more', 'must_fix'):
        page.locator(f'[data-fk=queue-{name}]').click()
        assert page.locator('#queue-progress').inner_text() == before
    assert not writes and not errors
    context.close()


def test_empty_tab_says_none_not_zero_of_zero(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=curated)
    assert page.locator('#queue-tabs [role=tab]').all_inner_texts() == ['Must-fix\n0 of 3 done', 'Quick wins\nnone', 'More ideas\nnone']
    context.close()


# ---- D10: "Checking…" only for a live job with real stage data ------------------------------------

def status(s):
    script = (f"global.window={{}};require('./site/dom.js');require('./site/card-status.js');"
              f"console.log(JSON.stringify(window.SC.surveyStatus({s})));")
    done = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.parametrize('survey,label,state', [
    ("{job:{status:'running',stage:'reading'},must_fix:null,readiness:null}", 'Checking…', 'unknown'),
    ("{job:{status:'running'},must_fix:null,readiness:null}", 'In progress', 'unknown'),
    ("{job:{status:'queued'},must_fix:null,readiness:null}", 'Queued', 'unknown'),
    ("{job:{status:'completed'},must_fix:2,readiness:'needs_work',ready_to_share:true}", '2 must-fixes', 'needs_work'),
    ("{job:{status:'completed'},must_fix:1,readiness:'needs_work'}", '1 must-fix', 'needs_work'),
    ("{job:{status:'completed'},must_fix:0,readiness:'ready',ready_to_share:true}", 'Ready to share', 'strong'),
    ("{job:{status:'completed'},must_fix:0,readiness:'ready',ready_to_share:false}", 'No blockers found in what we checked', 'mixed'),
    ("{must_fix:0,readiness:'almost_ready',ready_to_share:false}", 'Ideas to consider', 'mixed'),
    ("{must_fix:0,readiness:'needs_work',ready_to_share:false}", 'Needs work', 'needs_work'),
    ("{must_fix:null,readiness:null,job:null}", 'Not checked yet', 'unknown'),
    ("{must_fix:null,readiness:null,job:{status:'failed'}}", 'Check did not finish', 'unknown'),
])
def test_card_status_never_claims_checking_without_a_live_job(survey, label, state):
    assert status(survey) == {'label': label, 'state': state}


def test_home_card_chip_follows_status(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    base = dict(title='T', version=1, created_at='2026-01-01 00:00:00', signals=None, quality=None, ready_to_share=False,
                must_fix=0, readiness='ready', job={'status': 'completed'})
    page.route('**/api/surveys', lambda route: route.fulfill(json={'surveys': [
        dict(base, id='a'), dict(base, id='b', readiness=None, must_fix=None, job={'status': 'running', 'stage': 'reading'}),
        dict(base, id='c', readiness=None, must_fix=None, job=None)]}))
    page.route('**/api/reader/mode', lambda route: route.fulfill(json={}))
    page.goto(base_url + 'local.html')
    page.locator('a.survey-card').first.wait_for()
    assert page.locator('a.survey-card .chip').all_text_contents() == [
        'No blockers found in what we checked', 'Checking…', 'Not checked yet']
    context.close()
