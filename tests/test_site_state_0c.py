"""Workstream 0C state contracts. Synthetic details and intercepted API only: no RedJade, no AI."""
import subprocess
from pathlib import Path

from tests.test_issue_loop_ui import focus, open_review, single_paste
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import go_to

ROOT = Path(__file__).parent.parent
PENDING_KEY = 'surveycoach-pending-job'


def node(script: str):
    """Run model.js in Node with synthetic pages (no browser, no network)."""
    prelude = "const assert=require('node:assert/strict');global.window={SC:{}};require('./site/model.js');const SC=window.SC;"
    done = subprocess.run(['node', '-e', prelude + script], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


QUESTION = ("{id:'p',kind:'question',text:'Raw-only evidence',questions:[{id:'q',kind:'single_choice',"
            "text:'Yes or no?',help_text:'Choose Yes if applicable',options:[{label:'Yes'},{label:'No'}],media:[]}]}")


# ---- Audit 1: a rewrite lands on the exact field it targets -----------------------------------

def test_answer_rewrite_never_touches_stem_or_help():
    node(f'''
    const page = {QUESTION};
    const plan = [{{key:0, from:'Yes', to:'Definitely', page_id:'p', question_id:'q'}}];
    const scoped = SC.scopeFixes(plan, page);
    assert.equal(scoped[0].field, 'option:0');
    const at = field => SC.applyFixes('Yes or no?', scoped, null, {{page_id:'p', question_id:'q', field}});
    assert.equal(at('stem'), 'Yes or no?');
    assert.equal(SC.applyFixes('Choose Yes if applicable', scoped, null, {{page_id:'p', question_id:'q', field:'help'}}), 'Choose Yes if applicable');
    assert.equal(SC.applyFixes('Yes', scoped, null, {{page_id:'p', question_id:'q', field:'option:0'}}), 'Definitely');
    assert.deepEqual([...SC.hitsOn(page, plan)], [0]);
    ''')


def test_stem_rewrite_leaves_matching_answers_alone():
    node(f'''
    const page = {QUESTION};
    const plan = [{{key:3, from:'Yes or no?', to:'Would you buy it?', page_id:'p', question_id:'q'}}];
    assert.equal(SC.scopeFixes(plan, page)[0].field, 'stem');
    const answer = SC.applyFixes('Yes', SC.scopeFixes(plan, page), null, {{page_id:'p', question_id:'q', field:'option:0'}});
    assert.equal(answer, 'Yes');
    ''')


def test_help_rewrite_targets_help_even_when_stem_shares_words():
    node('''
    const page = {id:'p', kind:'question', questions:[{id:'q', kind:'single_choice', text:'Choose a flavor you like',
      help_text:'Choose Yes if applicable', options:[{label:'Yes'}], media:[]}]};
    const plan = [{key:1, from:'Choose Yes if applicable', to:'Pick Yes if it applies', page_id:'p', question_id:'q'}];
    assert.equal(SC.scopeFixes(plan, page)[0].field, 'help');
    ''')


def test_duplicate_or_ambiguous_matches_stay_manual():
    node('''
    const page = {id:'p', kind:'question', questions:[{id:'q', kind:'single_choice', text:'Maybe?',
      help_text:'', options:[{label:'Yes'},{label:'Yes'}], media:[]},
      {id:'r', kind:'single_choice', text:'Shared words here, shared words there', help_text:'', options:[], media:[]}]};
    const duplicate = SC.scopeFixes([{key:0, from:'Yes', to:'Definitely', page_id:'p', question_id:'q'}], page);
    assert.equal(duplicate[0].field, null);
    assert.equal(SC.hitsOn(page, duplicate).size, 0);
    const twice = {id:'p', kind:'question', questions:[{id:'q', kind:'single_choice', text:'Is it fun? Yes or no', help_text:'Say Yes',
      options:[], media:[]}]};
    assert.equal(SC.scopeFixes([{key:0, from:'Yes', to:'Sure', page_id:'p', question_id:'q'}], twice)[0].field, null);
    ''')


def test_copy_and_change_sheet_text_name_only_the_chosen_target(browser, base_url):
    def prepare(detail):
        queued = {fp for group in ('must_fix', 'quick_wins', 'more') for item in detail['plan'][group]
                  if len(item['fingerprints']) == 1 for fp in item['fingerprints']}
        finding = next(f for f in detail['review']['findings'] if f['fingerprint'] in queued and not f.get('absorbed_by')
                       and f.get('question_id') and not f.get('structural'))
        question = next(q for p in detail['snapshot']['pages'] for q in p.get('questions', []) if q['id'] == finding['question_id'])
        question.update(kind='single_choice', text='Yes or no?', help_text='Choose Yes if applicable',
                        options=[{'id': 'yes', 'label': 'Yes'}, {'id': 'no', 'label': 'No'}])
        finding.update(current_text='Yes', suggested_text='Definitely', options=[], edit_kind='replace', action_kind='paste', steps=[])
        detail['_target'] = finding['fingerprint']
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['_target'])
    focus(page, finding)
    page.locator('#coach .use-change').first.click()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.startsWith('My changes (1)')")
    # 2B: the server's My changes copy text replaces the browser's own copy-sheet builder (SC.changeSheetText is gone).
    change = page.evaluate('SC.workspaceDetail.my_changes.copy_all_text')
    sheet = page.evaluate('SC.shareChangesText(SC.workspaceDetail)')
    for text in (sheet, change):
        assert 'Definitely or no?' not in text and 'Choose Definitely' not in text
    assert 'Find: Yes\nReplace with: Definitely' in sheet
    assert 'Definitely' in change
    focus(page, finding)
    page.get_by_role('button', name='With my changes (1)', exact=True).click()
    phone = page.locator('#stage .phone-screen').inner_text()
    assert 'Yes or no?' in phone and 'Choose Yes if applicable' in phone and 'Definitely' in phone
    assert not errors
    context.close()


