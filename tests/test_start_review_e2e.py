"""Simple start screen: normal reviews include AI, test-link confirmation is contextual."""
from tests.test_site_e2e import browser
from tests.test_workflow_e2e import studio


def test_start_has_no_checkboxes_and_confirming_test_link_includes_ai(browser, studio):
    page = browser.new_page()
    page.goto(studio + "/local.html")
    assert page.locator("input[type=checkbox]").count() == 0
    page.get_by_label("RedJade preview link").fill("https://sample.redjade.net/test")
    submitted = []
    def intercept(route):
        submitted.append(route.request.post_data_json)
        route.fulfill(status=422, content_type="application/json", body='{"detail":"Synthetic test: no external request made"}')
    page.route("**/api/reader/jobs", intercept)
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Start review", exact=True).click()
    assert not submitted
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Start review", exact=True).click()
    page.get_by_text("Synthetic test: no external request made", exact=True).wait_for()
    assert submitted[0]["ai"] is True and submitted[0]["approval"] is True
    page.close()
