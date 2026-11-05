"""Cross-feature regressions. Synthetic intercepted API and disposable localhost only."""
import pytest
from tests.test_issue_loop_ui import open_review, focus
from tests.test_site_e2e import base_url, browser
from tests.site_helpers import open_how_we_check, go_to
from tests.test_workflow_e2e import studio


def keep(page):
    page.locator('#keep-as-is').click()
    page.get_by_role('button', name='Stakeholder requirement', exact=True).click()
    page.locator('#undo').wait_for()


@pytest.mark.parametrize('removed', [False, True, 'in-range'])
def test_undo_resolves_refetched_fingerprint_not_array_index(browser, base_url, removed):
    context, page, detail, writes, errors = open_review(browser, base_url)
    target = detail['review']['findings'][-1]
    focus(page, target)
    keep(page)
    page.evaluate("""removed => {
      const d = structuredClone(SC.workspaceDetail);
      if (removed === true) {
        const fp = d.review.findings.pop().fingerprint;
        for (const name of ['must_fix','quick_wins','more'])
          d.plan[name] = d.plan[name].filter(i => !i.fingerprints.includes(fp));
      } else if (removed === 'in-range') d.review.findings.reverse();
      else d.review.findings.splice(0,2);
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:d}));
    }""", removed)
    page.locator('#undo').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('restored')")
    assert len(writes) == (1 if removed is True else 2)
    if removed is not True:
        decisions = page.evaluate('SC.workspaceDetail.decisions')
        assert decisions[target['fingerprint']]['action'] == 'open'
        assert set(decisions) == {target['fingerprint']}
        assert page.locator('#coach .decision-content').get_attribute('data-fingerprint') == target['fingerprint']
        assert page.locator('#coach-h').evaluate('el => el === document.activeElement')
    assert not errors
    context.close()