# ---- Audit 2: hits and "previewed" claims only cover what the phone renders --------------------

def test_raw_only_page_text_is_not_a_visible_change():
    node(f'''
    const page = {QUESTION};
    const plan = [{{key:1, from:'Raw-only evidence', to:'New invisible text', page_id:'p'}}];
    assert.equal(SC.hitsOn(page, plan).size, 0);
    assert.deepEqual(SC.pageTexts(page), ['Yes or no?', 'Choose Yes if applicable', 'Yes', 'No']);
    const intro = {{id:'i', kind:'intro', intro_text:'Welcome in', text:'Hidden duplicate', questions:[]}};
    assert.deepEqual(SC.pageTexts(intro), ['Welcome in']);
    assert.equal(SC.hitsOn(intro, [{{key:2, from:'Hidden duplicate', to:'x', page_id:'i'}}]).size, 0);
    ''')


KINDS = ['single_choice', 'multi_choice', 'dropdown', 'grid_single', 'grid_multi', 'text_short', 'text_long', 'rating', 'slider']


def test_hit_count_equals_visible_replacements_for_every_control_kind(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    result = page.evaluate('''(kinds) => kinds.flatMap(kind => [['Yes', 'Definitely'], ['Strongly', 'Hardly']].map(([from, to]) => {
      const scale = {points:5, low_label:'Strongly', high_label:'Maybe'};
      const page = {id:'p', kind:'question', text:'Raw-only evidence', questions:[{id:'q', kind, text:'Yes or no?',
        help_text:'Choose Yes if applicable', options:[{label:'Yes'},{label:'No'}], rows:['Row'], scale, media:[]}]};
      const plan = [{key:0, from, to, page_id:'p', question_id:'q'}];
      const node = SC.renderPhone({page, entries:[], name:'Q1', index:0},
        {pageId:'p', plan, device:390, total:1, choiceOf:() => undefined, applied:() => false});
      document.body.append(node);
      const text = node.querySelector('.phone-screen').innerText; node.remove();
      return {kind, from, hits:SC.hitsOn(page, plan).size, visible:(text.match(new RegExp(to, 'g')) || []).length,
        stem:text.includes('Yes or no?'), help:text.includes('Choose Yes if applicable')};
    }))''', KINDS)
    for row in result:
        assert row['hits'] == (1 if row['visible'] else 0), row
        assert row['visible'] <= 1, row
        assert row['stem'] and row['help'], row
    shown = {(row['kind'], row['from']) for row in result if row['visible']}
    assert shown == {('single_choice', 'Yes'), ('multi_choice', 'Yes'), ('rating', 'Strongly'), ('slider', 'Strongly')}
    assert not errors
    context.close()


def test_preview_effect_does_not_count_raw_only_text(browser, base_url):
    def prepare(detail):
        finding = next(f for f in detail['review']['findings'] if f.get('question_id') and f.get('suggested_text'))
        page = next(p for p in detail['snapshot']['pages'] if any(q['id'] == finding['question_id'] for q in p.get('questions', [])))
        page['text'] = 'Raw-only stimulus words'
        finding.update(question_id=None, page_id=page['id'], current_text='Raw-only stimulus words',
                       suggested_text='New invisible words', options=[], edit_kind='replace', structural=False, highlight=None)
        for other in detail['review']['findings']:
            if other is not finding:
                other.update(suggested_text=None, options=[])
        detail['_target'] = finding['fingerprint']
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=prepare)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['_target'])
    focus(page, finding)
    page.locator('#coach .use-change').first.click()
    page.wait_for_function("document.querySelector('#tray-toggle').textContent.startsWith('My changes (1)')")
    focus(page, finding)
    page.get_by_role('button', name='With my changes (1)', exact=True).click()
    assert 'New invisible words' not in page.locator('#stage').inner_text()
    assert 'text change' not in page.locator('.preview-effect').inner_text()
    assert not errors
    context.close()


