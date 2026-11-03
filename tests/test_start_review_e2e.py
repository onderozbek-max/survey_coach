"""Start review is one click: AI included, no blocking confirmation dialog."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_start_has_no_checkboxes_or_confirmation_and_includes_ai(browser, studio):
    page = browser.new_page()
    page.goto(studio + "/local.html")
    assert page.locator("input[type=checkbox]").count() == 0
    page.get_by_label("RedJade preview link").fill("https://sample.redjade.net/test")
    submitted = []
    def intercept(route):
        submitted.append(route.request.post_data_json)
        route.fulfill(status=422, content_type="application/json", body='{"detail":"Synthetic test: no external request made"}')
    page.route("**/api/reader/jobs", intercept)
    dialogs = []
    def unexpected_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.dismiss()
    page.on("dialog", unexpected_dialog)
    page.get_by_role("button", name="Start review", exact=True).click()
    page.get_by_text("Synthetic test: no external request made", exact=True).wait_for()
    assert not dialogs
    assert submitted[0]["ai"] is True and submitted[0]["approval"] is True
    page.close()
