"""Workstream 2C: the member phone is a faithful, honest frame (D1 stimulus, D8 Optional, scroll, pins, tools).

Offline, synthetic data only. Every browser test intercepts the review API (tests.test_issue_loop_ui.open_review)."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_issue_loop_ui import focus, open_review
from tests.test_site_e2e import base_url, browser, open_screen

ROOT = Path(__file__).parent.parent
IDEA = "Imagine an easy meal at home."
STIMULUS = f"Alright, here's our idea: Member's Mark Quesadilla Meal Kit.\n\n{IDEA} Ready in ten minutes."
BANNED_IN_LINE = ('hypothetical', 'accepted', 'saved', 'verified')
LINE = '#stage .preview-effect'
WITH_CHANGES = re.compile(r'With (my )?changes')


def question_page(detail, index=1):
    return detail['snapshot']['pages'][index]


def with_stimulus(detail, index=1):
    page = question_page(detail, index)
    page['stimulus_text'] = STIMULUS
    page['media'] = []
    for question in page['questions']:
        question['media'] = []
        for option in question.get('options', []):
            option['media'] = None
    return page


def stimulus_finding(detail, index=1):
    """A page-level rewrite of a sentence that lives only in the stimulus (the stem repeats it on purpose)."""
    page = with_stimulus(detail, index)
    page['questions'][0]['text'] = f"{IDEA} Which would you buy?"
    finding = next(f for f in detail['review']['findings'] if f.get('question_id'))
    finding.update(question_id=None, page_id=page['id'], current_text=IDEA, highlight=IDEA, edit_kind='rewrite',
                   suggested_text='Picture an easy meal at home.', options=[], structural=False, element_id=None)
    return finding


def screen_name(detail, index=1):
    return detail['screens'][index]['name']


# ---- D1: stimulus --------------------------------------------------------------------------------

def test_stimulus_is_its_own_field_for_the_scoped_resolver():
    script = r'''
    const assert = require('node:assert/strict');
    global.window = {SC:{clip:t=>t}};
    require('./site/model.js');
    const SC = window.SC;
    const page = {id:'p', kind:'question', text:'raw', stimulus_text:'Imagine a kit. Great idea.', questions:[
      {id:'q', text:'Imagine a kit? Rate it.', kind:'text_short', options:[], rows:[], media:[]}]};
    assert.deepEqual(SC.displayedFields(page).map(f => f.id), ['stimulus', 'stem']);
    assert.equal(SC.displayedFields(page)[0].question_id, undefined);
    const pageFix = {key:1, from:'Imagine a kit.', to:'Picture a kit.', page_id:'p'};
    const stemFix = {key:2, from:'Imagine a kit?', to:'Picture a kit?', page_id:'p', question_id:'q'};
    assert.equal(SC.fixField(pageFix, page), 'stimulus');
    assert.equal(SC.fixField(stemFix, page), 'stem');
    const target = {page_id:'p', field:'stimulus'};
    assert.equal(SC.applyFixes(page.stimulus_text, SC.scopeFixes([pageFix, stemFix], page), null, target), 'Picture a kit. Great idea.');
    assert.equal(SC.applyFixes(page.questions[0].text, SC.scopeFixes([pageFix, stemFix], page), null,
      {page_id:'p', question_id:'q', field:'stem'}), 'Picture a kit? Rate it.');
    assert.deepEqual([...SC.hitsOn(page, [pageFix, stemFix])].sort(), [1, 2]);
    // no stimulus: no field, welcome pages unchanged
    assert.deepEqual(SC.displayedFields({...page, stimulus_text:''}).map(f => f.id), ['stem']);
    assert.deepEqual(SC.displayedFields({id:'w', kind:'intro', text:'Hi', intro_text:'Hi'}).map(f => f.id), ['page']);
    '''
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_stimulus_renders_above_the_question_in_member_type(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=lambda d: with_stimulus(d))
    open_screen(page, screen_name(detail))
    stimulus = page.locator('#stage .phone-screen .stimulus')
    assert stimulus.count() == 1
    assert "Quesadilla Meal Kit" in stimulus.inner_text() and 'Ready in ten minutes' in stimulus.inner_text()
    assert stimulus.evaluate("e => e.getBoundingClientRect().bottom <= document.querySelector('#stage .q-text').getBoundingClientRect().top")
    weights = page.evaluate("""() => [document.querySelector('#stage .stimulus p'), document.querySelector('#stage .q-text')]
      .map(e => Number(getComputedStyle(e).fontWeight))""")
    assert weights[0] < 600 <= weights[1]        # copy reads as copy; the question stays the question
    assert page.locator('#stage .phone-screen .media').count() == 0       # nothing invented when no image was captured
    assert not writes and not errors
    context.close()


def test_a_screen_without_stimulus_or_a_welcome_screen_shows_no_stimulus_block(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    assert page.locator('#stage .phone-screen .stimulus').count() == 0
    open_screen(page, screen_name(detail))
    assert page.locator('#stage .phone-screen .stimulus').count() == 0
    assert not errors
    context.close()


def test_a_rewrite_of_stimulus_wording_lands_only_in_the_stimulus(browser, base_url):
    holder = {}
    context, page, detail, writes, errors = open_review(
        browser, base_url, prepare=lambda d: holder.setdefault('f', stimulus_finding(d)))
    finding = holder['f']
    open_screen(page, screen_name(detail))
    focus(page, finding)
    page.locator('[data-fk=queue-mode-fixes]').click()
    stimulus, stem = page.locator('#stage .stimulus'), page.locator('#stage .q-text').first
    assert 'Picture an easy meal at home.' in stimulus.inner_text()
    assert IDEA not in stimulus.inner_text()
    assert stem.inner_text().startswith(IDEA)           # same sentence in the stem: untouched
    assert not writes and not errors
    context.close()


def test_a_finding_in_the_stimulus_gets_its_pin_and_field_highlight_there(browser, base_url):
    holder = {}
    context, page, detail, writes, errors = open_review(
        browser, base_url, prepare=lambda d: holder.setdefault('f', stimulus_finding(d)))
    open_screen(page, screen_name(detail))
    focus(page, holder['f'])
    block = page.locator('#stage .stimulus .phone-marked-block')
    assert block.count() == 1 and 'field-flagged' in block.get_attribute('class')
    assert page.locator('#stage .page-note').count() == 0        # located, so no floating page note
    assert block.locator('mark').inner_text() == IDEA
    context.close()


# ---- D8: Optional --------------------------------------------------------------------------------

@pytest.mark.parametrize('required,expected', [(False, 1), (True, 0), (None, 0)])
def test_optional_shows_only_when_verified_false(browser, base_url, required, expected):
    def prepare(detail):
        question_page(detail)['questions'][0]['required'] = required
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    open_screen(page, screen_name(detail))
    assert page.locator('#stage .q-optional').count() == expected
    context.close()


def test_a_missing_required_key_shows_nothing(browser, base_url):
    def prepare(detail):
        question_page(detail)['questions'][0].pop('required', None)
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    open_screen(page, screen_name(detail))
    assert page.locator('#stage .q-optional').count() == 0
    context.close()


def test_optional_never_duplicates_a_visible_vendor_label(browser, base_url):
    def prepare(detail):
        question = question_page(detail)['questions'][0]
        question.update(required=False, text='What else should we know? Optional')
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    open_screen(page, screen_name(detail))
    assert page.locator('#stage .q-optional').count() == 0
    visible = page.locator('#stage .phone-screen').inner_text()
    assert len(re.findall(r'\bOptional\b', visible)) == 1
    context.close()


# ---- device frame ---------------------------------------------------------------------------------

def long_list(detail):
    question = question_page(detail, 6)['questions'][0]
    question['options'] = [{'label': f'Answer number {i} with a reasonably long label'} for i in range(1, 11)]
    question.update(kind='multi_choice', options_below_fold=0)


def test_the_frame_has_status_bar_rounded_screen_and_a_realistic_shape(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=1440)
    phone = page.locator('#stage .phone')
    assert phone.locator('.phone-status').count() == 1
    assert phone.locator('.phone-status').get_attribute('aria-hidden') == 'true'
    box = phone.bounding_box()
    assert 1.5 <= box['height'] / box['width'] <= 2.2, box          # a phone, not a landscape card (844 tall when the window allows)
    assert float(phone.evaluate("e => parseFloat(getComputedStyle(e).borderTopLeftRadius)")) >= 28
    assert not errors
    context.close()


@pytest.mark.parametrize('width', [1440, 1024, 390])
def test_the_scroll_region_is_keyboard_reachable_and_cues_overflow(browser, base_url, width):
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, prepare=long_list)
    open_screen(page, screen_name(detail, 6))
    region = page.locator('#stage .phone-screen')
    assert region.get_attribute('tabindex') == '0'
    assert region.get_attribute('role') == 'region'
    assert 'scroll' in region.get_attribute('aria-label').lower()
    assert region.evaluate('e => e.scrollHeight > e.clientHeight')
    cue = page.locator('#stage .phone-scroll-cue')
    page.wait_for_function("document.querySelector('#stage .phone-viewport').dataset.more === 'true'")
    assert cue.is_visible() and 'more' in cue.inner_text().lower()
    region.focus()
    page.keyboard.press('End')
    page.wait_for_function("document.querySelector('#stage .phone-viewport').dataset.more === 'false'")
    assert not cue.is_visible()
    last = page.locator('#stage .opts li').last.bounding_box()
    nxt = page.locator('#stage .phone-screen .next').bounding_box()
    assert last['y'] + last['height'] <= nxt['y'] + 1, (last, nxt)      # the last answer is not clipped by Next
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors
    context.close()


def test_the_next_button_stays_pinned_to_the_bottom_while_the_list_scrolls(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=1440, prepare=long_list)
    open_screen(page, screen_name(detail, 6))
    region, nxt = page.locator('#stage .phone-screen'), page.locator('#stage .phone-screen .next')
    inside = "(r, n) => n.getBoundingClientRect().bottom <= r.getBoundingClientRect().bottom + 1 && n.getBoundingClientRect().top >= r.getBoundingClientRect().top"
    assert page.evaluate(f"([r, n]) => ({inside})(document.querySelector(r), document.querySelector(n))",
                         ['#stage .phone-screen', '#stage .phone-screen .next'])
    region.evaluate('e => { e.scrollTop = 40; }')
    assert nxt.evaluate(f"(n) => ({inside})(n.closest('.phone-screen'), n)")
    context.close()


@pytest.mark.parametrize('width', [1440, 1024, 390])
@pytest.mark.parametrize('screen', ['welcome', 'question'])
def test_no_horizontal_scroll_at_any_width(browser, base_url, width, screen):
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, prepare=long_list)
    if screen == 'question':
        open_screen(page, screen_name(detail, 6))
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.evaluate("[...document.querySelectorAll('#stage .phone')].every(p => p.getBoundingClientRect().right <= innerWidth + 1)")
    context.close()


# ---- pins -----------------------------------------------------------------------------------------

def test_pins_are_numbered_like_the_card_with_a_text_alternative(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    pins = page.locator('#stage .phone-marker')
    assert pins.count() >= 1
    for index in range(pins.count()):
        pin = pins.nth(index)
        label = pin.get_attribute('aria-label')
        number = pin.locator('.pin-number').inner_text()
        assert number.isdigit() and f'pin {number}' in label.lower(), label
        assert label.startswith(('Must-fix:', 'Worth improving:'))      # severity is spoken, not only coloured
    numbers = sorted(int(pins.nth(i).locator('.pin-number').inner_text()) for i in range(pins.count()))
    assert numbers == list(range(1, len(numbers) + 1))      # the card numbers, one each, starting at 1
    context.close()


def test_the_affected_field_is_tinted_and_outlined_not_the_whole_question(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    block = page.locator('#stage .field-flagged').first
    style = block.evaluate("e => ({bg:getComputedStyle(e).backgroundColor, outline:getComputedStyle(e).outlineStyle + getComputedStyle(e).borderStyle})")
    assert style['bg'] != 'rgba(0, 0, 0, 0)' and ('solid' in style['outline'] or 'dashed' in style['outline'])
    question = page.locator('#stage .q.flagged').first
    assert question.evaluate("e => getComputedStyle(e).backgroundColor") == 'rgba(0, 0, 0, 0)'    # no pink wash
    # state is never by colour alone: the severity differs by outline style and the pin text
    assert block.get_attribute('data-severity') in ('must_fix', 'worth_improving')
    context.close()


# ---- Text size control ----------------------------------------------------------------------------

def open_tools(page):
    details = page.locator('#stage details.preview-tools')
    if details.get_attribute('open') is None:
        details.locator('summary').click()


def test_aa_is_gone_and_text_size_lives_inside_preview_tools_with_a_keyboard_path(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390)
    assert page.locator('#phone-settings').count() == 0
    assert 'Aa' not in page.locator('#stage').inner_text().split()
    open_tools(page)
    group = page.get_by_role('group', name='Text size')
    buttons = group.get_by_role('button')
    assert [b.inner_text() for b in buttons.all()] == ['Small', 'Default', 'Large']
    assert buttons.nth(1).get_attribute('aria-pressed') == 'true'
    buttons.nth(2).focus()
    page.keyboard.press('Enter')
    assert buttons.nth(2).get_attribute('aria-pressed') == 'true'
    assert page.locator('#stage .phone.size-large').count() == 1
    assert page.evaluate("document.activeElement.dataset.fk") == 'text-size-large'      # focus survives the redraw
    big = page.locator('#stage .q-text').first.evaluate('e => parseFloat(getComputedStyle(e).fontSize)')
    page.locator('[data-fk=text-size-small]').focus()
    page.keyboard.press('Space')
    small = page.locator('#stage .q-text').first.evaluate('e => parseFloat(getComputedStyle(e).fontSize)')
    assert small < big
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not writes and not errors
    context.close()


def test_text_size_is_remembered_for_the_session(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    open_tools(page)
    page.locator('[data-fk=text-size-large]').click()
    assert page.evaluate("sessionStorage.getItem('surveycoach.phoneTextSize')") == 'large'
    
    page.reload()
    page.wait_for_selector('#stage .phone')
    assert page.locator('#stage .phone.size-large').count() == 1
    context.close()


# ---- Preview line and timeline ----------------------------------------------------------------------

def test_the_preview_line_says_there_is_nothing_to_preview(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    assert page.locator(LINE).inner_text() == 'No wording changes to preview on this screen.'
    context.close()


def test_the_preview_line_counts_your_changes_honestly(browser, base_url):
    holder = {}
    context, page, detail, writes, errors = open_review(
        browser, base_url, prepare=lambda d: holder.setdefault('f', stimulus_finding(d)))
    open_screen(page, screen_name(detail))
    focus(page, holder['f'])
    page.locator('[data-fk=queue-mode-fixes]').click()
    text = page.locator(LINE).inner_text()
    assert text == 'Showing your 1 change. RedJade is only changed when you edit it there.'
    assert not any(word in text.lower() for word in BANNED_IN_LINE)
    context.close()


@pytest.mark.parametrize('kind', ['single_choice', 'dropdown'])
def test_a_page_with_only_a_ghost_answer_says_so(browser, base_url, kind):
    def prepare(detail):
        finding = next(f for f in detail['review']['findings'] if f.get('question_id'))
        finding.update(edit_kind='add_answer', structural=True, current_text='Keep this entire stem',
                       suggested_text='I did not shop this year', options=[])
        next(q for p in detail['snapshot']['pages'] for q in p.get('questions', [])
             if q['id'] == finding['question_id']).update(kind=kind, text='Keep this entire stem')
        holder['f'] = finding
    holder = {}
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    focus(page, holder['f'])
    page.locator('[data-fk=queue-mode-fixes]').click()
    assert page.locator('li.suggested-option').count() == 1
    text = page.locator(LINE).inner_text()
    assert text == 'Suggested answers must be added in RedJade; shown faded here.'
    assert not any(word in text.lower() for word in BANNED_IN_LINE)
    context.close()


def test_the_timeline_is_a_neutral_bar_with_a_marker_and_plain_words(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    line = page.locator('#stage .timing p').first.inner_text()
    assert re.fullmatch(r'~\d+:\d\d in · \d+ min total', line), line
    assert 'estimate' not in page.locator('#stage .timing').inner_text().lower()      # the caveat lives in the tooltip
    assert page.locator('#stage .timing [title*="stimate"]').count() == 1
    bar = page.locator('#stage .timebar')
    assert bar.locator('i').count() == 1 and bar.get_attribute('aria-hidden') == 'true'
    colours = page.evaluate("""() => { const bar = document.querySelector('#stage .timebar');
      return [getComputedStyle(bar, '::before').backgroundColor, getComputedStyle(bar, '::after').backgroundColor]; }""")
    assert colours[0] == colours[1] or 'rgba(0, 0, 0, 0)' in colours       # no blue/yellow/red zones
    context.close()


def test_the_phone_modules_stay_small_and_token_only():
    for name in ('phone.js', 'phone-frame.js', 'phone-tools.js', 'phone-frame.css', 'phone-tools.css'):
        text = (ROOT / 'site' / name).read_text()
        assert text.count('\n') < 600, name
        assert not re.search(r'gradient|backdrop-filter', text), name
        if name.endswith('.css'):
            assert not re.search(r'#[0-9a-fA-F]{3,8}\b|rgba?\(', text.replace('rgba(0, 0, 0, 0)', '')), name
        else:
            assert 'style.color' not in text and 'style.background' not in text, name
