"""Browser checks for the static demo in site/. Skipped when Playwright or its Chromium is unavailable."""
import functools
import http.server
import re
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
SITE = Path(__file__).parent.parent / "site"
BAD_TEXT = ("false", "undefined", "null", "NaN", "[object Object]")


@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            chromium = p.chromium.launch()
        except Exception as error:   # browser not installed on this machine
            pytest.skip(f"Chromium unavailable: {error}")
        yield chromium
        chromium.close()


def open_page(browser, base_url, width=1280):
    context = browser.new_context(viewport={"width": width, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(base_url + 'index.html#improve')
    return page, errors


def stray_text(page) -> list[str]:
    lines = [line.strip() for line in page.locator("body").inner_text().splitlines()]
    return [bad for bad in BAD_TEXT if bad in lines] + [line for line in lines if "[object" in line]


def phone_text(page) -> str:
    """What a member would read on the phone: the numbered pins are our annotations, so they are left out."""
    text = page.evaluate("""() => {
        const pins = [...document.querySelectorAll('#stage .phone-screen .phone-marker')];
        pins.forEach((p) => { p.style.display = 'none'; });
        const text = document.querySelector('#stage .phone-screen').innerText;
        pins.forEach((p) => { p.style.display = ''; });
        return text; }""")
    return " ".join(text.split())


def open_screen(page, name: str):
    """Select the exact screen name (so Q1 never matches Q10)."""
    page.locator('#all-screens').click()
    rows = page.locator('#screen-drawer .screen-row')
    row = rows.filter(has=page.locator('strong', has_text=re.compile(rf'^{re.escape(name)}$'))).first
    row.click()


def card_with(page, text: str):
    page.evaluate("""text => {
      const detail = SC.workspaceDetail;
      const f = detail.review.findings.find(f => f.headline.includes(text) && !f.absorbed_by);
      if (f) dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:f.fingerprint}));
    }""", text)
    return page.locator('#coach .card')


def settings(page):
    if page.locator('#phone-settings').get_attribute('aria-expanded') == 'false':
        page.locator('#phone-settings').click()


def demo_finding(page, question_id: str, criterion_id: str) -> dict:
    return page.evaluate("""([q, c]) => window.SURVEYCOACH_DEMO.surveys[0].review.findings
        .find((f) => f.question_id === q && f.criterion_id === c)""", [question_id, criterion_id])


def structural_finding(page) -> dict:
    return page.evaluate("window.SURVEYCOACH_DEMO.surveys[0].review.findings.find((f) => f.structural)")


def open_finding(page, finding: dict):
    page.evaluate("fp => dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:fp}))", finding["fingerprint"])


def test_it_opens_on_the_first_screen_with_a_must_fix_and_that_issue_selected(browser, base_url):
    page, errors = open_page(browser, base_url)
    shown = page.locator("#stage .phone-bar").inner_text().split()[0]
    assert page.locator('#coach .location').inner_text().startswith(shown)
    first = page.locator(".card").first
    assert "Must-fix" in first.inner_text()
    assert page.locator("#stage .phone-marker.on").get_attribute("aria-label").startswith("Must-fix:")
    assert not stray_text(page) and errors == []


def test_the_header_scores_only_what_was_checked_and_says_what_the_ai_did(browser, base_url):
    page, _ = open_page(browser, base_url)
    header = page.locator("#topbar").inner_text()
    review = page.evaluate('SURVEYCOACH_DEMO.surveys[0].review')
    card = review['scorecard']
    assert f"of {card['checked_points']} points checked" in header
    assert 'AI checked 3 of 3 parts' in header and re.search(r'Needs work\. Fix \d+ things first\.', header)
    assert f"{card['unchecked_points']} points still unchecked" in header
    assert all(name in header for name in review['unchecked'])         # the unchecked checks are named, not just counted
    assert "AI check pending" not in header and "wait on the AI step" not in header
    assert "83" not in header and "84" not in header and "63%" not in header   # no 0-100 figure, no bare percentage


@pytest.mark.parametrize("sample", [0, 1])
def test_every_screen_renders_real_text(browser, base_url, sample):
    page, errors = open_page(browser, base_url)
    page.locator('[data-fk="survey-picker"]').select_option(index=sample)
    screens = page.evaluate('SC.workspaceDetail.screens')
    for screen in screens:
        open_screen(page, screen['name'])
        assert "[object" not in phone_text(page) and "undefined" not in phone_text(page)
        assert not stray_text(page)
    assert errors == []


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_page_reflows_without_sideways_scroll(browser, base_url, width):
    page, _ = open_page(browser, base_url, width)
    for name in ("Q1", "Q4", "Q7"):
        open_screen(page, name)
        assert page.evaluate("document.documentElement.scrollWidth") <= width, name


def test_ai_findings_are_marked_and_code_findings_are_not(browser, base_url):
    page, _ = open_page(browser, base_url)
    assert page.locator(".card").first.locator(".pill.ai").inner_text() == "AI suggestion"
    open_screen(page, "Q7")
    assert card_with(page, "desktop word").locator(".pill.ai").count() == 0 and card_with(page, "Image didn't load").locator(".pill.ai").count() == 0


def test_clicking_a_pin_selects_its_card_and_moves_focus_there(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    page.locator('#stage .phone-marker[aria-label*="desktop word"]').click()
    assert "desktop word" in page.locator(".card.selected").inner_text()
    assert page.evaluate("document.activeElement.className") == "headline"
    assert "desktop word" in page.evaluate("document.activeElement.textContent")


def test_focus_stays_on_the_control_the_user_used(browser, base_url):
    page, _ = open_page(browser, base_url)
    settings(page)
    page.get_by_role("button", name="Large text").focus()
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.dataset.fk") == "large"
    page.locator('#all-screens').click()
    page.get_by_role('searchbox').fill('Q2')
    page.locator('#screen-drawer .screen-row').first.click()
    assert page.locator('#coach h3').evaluate('e => e === document.activeElement')


def test_a_code_fix_previews_and_your_original_pick_wins(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    assert "Click" in phone_text(page)
    page.get_by_role("button", name="With changes").click()
    assert "Tap the one you like best." in phone_text(page) and "Click the one" not in phone_text(page)
    card_with(page, "desktop word").get_by_role('button', name='Keep as is', exact=True).click()
    page.get_by_role('button', name='Stakeholder requirement', exact=True).click()
    page.locator('#toast').wait_for()
    open_screen(page, 'Q7')
    assert "Tap the one" not in phone_text(page) and "Click the one you like best." in phone_text(page)


def test_an_ai_finding_offers_three_rewrites_and_the_picked_one_is_previewed_and_copied(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q10")
    finding = demo_finding(page, "q10", "3.4")
    shorter = next(o["text"] for o in finding["options"] if o["label"] == "Shorter")
    card = card_with(page, finding["headline"])
    assert card.locator('.issue-original').count() == 1
    assert card.locator('.alternatives button').count() == 3
    assert card.locator('.alternatives button').all_inner_texts() == [o['label'] for o in finding['options']]
    page.get_by_role("button", name="With changes").click()
    index = next(i for i, o in enumerate(finding['options']) if o['label'] == 'Shorter')
    card.locator('.alternatives button').nth(index).click()
    card.locator('.use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    open_finding(page, finding)
    assert shorter in phone_text(page)
    assert page.evaluate("navigator.clipboard.readText()") == shorter


def test_a_bundle_of_answer_choices_is_copy_only_and_never_drawn_on_the_phone(browser, base_url):
    page, _ = open_page(browser, base_url)
    finding = structural_finding(page)
    open_finding(page, finding)
    before = phone_text(page)
    new_choices = [line for line in finding["options"][0]["text"].splitlines()[1:] if line.strip() and line not in before]
    assert new_choices                                          # the rewrite adds answer choices the phone does not have yet
    page.get_by_role("button", name="With changes").click()
    card = card_with(page, finding["headline"])
    assert card.locator('.suggested').count() > 0
    assert not any(choice in phone_text(page) for choice in new_choices)    # the bundle's choices did not leak into the phone
    card.locator('.use-change').first.click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == finding["options"][0]["text"] and copied.count("\n") >= 2


def test_rewrites_only_replace_real_matching_phone_text(browser, base_url):
    """Every previewable rewrite must actually change its matching phone wording."""
    page, _ = open_page(browser, base_url)
    page.get_by_role('button', name='With changes').click()
    claimed = 0
    findings = page.evaluate('SC.workspaceDetail.review.findings')
    for finding in findings:
        if finding.get('absorbed_by') or finding.get('structural') or not finding.get('current_text'):
            continue
        choices = finding.get('options') or ([{'text':finding['suggested_text']}] if finding.get('suggested_text') else [])
        if not choices:
            continue
        open_finding(page, finding)
        old, rewritten = ' '.join(finding['current_text'].split()), ' '.join(choices[0]['text'].split())
        if rewritten in phone_text(page) and rewritten != old:
            claimed += 1
            if old not in rewritten:
                assert old not in phone_text(page)
    assert claimed >= 3


def test_first_rewrite_wins_when_two_fixes_target_the_same_words(browser, base_url):
    # Use an explicit conflict, not a historical template now correctly suppressed.
    page = browser.new_page()
    def conflict(route):
        response = route.fetch()
        script = response.text() + '''\n{
          const s = SURVEYCOACH_DEMO.surveys[0], p = s.snapshot.pages[0];
          const f = {...s.review.findings[0], page_id:p.id, question_id:null, current_text:p.intro_text, structural:false, source:'auto', options:[], suggested_text:'Complete replacement introduction.'};
          s.review.findings = s.review.findings.filter(existing => existing.page_id !== p.id || existing.question_id);
          s.review.findings.push({...f, headline:'First rewrite for regression'});
          s.review.findings.push({...f, headline:'Conflicting rewrite for regression', suggested_text:'Different complete wording.'});
        }'''
        route.fulfill(response=response, body=script)
    page.route('**/data.js', conflict)
    page.goto(base_url + 'index.html#improve')
    page.get_by_role("button", name="With changes").click()
    open_screen(page, "Welcome")
    assert 'Complete replacement introduction.' in phone_text(page)
    assert 'Different complete wording.' not in phone_text(page)


def test_a_finding_without_a_real_fix_has_no_copy_button(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    assert card_with(page, "Image didn't load").locator('.use-change').count() == 0


def test_original_and_rewrite_make_changed_wording_comparable(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    card = card_with(page, "desktop word")
    assert card.locator('.issue-original blockquote').text_content() == 'Click the one you like best.'
    assert card.locator('.suggested ins').inner_text() == 'Tap'
    assert 'the one you like best.' in card.locator('.suggested').inner_text()


def test_copy_puts_only_the_suggested_text_on_the_clipboard(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    card = card_with(page, "desktop word")
    card.locator('.use-change').first.click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Copied.')")
    assert page.evaluate("navigator.clipboard.readText()") == "Tap the one you like best."
    assert 'Paste it into RedJade.' in page.locator('#toast').inner_text()


def test_what_we_checked_explains_ai_advice_and_unchecked_scope(browser, base_url):
    from tests.test_issue_loop_ui import open_review
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('.checked-summary > summary').click()
    text = page.locator('#review-summary').inner_text()
    assert 'Imported survey screens checked' in text
    assert 'AI advice needs your judgment' in text
    assert 'Unvisited paths are not checked' in text
    assert 'not launch approval' in text
    page.locator('#review-summary > details').first.locator(':scope > summary').click()
    for unchecked in detail['review']['unchecked']:
        assert unchecked in page.locator('#review-summary').inner_text()
    page.locator('[data-chapter=share]').click()
    assert page.locator('#download-summary').get_attribute('href').endswith('/versions/2/summary?download=1')
    assert not writes and not errors
    context.close()


def test_unchecked_points_are_disclosed_as_unknown_not_earned(browser, base_url):
    from tests.test_issue_loop_ui import open_review
    context, page, detail, writes, errors = open_review(browser, base_url)
    page.locator('.checked-summary > summary').click()
    page.get_by_text('Technical details & source evidence', exact=True).click()
    card = detail['review']['scorecard']
    checked = card.get('checked_points', 100 - card['unchecked_points'])
    earned = card['score'] if 'checked_points' in card else card['score'] - card['unchecked_points']
    text = page.locator('#review-summary').inner_text()
    assert f"{int(earned + .5)} of {checked} checked points earned" in text
    assert f"{card['unchecked_points']} points unchecked" in text
    assert not errors
    context.close()


def test_the_clean_sample_has_no_issues_but_does_not_hide_unchecked_points(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.locator('[data-fk="survey-picker"]').select_option(index=1)
    header = page.locator("#topbar").inner_text()
    review = page.evaluate('SURVEYCOACH_DEMO.surveys[1].review')
    card = review['scorecard']
    assert page.locator('.card').count() == 0 and 'Nothing to fix.' in header
    assert 'Ready to launch' not in header
    assert f"of {card['checked_points']} points checked" in header
    assert f"{card['unchecked_points']} points still unchecked" in header
    assert all(name in header for name in review['unchecked'])
    assert 'AI checked 3 of 3 parts' in header    # never an unqualified full ring
    page.locator('#all-screens').click()
    screens = page.locator('#screen-drawer').inner_text()
    assert '0 findings' in page.locator('#screen-drawer').text_content()            # the AI did run, so 'yet' would be wrong
    assert not stray_text(page)


def test_on_a_phone_the_phone_is_the_hero_and_opens_on_the_problem(browser, base_url):
    page, _ = open_page(browser, base_url, 390)
    phone = page.locator("#stage .phone").bounding_box()
    assert phone["y"] < 844 / 2 and phone["y"] < page.locator(".coach").bounding_box()["y"]   # the phone starts in the top half
    assert page.get_by_role("group", name="Device").is_hidden()
    assert page.locator('#queue-tabs [aria-selected=true]').inner_text().startswith('Must-fix')
    pin, screen = page.locator('#stage .phone-marker.on').bounding_box(), page.locator("#stage .phone-screen").bounding_box()
    assert screen["y"] <= pin["y"] and pin["y"] + pin["height"] <= screen["y"] + screen["height"]   # pin 1 is in view


def test_the_ring_never_draws_unchecked_points_as_earned(browser, base_url):
    page, _ = open_page(browser, base_url)
    ring = page.locator(".ring")
    earned, checked = (float(ring.evaluate(f"el => getComputedStyle(el).getPropertyValue('--{v}')").strip().replace("deg", "")) for v in "ek")
    assert earned < checked < 360                       # earned < checked < everything: a grey 'waiting' arc always remains


def test_ai_advice_is_labeled_for_review_and_rule_made_rewrites_are_not(browser, base_url):
    page, _ = open_page(browser, base_url)
    assert page.locator('.card').first.locator('.pill.ai').inner_text() == 'AI suggestion'
    assert page.locator('.card').first.locator('.suggested').count() > 0
    open_screen(page, "Q7")
    assert "AI-written" not in card_with(page, "desktop word").inner_text()           # a rule-made fix is not labeled as AI


def test_a_bundle_shows_its_original_choices_next_to_the_rewrite_so_they_can_be_compared(browser, base_url):
    page, _ = open_page(browser, base_url)
    finding = structural_finding(page)
    open_finding(page, finding)
    original = card_with(page, finding["headline"]).locator(".issue-original").text_content()
    options = page.evaluate("""(id) => window.SURVEYCOACH_DEMO.surveys[0].snapshot.pages
        .flatMap((p) => p.questions || []).find((q) => q.id === id).options.map((o) => o.label)""", finding["question_id"])
    assert options and all(label in original for label in options)


def test_the_title_is_not_pretended_to_be_previewed_and_an_overridden_fix_says_why(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_role("button", name="With changes").click()
    title = page.evaluate("window.SURVEYCOACH_DEMO.surveys[0].review.findings.find((f) => f.criterion_id === '1.1')")
    open_screen(page, "Welcome")                                                         # the title finding is anchored to the first page
    title_card = card_with(page, title["headline"])
    assert title_card.locator('.suggested').count() > 0
    rewrites = title_card.locator('.suggested ins').all_inner_texts()
    assert all(text not in phone_text(page) for text in rewrites)
    assert not page.evaluate('Object.keys(SC.workspaceDetail.decisions).length')


def test_with_fixes_the_true_time_promise_beats_an_ai_rewrite_of_the_same_paragraph(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_role("button", name="With changes").click()
    open_screen(page, "Welcome")
    intro = phone_text(page)
    assert "about 4 minutes" in intro and "about 3 minutes" not in intro               # the code-made fix is a fact, so it goes first
