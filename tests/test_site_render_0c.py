"""Workstream 0C rendering contracts (D3, D4, D5, D9, D10). Synthetic data and intercepted API only."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_issue_loop_ui import focus, open_review
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import open_how_we_check, go_to

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
    assert page.locator('.round-comparison').count() == 0 and page.locator('#chapter-share').evaluate(STRAY_DIGITS) == []
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


# ---- D5: "Use all N" is gone ---------------------------------------------------------------------
# 2B replaced the Use all button with one action on a grouped card ("Add to my changes" saves every member that has
# wording). Retired: test_use_all_counts_every_applicable_suggestion, test_use_all_hides_when_only_one_finding_has_a_suggestion,
# test_use_all_applies_to_applicable_suggestions_and_says_what_is_left and
# test_use_all_is_disabled_with_a_reason_once_everything_is_chosen. Replacement coverage:
# tests/test_fix_flow_ui.py::test_add_to_my_changes_applies_to_the_whole_group_and_fills_the_tray (one PUT per member,
# one card), tests/test_queue.py::test_action_kind_and_pasteability_are_per_entry (has_paste per entry) and
# tests/test_fix_flow_ui.py::test_with_my_changes_is_disabled_until_there_is_one (a disabled control says why).


# ---- D3: every button has the base component and is not dressed like an input ---------------------

def test_every_secondary_button_declares_the_base_class():
    pattern_ = re.compile(r"""class(?:=|:\s*)["']btn-secondary""")
    offenders = [path.name for path in SOURCES if pattern_.search(path.read_text())]
    assert offenders == [], f'btn-secondary without .btn: {offenders}'


def test_buttons_are_padded_rounded_and_unlike_inputs(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    go_to(page, 'share')
    open_how_we_check(page)
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


# ---- D9: one "N of M done" model for the list, the chips and the drawer ---------------------------

def open_by_state(detail):
    counts = {}
    for entry in detail['queue']['items']:
        if entry['open']:
            counts[entry['state']] = counts.get(entry['state'], 0) + 1
    return counts


def chip_counts(page):
    return {chip.get_attribute('data-state'): int(chip.locator('.filter-count').inner_text())
            for chip in page.locator('.fix-filters .filter-chip').all()}


def test_one_progress_model_everywhere(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    counts = detail['queue']['counts']
    total = counts['total']
    assert page.locator('#queue-progress').inner_text() == f'0 of {total} done'
    chips = chip_counts(page)
    open_now = open_by_state(detail)
    assert chips == {state: open_now.get(state, 0) for state in ('fix_before_launch', 'worth_improving', 'you_check')}
    assert sum(chips.values()) == counts['open'] == total          # the list, the chips and the progress never disagree
    assert page.locator('#fix-queue .fix-row').count() == total
    entry = next(e for e in detail['queue']['items'] if e['action_kind'] == 'paste' and len(e['fingerprints']) == 1)
    focus(page, next(f for f in detail['review']['findings'] if f['fingerprint'] == entry['fingerprints'][0]))
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert page.locator('#queue-progress').inner_text() == f'1 of {total} done'
    after = chip_counts(page)
    assert after[entry['state']] == chips[entry['state']] - 1 and sum(after.values()) == total - 1
    assert page.locator('#fix-queue .fix-row').count() == total      # handled items stay in the list, ticked
    assert not errors
    context.close()


def test_progress_ignores_which_item_is_open(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    before = page.locator('#queue-progress').inner_text()
    rows = page.locator('#fix-queue .fix-row')
    for index in reversed(range(rows.count())):
        rows.nth(index).click()
        assert page.locator('#queue-progress').inner_text() == before
    assert not writes and not errors
    context.close()


def test_a_state_with_nothing_open_shows_a_zero_chip_not_a_missing_one(browser, base_url):
    def prepare(detail):
        detail['review']['findings'] = []         # only the curated You check items and the time item remain
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    chips = chip_counts(page)
    assert set(chips) == {'fix_before_launch', 'worth_improving', 'you_check'}
    assert all(isinstance(value, int) and value >= 0 for value in chips.values())
    assert sum(chips.values()) == detail['queue']['counts']['open']
    assert not errors
    context.close()


# ---- D10: "Checking…" only for a live job with real stage data ------------------------------------

def status(s):
    script = (f"global.window={{}};require('./site/dom.js');require('./site/states.js');require('./site/card-status.js');"
              f"console.log(JSON.stringify(window.SC.surveyStatus({s})));")
    done = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


FIX = "{kind:'fix_before_launch',tiles:{fix:2,improve:0,you_check:0}}"
OUT = {'running': True, 'state': None}


@pytest.mark.parametrize('survey,expected', [
    ("{job:{status:'running',stage:'reading'},verdict:null}", dict(OUT, label='Checking…')),
    ("{job:{status:'running'},verdict:null}", dict(OUT, label='In progress')),
    ("{job:{status:'queued'},verdict:null}", dict(OUT, label='Queued')),
    (f"{{job:{{status:'completed'}},verdict:{FIX}}}", {'label': 'Fix before launch', 'state': 'fix_before_launch'}),
    ("{job:{status:'completed'},verdict:{kind:'ready_for_signoff',tiles:{fix:0,improve:0,you_check:0}}}",
     {'label': 'Ready for sign-off', 'state': 'looks_good'}),
    ("{verdict:{kind:'almost_ready',tiles:{fix:0,improve:3,you_check:1}}}", {'label': 'Almost ready', 'state': 'worth_improving'}),
    ("{verdict:{kind:'almost_ready',tiles:{fix:0,improve:0,you_check:4}}}", {'label': 'Almost ready', 'state': 'you_check'}),
    ("{verdict:null,job:null}", {'label': 'Not checked yet', 'state': None}),
    ("{verdict:null,job:{status:'failed'}}", {'label': 'Check did not finish', 'state': None}),
    (f"{{job:{{status:'failed'}},verdict:{FIX}}}", {'label': 'Fix before launch', 'state': 'fix_before_launch'}),   # the old review still stands
])
def test_card_status_never_claims_checking_without_a_live_job(survey, expected):
    assert status(survey) == expected


def test_home_card_chip_follows_status(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    base = dict(title='T', version=1, created_at='2026-01-01 00:00:00', signals=[], tiles=None, ready_to_share=False,
                verdict=None, job={'status': 'completed'})
    done = {'kind': 'ready_for_signoff', 'tiles': {'fix': 0, 'improve': 0, 'you_check': 0}}
    page.route('**/api/surveys', lambda route: route.fulfill(json={'surveys': [
        dict(base, id='a', verdict=done, tiles=done['tiles']), dict(base, id='b', job={'status': 'running', 'stage': 'reading'}),
        dict(base, id='c', job=None)]}))
    page.route('**/api/reader/mode', lambda route: route.fulfill(json={}))
    page.goto(base_url + 'local.html')
    page.locator('a.survey-card').first.wait_for()
    assert page.locator('a.survey-card .state-chip').all_text_contents() == ['Ready for sign-off', 'Checking…', 'Not checked yet']
    context.close()