# ---- Audit 3: a late save belongs to the item that started it ------------------------------------

def test_delayed_save_does_not_advance_unrelated_navigation(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = single_paste(detail)[0]
    focus(page, finding)
    held = []
    page.route('**/decisions/**', lambda route: held.append(route))
    page.locator('#use-change').click()
    page.wait_for_function('document.querySelector("#coach .issue-save-status")?.textContent === "Saving…"')
    other = next(e for e in detail['queue']['items'] if finding['fingerprint'] not in e['fingerprints'])     # the user moves to another item
    page.locator('#fix-queue .fix-row', has_text=other['title']).first.click()
    before = page.locator('#coach h3').inner_text()
    assert before != finding['headline'] and before == other['title']
    route = held[0]
    payload = route.request.post_data_json
    detail['decisions'][finding['fingerprint']] = payload
    route.fulfill(json=payload)
    page.wait_for_timeout(400)
    assert page.locator('#coach h3').inner_text() == before                    # the late save did not move the user
    assert page.locator('#fix-queue .fix-row[aria-current=true] .fix-row-title').inner_text() == before
    assert page.evaluate("document.activeElement === document.querySelector('#coach h3')") is False       # nor steal focus
    assert not errors
    context.close()


def test_save_without_navigation_still_advances(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = single_paste(detail)[0]
    focus(page, finding)
    first = page.locator('#coach h3').inner_text()
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert page.locator('#coach h3').inner_text() != first
    assert not errors
    context.close()


# ---- Audit 4: one selected alternative drives coach and phone -----------------------------------

def alternatives(detail):
    finding = next(f for f in detail['review']['findings'] if f.get('question_id') and not f.get('structural')
                   and f.get('current_text') and any(f['fingerprint'] in item['fingerprints'] and len(item['fingerprints']) == 1
                                                     for group in ('must_fix', 'quick_wins', 'more') for item in detail['plan'][group]))
    finding['options'] = [{'label': 'Recommended', 'text': 'SYNTHETIC FIRST WORDING'},
                          {'label': 'Shorter', 'text': 'SYNTHETIC SECOND WORDING'}]
    finding.update(action_kind='paste', steps=[])
    detail['_target'] = finding['fingerprint']


def test_alternative_choice_updates_phone_comparison_and_survives_unrelated_render(browser, base_url):
    """2B: the phone previews only what was added, so the chosen alternative shows on the card first, then (once added) on the phone."""
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=alternatives)
    finding = next(f for f in detail['review']['findings'] if f['fingerprint'] == detail['_target'])
    focus(page, finding)
    stage, card = page.locator('#stage'), page.locator('#coach')
    assert 'SYNTHETIC FIRST WORDING' in card.inner_text() and 'SYNTHETIC SECOND WORDING' not in card.locator('.after-text').inner_text()
    shorter = page.get_by_role('button', name='Shorter', exact=True)
    shorter.click()
    assert 'SYNTHETIC SECOND WORDING' in card.locator('.after-text').inner_text()
    assert shorter.evaluate('e => e === document.activeElement')
    assert 'SYNTHETIC' not in stage.inner_text()                # not added yet: the phone still shows the original
    assert not writes
    page.get_by_text('Preview tools').click()
    page.get_by_role('button', name='Large', exact=True).click()          # unrelated full render
    assert page.get_by_role('button', name='Shorter', exact=True).get_attribute('aria-pressed') == 'true'
    assert 'SYNTHETIC SECOND WORDING' in card.locator('.after-text').inner_text()
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == 'SYNTHETIC SECOND WORDING'
    focus(page, finding)
    page.get_by_role('button', name='With my changes (1)', exact=True).click()
    assert 'SYNTHETIC SECOND WORDING' in stage.inner_text() and 'SYNTHETIC FIRST WORDING' not in stage.inner_text()
    page.get_by_role('button', name='Compare wording', exact=True).click()           # Preview tools stayed open from the Large step
    assert 'SYNTHETIC SECOND WORDING' in page.locator('section[aria-label="Recommended wording"]').inner_text()
    assert not errors
    context.close()


def test_draft_alternative_is_dropped_when_candidates_change(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, prepare=alternatives)
    result = page.evaluate('''(fp) => {
      const f = SC.workspaceDetail.review.findings.find(f => f.fingerprint === fp);
      SC.drafts.set(f, 'v2', '1');
      const kept = SC.drafts.get(f, 'v2');
      const otherVersion = SC.drafts.get(f, 'v3');
      SC.drafts.set(f, 'v2', '1');
      f.options = [{label:'New', text:'a'}, {label:'Newer', text:'b'}];
      return {kept, otherVersion, changed:SC.drafts.get(f, 'v2')};
    }''', detail['_target'])
    assert result == {'kept': '1', 'otherVersion': None, 'changed': None}
    assert not errors
    context.close()


# ---- Audits 5 and 6: opening a review while a job or an uncertain request exists -----------------

def review_server(browser, base_url, detail, metadata, job_status=None, posts=None):
    """Fresh tab whose API is the synthetic detail, with an optional job-poll script."""
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def api(route):
        request = route.request
        url = request.url
        if request.method != 'GET':
            (posts if posts is not None else []).append((request.method, url))
            route.fulfill(json=request.post_data_json or {})
        elif url.endswith('/api/surveys'):
            route.fulfill(json={'surveys': []})
        elif url.endswith('/api/metadata'):
            route.fulfill(json=metadata)
        elif '/api/jobs/' in url:
            detail['job'] = {'id': 'job', 'status': 'failed', 'error': 'Synthetic failure'}
            route.fulfill(json={'status': 'failed', 'error': 'Synthetic failure', 'survey_id': 'synthetic', 'version': 2})
        else:
            route.fulfill(json=detail)
    page.route('**/api/**', api)
    return context, page, errors


def base_detail(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='overview')
    metadata = page.evaluate('({criteria:SURVEYCOACH_DEMO.criteria, dimensions:SURVEYCOACH_DEMO.dimensions, ai_batches:SURVEYCOACH_DEMO.ai_batches})')
    context.close()
    return detail, metadata


def test_failed_running_recheck_still_loads_previous_review_with_a_banner(browser, base_url):
    detail, metadata = base_detail(browser, base_url)
    detail['job'] = {'id': 'job', 'status': 'running', 'stage': 'reading'}
    context, page, errors = review_server(browser, base_url, detail, metadata)
    page.goto(base_url + 'review.html?id=synthetic#overview')
    page.wait_for_function('SC.reviewReady === true', timeout=15000)
    status = page.locator('#review-status')
    assert 'Synthetic failure' in status.inner_text() and 'previous completed review' in status.inner_text()
    assert status.get_attribute('data-tone') == 'error'
    assert len(page.locator('#chapter-overview').inner_text()) > len('Overview') + 20
    assert not errors
    context.close()


def test_failed_known_pending_job_loads_previous_review_with_the_failure(browser, base_url):
    detail, metadata = base_detail(browser, base_url)
    detail['job'] = {'id': 'job', 'status': 'completed'}               # the refetch no longer carries the failure
    context, page, errors = review_server(browser, base_url, detail, metadata)
    page.goto(base_url + 'local.html')
    page.evaluate("key => sessionStorage.setItem(key, JSON.stringify({jobId:'job', started:Date.now()}))", PENDING_KEY)
    page.route('**/api/jobs/job', lambda route: route.fulfill(json={'status': 'failed', 'error': 'Synthetic failure', 'survey_id': 'synthetic', 'version': 2}))
    page.goto(base_url + 'review.html?id=synthetic#overview')
    page.wait_for_function('SC.reviewReady === true', timeout=15000)
    assert 'Synthetic failure' in page.locator('#review-status').inner_text()
    assert not errors
    context.close()


def test_uncertain_marker_opens_existing_review_read_only_and_blocks_submissions(browser, base_url):
    detail, metadata = base_detail(browser, base_url)
    posts = []
    context, page, errors = review_server(browser, base_url, detail, metadata, posts=posts)
    page.goto(base_url + 'local.html')
    page.evaluate("key => sessionStorage.setItem(key, JSON.stringify({submissionPending:true, started:Date.now()}))", PENDING_KEY)
    page.goto(base_url + 'review.html?id=synthetic#overview')
    page.wait_for_function('SC.reviewReady === true', timeout=15000)
    notice = page.locator('#review-status').inner_text()
    assert 'Request status unknown' in notice and 'read' in notice.lower() and 'paused' in notice.lower()
    assert page.locator('#review-status').get_attribute('data-tone') != 'error'
    assert len(page.locator('#chapter-overview').inner_text()) > len('Overview') + 20
    saved = page.evaluate('key => JSON.parse(sessionStorage.getItem(key))', PENDING_KEY)
    assert saved['submissionPending'] is True and set(saved) == {'submissionPending', 'started'}
    go_to(page, 'share')
    for selector in ('#check-again', '#recheck-form button[type=submit]', '#survey-link'):
        assert page.locator(selector).is_disabled(), selector
    go_to(page, 'improve')
    page.wait_for_selector('#coach .card')
    for selector in ('#coach .use-change', '#coach .keep-as-is'):
        assert page.locator(selector).first.is_disabled(), selector
    page.reload()
    page.wait_for_function('SC.reviewReady === true', timeout=15000)
    assert page.evaluate('key => JSON.parse(sessionStorage.getItem(key)).submissionPending', PENDING_KEY) is True
    assert posts == [] and not errors
    context.close()


def test_uncertain_marker_survives_a_running_job_on_the_opened_review(browser, base_url):
    detail, metadata = base_detail(browser, base_url)
    detail['job'] = {'id': 'job', 'status': 'running', 'stage': 'reading'}
    posts = []
    context, page, errors = review_server(browser, base_url, detail, metadata, posts=posts)
    page.goto(base_url + 'local.html')
    page.evaluate("key => sessionStorage.setItem(key, JSON.stringify({submissionPending:true, started:Date.now()}))", PENDING_KEY)
    page.goto(base_url + 'review.html?id=synthetic#overview')
    page.wait_for_function('SC.reviewReady === true', timeout=15000)
    saved = page.evaluate('key => JSON.parse(sessionStorage.getItem(key))', PENDING_KEY)
    assert saved['submissionPending'] is True and 'jobId' not in saved
    assert page.locator('#recheck-form button[type=submit]').is_disabled()
    assert posts == [] and not errors
    context.close()
