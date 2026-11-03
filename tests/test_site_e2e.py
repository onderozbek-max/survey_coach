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
    page.goto(base_url)
    return page, errors


def stray_text(page) -> list[str]:
    lines = [line.strip() for line in page.locator("body").inner_text().splitlines()]
    return [bad for bad in BAD_TEXT if bad in lines] + [line for line in lines if "[object" in line]


def phone_text(page) -> str:
    """What a member would read on the phone: the numbered pins are our annotations, so they are left out."""
    text = page.evaluate("""() => {
        const pins = [...document.querySelectorAll('.phone-screen .pin')];
        pins.forEach((p) => { p.style.display = 'none'; });
        const text = document.querySelector('.phone-screen').innerText;
        pins.forEach((p) => { p.style.display = ''; });
        return text; }""")
    return " ".join(text.split())


def open_screen(page, name: str):
    """Click a rail row by its exact screen name (so Q1 never matches Q10)."""
    page.locator(".rail-item", has=page.locator("strong", has_text=re.compile(rf"^{name}\b"))).click()


def card_with(page, text: str):
    return page.locator(".card", has=page.locator(".card-head", has_text=text))


def demo_finding(page, question_id: str, criterion_id: str) -> dict:
    return page.evaluate("""([q, c]) => window.SURVEYCOACH_DEMO.surveys[0].review.findings
        .find((f) => f.question_id === q && f.criterion_id === c)""", [question_id, criterion_id])


def structural_finding(page) -> dict:
    return page.evaluate("window.SURVEYCOACH_DEMO.surveys[0].review.findings.find((f) => f.structural)")


def open_finding(page, finding: dict):
    open_screen(page, "Q" + finding["question_id"][1:])      # in these samples question q7 is shown as Q7


def test_it_opens_on_the_first_screen_with_a_must_fix_and_that_issue_selected(browser, base_url):
    page, errors = open_page(browser, base_url)
    shown = page.locator(".phone-bar").inner_text().split()[0]
    assert page.locator(".rail-item.on").inner_text().startswith(shown)
    first = page.locator(".card").first
    assert "Must fix" in first.inner_text()
    assert page.locator(".pin.on").get_attribute("aria-label").startswith("Issue 1")
    assert not stray_text(page) and errors == []


def test_the_header_scores_only_what_was_checked_and_says_what_the_ai_did(browser, base_url):
    page, _ = open_page(browser, base_url)
    header = page.locator("#topbar").inner_text()
    assert "of 96 points checked" in header and "AI checked 3 of 3 parts" in header and re.search(r"Needs work\. Fix \d+ things first\.", header)
    assert "points still unchecked (The right image is there" in header         # the unchecked checks are named, not just counted
    assert "AI check pending" not in header and "wait on the AI step" not in header
    assert "83" not in header and "84" not in header and "63%" not in header   # no 0-100 figure, no bare percentage


@pytest.mark.parametrize("sample", [0, 1])
def test_every_screen_renders_real_text(browser, base_url, sample):
    page, errors = open_page(browser, base_url)
    page.locator("select").select_option(index=sample)
    for i in range(page.locator(".rail-item").count()):
        page.locator(".rail-item").nth(i).click()
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
    assert page.locator(".card").first.locator(".chip.ai").inner_text() == "AI"
    open_screen(page, "Q7")
    assert card_with(page, "desktop word").locator(".chip.ai").count() == 0 and card_with(page, "Image didn't load").locator(".chip.ai").count() == 0