def test_preview_choice_survives_reordering_only_on_its_fingerprint(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    target = detail['review']['findings'][-1]
    focus(page, target)
    keep(page)
    page.evaluate("""() => {
      const d = structuredClone(SC.workspaceDetail);
      d.review.findings.reverse();
      dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail:d}));
    }""")
    # Saved keep must not become a default rewrite after its index changes.
    page.locator('[data-fk=queue-mode-fixes]').click()
    focus(page, target)
    assert page.locator('#stage .phone-screen').inner_text().find(target['current_text']) >= 0
    assert not errors
    context.close()


def test_keyboard_undo_returns_to_restored_single_card(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    fp = page.locator('.decision-content').get_attribute('data-fingerprint')
    page.locator('#keep-as-is').focus()
    page.keyboard.press('Enter')
    page.get_by_role('button', name='Stakeholder requirement', exact=True).focus()
    page.keyboard.press('Enter')
    page.locator('#undo').wait_for()
    page.locator('#undo').focus()
    page.keyboard.press('Enter')
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Previous decisions restored')")
    assert page.locator('#coach-h').evaluate('el => el === document.activeElement')
    assert page.locator('.decision-content').get_attribute('data-fingerprint') == fp
    page.locator('#skip').focus()
    page.keyboard.press('Enter')
    page.locator('[data-chapter=share]').focus()
    page.keyboard.press('Enter')
    assert page.locator('#share-h').evaluate('el => el === document.activeElement')
    assert not errors
    context.close()


@pytest.mark.parametrize('motion', ['reduce', 'no-preference'])
@pytest.mark.parametrize('large', [False, True])
def test_mobile_tab_focus_is_not_covered_by_actions(browser, base_url, motion, large):
    context, page, detail, writes, errors = open_review(browser, base_url, width=390, chapter='overview')
    page.set_viewport_size({'width':390,'height':844})
    page.emulate_media(reduced_motion=motion)
    if large:
        page.add_style_tag(content='html {font-size:150%} #chapter-overview button {font-size:1.3rem}')
    page.locator('#start-improving').focus()
    for direction in ['Tab', 'Shift+Tab']:
        for _ in range(28):
            page.keyboard.press(direction)
            assert page.evaluate("""() => {
              const el = document.activeElement;
              if (!el.closest('#chapter-overview')) return true;
              const r = el.getBoundingClientRect();
              const x = Math.min(innerWidth-1, Math.max(0, r.x+r.width/2));
              const y = Math.min(innerHeight-1, Math.max(0, r.y+r.height/2));
              const hit = document.elementFromPoint(x,y);
              return r.top >= 0 && r.bottom <= innerHeight && (el.contains(hit) || hit?.contains(el));
            }"""), page.evaluate('document.activeElement.outerHTML')
    assert not errors
    context.close()


@pytest.mark.parametrize('route', ['hash', 'back', 'forward'])
def test_about_closes_on_real_chapter_change(browser, base_url, route):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share')
    if route == 'forward':
        page.evaluate("SC.goChapter('overview')")
        page.go_back()
    open_how_we_check(page)
    if route == 'hash':
        page.evaluate("location.hash='overview'")
    elif route == 'back':
        page.evaluate("SC.goChapter('overview')")
    else:
        page.go_forward()
    page.wait_for_function("SC.currentChapter() === 'overview'")
    assert not page.locator('#about-review-dialog').evaluate('el => el.open')
    page.wait_for_function("document.activeElement.id === 'overview-h'")
    assert not errors
    context.close()


def test_about_escape_returns_connected_trigger_deterministically(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url, chapter='share')
    for _ in range(3):
        open_how_we_check(page)
        page.keyboard.press('Escape')
        page.wait_for_function("!document.querySelector('#about-review-dialog').open")
        page.wait_for_function("document.activeElement.isConnected && document.activeElement.id === 'header-menu-button'")
    assert not errors
    context.close()


@pytest.mark.parametrize('kind', ['missing', 'network', 'metadata', 'failed', 'queued'])
def test_default_overview_feedback_is_visible(browser, base_url, kind):
    context = browser.new_context()
    page = context.new_page()
    def api(route):
        if kind == 'network':
            route.abort(); return
        if kind == 'metadata' and route.request.url.endswith('/api/metadata'):
            route.fulfill(status=503, json={'detail':'Metadata unavailable'}); return
        if '/api/jobs/' in route.request.url:
            route.fulfill(json={'id':'job','status':'queued'}); return
        if kind in ['missing', 'metadata']:
            if kind == 'missing':
                route.fulfill(status=404, json={'detail':'Survey not found'}); return
            # Metadata errors arise after the shell has loaded a review.
        route.fulfill(json={'id':'synthetic','title':'Synthetic','version':1,
                            'job':{'id':'job','status':'queued' if kind == 'queued' else 'failed','error':'Synthetic failure'},
                            'review':None})
    page.route('**/api/**', api)
    page.goto(base_url + 'review.html?id=synthetic#overview')
    status = page.locator('#review-status')
    page.wait_for_function("document.querySelector('#review-status').textContent.length > 0")
    assert status.is_visible()
    assert page.get_by_role('link', name='My surveys', exact=True).first.is_visible()
    context.close()


def test_decision_refresh_overview_matches_authoritative_api(browser, studio):
    page = browser.new_page()
    page.goto(studio + '/local.html')
    page.locator('#sample-start').click()
    page.wait_for_url('**/review.html?**')
    page.locator('#overview-h').wait_for()
    before = page.locator('#overview-h').inner_text()
    page.locator('#start-improving').click()
    keep(page)
    go_to(page, 'overview')
    page.wait_for_function("before => document.querySelector('#overview-h').textContent !== before", arg=before)
    authoritative = page.evaluate("fetch('/api/surveys/'+SC.workspaceDetail.id).then(r=>r.json())")
    assert page.locator('#overview-h').inner_text() == authoritative['overview']['headline']
    page.locator('#undo').click()
    page.wait_for_function("before => document.querySelector('#overview-h').textContent === before", arg=before)
    page.close()
