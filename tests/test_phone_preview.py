"""Quiet phone contracts using shared cleanup fixtures and intercepted synthetic reviews."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_issue_loop_ui import focus, open_review
from tests.test_site_e2e import base_url, browser, open_screen

ROOT = Path(__file__).parent.parent


def test_clean_copy_fixture_parity_and_read_only_projection():
    cases = json.loads((ROOT / 'tests/fixtures/clean_copy_cases.json').read_text())
    script = r'''
    const assert = require('node:assert/strict');
    global.window = {SC:{clip:t=>t}};
    require('./site/model.js');
    const SC = window.SC;
    for (const [raw, expected] of CASES) assert.equal(SC.cleanCopy(raw), expected);
    const page = {id:'p', kind:'intro', text:'Welcome!\n\nNext', intro_text:'Welcome!\nNext'};
    const before = JSON.stringify(page);
    assert.deepEqual(SC.pageTexts(page), ['Welcome!']);   // an intro screen shows one copy (intro_text first)
    const hits = SC.hitsOn(page, [
      {key:1, from:'Next', to:'Not real copy', page_id:'p'},
      {key:2, from:'Welcome!', to:'Hello!', page_id:'p'},
    ]);
    assert.deepEqual([...hits], [2]);
    const survey = {snapshot:{pages:[page]}, review:{findings:[]},
      screens:[{page_id:'p', name:'Canonical welcome', topic:'Not part of the label'}]};
    assert.equal(SC.buildModel(survey).items[0].name, 'Canonical welcome');
    assert.equal(JSON.stringify(page), before);
    '''.replace('CASES', json.dumps(cases))
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('kind', ['intro', 'info'])
def test_welcome_copy_has_one_navigation_control_and_canonical_label(browser, base_url, kind):
    def prepare(detail):
        page = detail['snapshot']['pages'][0]
        page.update(kind=kind, intro_text='Welcome member!\n\nNext', text='Welcome member!\n\nNext')
        detail['screens'][0]['name'] = 'Member welcome'
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    raw = page.evaluate('JSON.stringify(SC.workspaceDetail.snapshot)')
    open_screen(page, 'Member welcome')
    assert page.locator('#stage .phone-bar').inner_text() == f"Member welcome · Screen 1 of {len(detail['screens'])}"
    assert page.locator('#stage .phone-screen .intro, .phone-screen .survey-copy').inner_text() == 'Welcome member!'
    assert page.locator('#stage .phone-screen .next').count() == 1
    assert page.locator('#stage .phone-screen .next').inner_text() in ('Start', 'Next')
    assert page.evaluate('JSON.stringify(SC.workspaceDetail.snapshot)') == raw
    assert not writes and not errors
    context.close()


def test_markers_live_in_right_gutter_and_focus_the_same_card(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = next(f for f in detail['review']['findings'] if 'desktop word' in f['headline'])
    focus(page, finding)
    assert page.locator('#stage .phone-screen p.q-text .pin, .phone-screen p.q-text button').count() == 0
    marker = page.get_by_role('button', name=re.compile(rf"^Worth improving: {re.escape(finding['headline'])}, pin \d+$"))
    assert 'phone-marker' in marker.get_attribute('class')
    assert marker.evaluate("e => e.closest('.phone-marked-block').getBoundingClientRect().right >= e.getBoundingClientRect().right")
    assert marker.evaluate("e => e.getBoundingClientRect().left >= e.closest('.phone-marked-block').querySelector('.phone-block-copy').getBoundingClientRect().right")
    mark = page.locator('#stage .phone-screen mark').first
    assert mark.evaluate("e => getComputedStyle(e).borderBottomWidth") == '2px'
    assert mark.evaluate("e => { const probe=document.createElement('span'); probe.style.backgroundColor='var(--mark)'; e.append(probe); const color=getComputedStyle(probe).backgroundColor; probe.remove(); return getComputedStyle(e).backgroundColor === color; }")
    marker.click()
    assert page.locator('#coach h3.headline').inner_text() == finding['headline']
    assert page.locator('#coach h3.headline').evaluate('e => e === document.activeElement')
    assert not writes and not errors
    context.close()


@pytest.mark.parametrize('kind', ['single_choice', 'multi_choice', 'dropdown'])
def test_answer_additions_are_ghosts_not_stem_rewrites_or_verified_fixes(browser, base_url, kind):
    def prepare(detail):
        finding = next(f for f in detail['review']['findings'] if f.get('question_id'))
        finding.update(edit_kind='add_answer', structural=True, current_text='Keep this entire stem',
                       suggested_text='I did not shop this year', options=[],
                       explanation='Keep the question. Add this answer and make it exclusive.')
        question = next(q for p in detail['snapshot']['pages'] for q in p.get('questions', [])
                        if q['id'] == finding['question_id'])
        question.update(kind=kind, text=finding['current_text'])
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    finding = next(f for f in detail['review']['findings'] if f.get('edit_kind') == 'add_answer')
    raw = page.evaluate('JSON.stringify(SC.workspaceDetail.snapshot)')
    focus(page, finding)
    assert page.locator('li.suggested-option').count() == 0
    # 2B: the preview shows only what was added to My changes, so the toggle is off until then.
    assert page.get_by_role('button', name='With my changes (0)').is_disabled()
    page.get_by_role('button', name='Add to my changes', exact=True).click()
    page.get_by_role('button', name='With my changes (1)').wait_for()
    focus(page, finding)                                   # saving moved on to the next item; come back to this screen
    page.get_by_role('button', name='With my changes (1)').click()
    ghost = page.locator('li.suggested-option')
    assert ghost.locator('span:not(.sr-only)').inner_text() == 'I did not shop this year'
    assert ghost.locator('.sr-only').evaluate('e => getComputedStyle(e).position') == 'absolute'
    assert ghost.locator('.sr-only').text_content() == 'Suggested answer: '
    assert ghost.evaluate('e => getComputedStyle(e).borderStyle') == 'dashed'
    assert 'Keep this entire stem' in page.locator('#stage .phone-screen .q-text').all_inner_texts()
    assert 'I did not shop this year' not in page.locator('#stage .phone-screen .q-text').all_inner_texts()
    # 2C: with only a ghost answer on the screen, the line says exactly that, in plain words.
    effect = page.locator('.preview-effect').inner_text()
    assert effect == 'Suggested answers must be added in RedJade; shown faded here.'
    assert 'verified' not in effect.lower()
    assert page.evaluate('JSON.stringify(SC.workspaceDetail.snapshot)') == raw
    page.get_by_role('button', name='Original', exact=True).click()
    assert ghost.count() == 0
    assert [w['action'] for w in writes] == ['pick']       # only the explicit add was written; previews write nothing
    page.locator('#coach details.more > summary').click()
    assert 'exclusive' in page.locator('#coach details.more').inner_text()
    assert 'Preview does not configure its behavior.' in page.locator('#coach details.more').inner_text()
    page.get_by_role('button', name='Undo', exact=True).first.click()
    focus(page, finding)
    page.get_by_role('button', name='Keep as is…', exact=True).click()
    page.get_by_role('button', name='Intentional', exact=True).click()
    page.get_by_role('button', name='Keep as is', exact=True).click()
    page.locator('.fix-handled').wait_for()
    assert 'Kept as is' in page.locator('.fix-handled').inner_text()
    assert page.get_by_role('button', name='With my changes (0)').is_disabled()      # a kept answer is never previewed
    assert ghost.count() == 0
    assert not errors
    context.close()


@pytest.mark.parametrize('width,large', [(1280, False), (390, True)])
@pytest.mark.parametrize('kind', ['single_choice', 'multi_choice'])
def test_option_control_and_copy_share_a_row(browser, base_url, width, large, kind):
    def prepare(detail):
        question = detail['snapshot']['pages'][1]['questions'][0]
        question.update(kind=kind, options=[{'id': 'o1', 'label': 'Ordinary answer'},
                                           {'id': 'o2', 'label': 'A longer answer that can wrap naturally'}],
                        options_below_fold=1)
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, prepare=prepare)
    open_screen(page, detail['screens'][1]['name'])
    if large:
        open_preview_tools(page)
        page.get_by_role('group', name='Text size').get_by_role('button', name='Large', exact=True).click()
        page.get_by_label('Device size', exact=True).select_option('320')
    rows = page.locator('#stage .opts li:not(.fold):not(.suggested-option)')
    assert rows.count() == 2
    for row in rows.all():
        geometry = row.evaluate('''e => {
          const box = e.getBoundingClientRect(), style = getComputedStyle(e);
          const control = getComputedStyle(e, '::before');
          const copy = e.querySelector('.phone-marked-block').getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(e.querySelector('.phone-block-copy > span'));
          const label = range.getClientRects()[0];
          const top = box.top + parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop);
          return {copyTop:copy.top, top, controlBottom:top + parseFloat(control.marginTop)
            + parseFloat(control.height), labelTop:label.top, right:copy.right, rowRight:box.right};
        }''')
        assert abs(geometry['copyTop'] - geometry['top']) <= 1, geometry
        assert geometry['labelTop'] < geometry['controlBottom'], geometry
        assert geometry['right'] <= geometry['rowRight'], geometry
    fold = page.locator('#stage .opts li.fold')
    assert fold.count() == 1
    assert fold.evaluate("e => getComputedStyle(e, '::before').display") == 'none'
    assert not writes and not errors
    context.close()


def open_preview_tools(page):
    details = page.locator('#stage details.preview-tools')
    if details.get_attribute('open') is None:
        details.locator('summary').click()


def test_device_size_keyboard_path_and_no_horizontal_scroll(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390)
    open_preview_tools(page)
    device = page.get_by_label('Device size', exact=True)
    device.focus()
    device.select_option('320')
    assert page.locator('#stage .phone').evaluate("e => e.style.getPropertyValue('--w')") == '320px'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()