def test_clicking_a_pin_selects_its_card_and_moves_focus_there(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    page.locator('.pin[aria-label*="desktop word"]').click()
    assert "desktop word" in page.locator(".card.selected").inner_text()
    assert page.evaluate("document.activeElement.className") == "card-head"
    assert "desktop word" in page.evaluate("document.activeElement.textContent")


def test_focus_stays_on_the_control_the_user_used(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_role("button", name="Large text").focus()
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.dataset.fk") == "large"
    page.locator(".rail-item").nth(2).focus()
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.dataset.fk") == "rail-2"


def test_a_code_fix_previews_and_your_original_pick_wins(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    assert "Click" in phone_text(page)
    page.get_by_role("button", name="With fixes").click()
    assert "Tap the one you like best." in phone_text(page) and "Click the one" not in phone_text(page)
    assert "Fixed in preview" in card_with(page, "desktop word").inner_text()
    card_with(page, "desktop word").get_by_label("Your original").check()      # the researcher overrules the coach
    assert "Tap the one" not in phone_text(page) and "Click the one you like best." in phone_text(page)


def test_an_ai_finding_offers_three_rewrites_and_the_picked_one_is_previewed_and_copied(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q10")
    finding = demo_finding(page, "q10", "3.4")
    shorter = next(o["text"] for o in finding["options"] if o["label"] == "Shorter")
    card = card_with(page, finding["headline"])
    assert card.locator('input[type="radio"]').count() == 4                           # your original + 3 rewrites
    assert [t.strip().lower() for t in card.locator(".opt-label").all_inner_texts()] == ["your original", "neutral", "shorter", "friendlier"]
    page.get_by_role("button", name="With fixes").click()
    card.get_by_label("Shorter").check()
    assert shorter in phone_text(page)
    card.get_by_role("button", name="Copy suggested text").click()
    assert page.evaluate("navigator.clipboard.readText()") == shorter


def test_a_bundle_of_answer_choices_is_copy_only_and_never_drawn_on_the_phone(browser, base_url):
    page, _ = open_page(browser, base_url)
    finding = structural_finding(page)
    open_finding(page, finding)
    before = phone_text(page)
    new_choices = [line for line in finding["options"][0]["text"].splitlines()[1:] if line.strip() and line not in before]
    assert new_choices                                          # the rewrite adds answer choices the phone does not have yet
    page.get_by_role("button", name="With fixes").click()
    card = card_with(page, finding["headline"])
    assert "Not previewed" in card.inner_text() and "Fixed in preview" not in card.inner_text()
    assert not any(choice in phone_text(page) for choice in new_choices)    # the bundle's choices did not leak into the phone
    card.get_by_role("button", name="Copy suggested text").click()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == finding["options"][0]["text"] and copied.count("\n") >= 2


def test_fixed_in_preview_is_only_ever_said_when_the_phone_really_shows_that_text(browser, base_url):
    """The invariant behind the badge: overlapping fixes must not claim a change the phone did not make."""
    page, _ = open_page(browser, base_url)
    page.get_by_role("button", name="With fixes").click()
    claimed = 0
    for i in range(page.locator(".rail-item").count()):
        page.locator(".rail-item").nth(i).click()
        phone = phone_text(page)
        for card in page.locator(".card").all():
            if "Fixed in preview" not in card.inner_text():
                continue
            claimed += 1
            shown = " ".join(card.locator(".opt.on .opt-text").inner_text().replace(" ... ", " ").split())   # two scale ends are two labels
            assert shown in phone, (page.locator(".rail-item.on").inner_text(), shown)
    assert claimed >= 3


def test_a_fix_that_loses_to_an_earlier_fix_on_the_same_words_says_so(browser, base_url):
    # Use an explicit conflict, not a historical template now correctly suppressed.
    page = browser.new_page()
    def conflict(route):
        response = route.fetch()
        script = response.text() + '''\n{
          const s = SURVEYCOACH_DEMO.surveys[0], p = s.snapshot.pages[0];
          const f = {...s.review.findings[0], page_id:p.id, question_id:null, current_text:p.intro_text, structural:false, source:'auto', options:[], suggested_text:'Complete replacement introduction.'};
          s.review.findings.push({...f, headline:'First rewrite for regression'});
          s.review.findings.push({...f, headline:'Conflicting rewrite for regression', suggested_text:'Different complete wording.'});
        }'''
        route.fulfill(response=response, body=script)
    page.route('**/data.js', conflict)
    page.goto(base_url)
    page.get_by_role("button", name="With fixes").click()
    open_screen(page, "Intro")
    notes = page.locator(".card .note").all_inner_texts()
    assert any("Another fix already changes this text" in n for n in notes)


def test_a_finding_without_a_real_fix_has_no_copy_button(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    assert card_with(page, "Image didn't load").get_by_role("button", name="Copy suggested text").count() == 0


def test_suggestions_mark_only_the_words_that_change(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    card = card_with(page, "desktop word")
    assert card.locator("del").inner_text() == "Click" and card.locator("ins").inner_text() == "Tap"


def test_copy_puts_only_the_suggested_text_on_the_clipboard(browser, base_url):
    page, _ = open_page(browser, base_url)
    open_screen(page, "Q7")
    card = card_with(page, "desktop word")
    card.get_by_role("button", name="Copy suggested text").click()
    status = card.locator("[role=status]")
    page.wait_for_function("(el) => el.textContent.length > 0", arg=status.element_handle())
    assert page.evaluate("navigator.clipboard.readText()") == "Tap the one you like best."
    assert "does not change your survey" in card.inner_text()


def test_the_report_explains_what_the_ai_checked_and_what_it_did_not(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_text("About the AI check").click()
    text = page.locator(".report").inner_text()
    dropped = page.evaluate("window.SURVEYCOACH_DEMO.surveys[0].review.ai.dropped.length")
    merged = page.evaluate("window.SURVEYCOACH_DEMO.surveys[0].review.ai.merged.length")
    assert "gpt-6.1-sol" in text and "Checked 3 of 3 parts" in text and "saved and reviewed by a person" in text
    assert "same model" not in text and "comparable" not in text                       # no false comfort about reproducibility
    assert ("Points are only lost where a finding quotes the survey" in text) == (dropped > 0)
    assert (f"Merged {merged} overlap" in text) == (merged > 0)
    assert "nothing is edited in RedJade" in text
    assert "The right image is there" in text                                          # unchecked checks are open by default


def test_unchecked_areas_are_not_drawn_as_earned(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_text("Score by area").click()
    assert page.locator(".areas i.wait").count() > 0
    assert "waiting" in page.locator(".areas").inner_text() or "Not checked yet" in page.locator(".areas").inner_text()


def test_the_clean_sample_is_ready_but_says_which_checks_have_not_run(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.locator("select").select_option(index=1)
    header = page.locator("#topbar").inner_text()
    assert page.locator(".card").count() == 0 and "Ready to launch, but 2 checks have not run." in header
    assert "of 96 points checked" in header and "AI checked 3 of 3 parts" in header    # never an unqualified full ring
    rail = page.locator(".rail").inner_text()
    assert "Nothing flagged" in rail and "Nothing flagged yet" not in rail            # the AI did run, so 'yet' would be wrong
    assert not stray_text(page)


def test_on_a_phone_the_phone_is_the_hero_and_opens_on_the_problem(browser, base_url):
    page, _ = open_page(browser, base_url, 390)
    phone = page.locator(".phone").bounding_box()
    assert phone["y"] < 844 / 2 and phone["y"] < page.locator(".coach").bounding_box()["y"]   # the phone starts in the top half
    assert page.get_by_role("group", name="Device").is_hidden()
    assert page.locator(".card-head").first.inner_text() in page.locator(".lead").inner_text()   # the top issue, above the phone
    pin, screen = page.locator('.pin[aria-label^="Issue 1"]').bounding_box(), page.locator(".phone-screen").bounding_box()
    assert screen["y"] <= pin["y"] and pin["y"] + pin["height"] <= screen["y"] + screen["height"]   # pin 1 is in view


def test_the_ring_never_draws_unchecked_points_as_earned(browser, base_url):
    page, _ = open_page(browser, base_url)
    ring = page.locator(".ring")
    earned, checked = (float(ring.evaluate(f"el => getComputedStyle(el).getPropertyValue('--{v}')").strip().replace("deg", "")) for v in "ek")
    assert earned < checked < 360                       # earned < checked < everything: a grey 'waiting' arc always remains


def test_who_said_it_comes_first_on_every_ai_card_and_ai_rewrites_are_labeled_for_checking(browser, base_url):
    page, _ = open_page(browser, base_url)
    chips = [t.strip() for t in page.locator(".card").first.locator(".chips span").all_inner_texts()]
    assert chips[1] == "AI"                                                            # right after the number, before the severity
    assert "AI-written. Check it before you use it." in page.locator(".card").first.inner_text()
    open_screen(page, "Q7")
    assert "AI-written" not in card_with(page, "desktop word").inner_text()           # a rule-made fix is not labeled as AI


def test_a_bundle_shows_its_original_choices_next_to_the_rewrite_so_they_can_be_compared(browser, base_url):
    page, _ = open_page(browser, base_url)
    finding = structural_finding(page)
    open_finding(page, finding)
    original = card_with(page, finding["headline"]).locator(".opt", has_text="Your original").inner_text()
    options = page.evaluate("""(id) => window.SURVEYCOACH_DEMO.surveys[0].snapshot.pages
        .flatMap((p) => p.questions || []).find((q) => q.id === id).options.map((o) => o.label)""", finding["question_id"])
    assert options and all(label in original for label in options)


def test_the_title_is_not_pretended_to_be_previewed_and_an_overridden_fix_says_why(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_role("button", name="With fixes").click()
    title = page.evaluate("window.SURVEYCOACH_DEMO.surveys[0].review.findings.find((f) => f.criterion_id === '1.1')")
    open_screen(page, "Intro")                                                         # the title finding is anchored to the first page
    title_card = card_with(page, title["headline"])
    assert "Not previewed" in title_card.inner_text() and "not on a phone screen" in title_card.inner_text()
    assert "Another fix already changes" not in title_card.inner_text()                # nothing overrode it; it is simply not drawn
    for card in page.locator(".card").all():                                           # the chip and the note always agree
        assert ("Not shown in preview" in card.inner_text()) == ("Another fix already changes this text" in card.inner_text())


def test_with_fixes_the_true_time_promise_beats_an_ai_rewrite_of_the_same_paragraph(browser, base_url):
    page, _ = open_page(browser, base_url)
    page.get_by_role("button", name="With fixes").click()
    open_screen(page, "Intro")
    intro = phone_text(page)
    assert "about 4 minutes" in intro and "about 3 minutes" not in intro               # the code-made fix is a fact, so it goes first
