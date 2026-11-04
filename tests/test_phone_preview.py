"""Quiet phone contracts using shared cleanup fixtures and intercepted synthetic reviews."""
import json
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
    assert.deepEqual(SC.pageTexts(page), ['Welcome!', 'Welcome!']);
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
    marker = page.get_by_role('button', name=f"Worth improving: {finding['headline']}", exact=True)
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
    page.get_by_role('button', name='With changes', exact=True).click()
    ghost = page.locator('li.suggested-option')
    assert ghost.locator('span:not(.sr-only)').inner_text() == 'I did not shop this year'
    assert ghost.locator('.sr-only').evaluate('e => getComputedStyle(e).position') == 'absolute'
    assert ghost.locator('.sr-only').text_content() == 'Suggested answer: '
    assert ghost.evaluate('e => getComputedStyle(e).borderStyle') == 'dashed'
    assert 'Keep this entire stem' in page.locator('#stage .phone-screen .q-text').all_inner_texts()
    assert 'I did not shop this year' not in page.locator('#stage .phone-screen .q-text').all_inner_texts()
    assert 'not accepted or saved' in page.locator('.preview-effect').inner_text()
    assert page.evaluate('JSON.stringify(SC.workspaceDetail.snapshot)') == raw
    page.get_by_role('button', name='Original', exact=True).click()
    assert ghost.count() == 0
    assert not writes
    page.locator('#coach details.more > summary').click()
    assert 'exclusive' in page.locator('#coach details.more').inner_text()
    assert 'Preview does not configure its behavior.' in page.locator('#coach details.more').inner_text()
    page.get_by_role('button', name='Keep as is', exact=True).click()
    page.get_by_role('button', name='Intentional for this study', exact=True).click()
    page.locator('#toast').wait_for()
    focus(page, finding)
    page.get_by_role('button', name='With changes', exact=True).click()
    assert ghost.count() == 0
    assert 'accepted risk' in page.locator('.accepted-risk').inner_text()
    assert not errors
    context.close()


def test_phone_settings_keyboard_large_text_and_device_size(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390)
    settings = page.locator('button#phone-settings')
    assert settings.inner_text() == 'Aa'
    assert settings.get_attribute('aria-expanded') == 'false'
    settings.focus()
    page.keyboard.press('Enter')
    assert settings.get_attribute('aria-expanded') == 'true'
    large = page.get_by_role('button', name='Large text', exact=True)
    large.click()
    assert large.get_attribute('aria-pressed') == 'true'
    assert page.locator('.phone.large').count() == 1
    assert large.evaluate('e => e === document.activeElement')
    page.get_by_label('Device size', exact=True).select_option('320')
    assert page.locator('#stage .phone').evaluate("e => e.style.getPropertyValue('--w')") == '320px'
    page.get_by_label('Device size', exact=True).press('Escape')
    assert settings.get_attribute('aria-expanded') == 'false'
    assert settings.evaluate('e => e === document.activeElement')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()
