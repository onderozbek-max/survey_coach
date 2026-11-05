"""DOM observation facts that identity and requiredness depend on (inline pages, no network)."""
import pytest
from playwright.sync_api import sync_playwright

from surveycoach.reader.extract import extract_page
from surveycoach.reader.observe import OBSERVE


@pytest.fixture(scope="module")
def observe():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        def run(html):
            page.set_content(html)
            return page.evaluate(OBSERVE)
        yield run
        browser.close()


def test_visible_optional_label_is_observed_and_unlabelled_question_stays_unknown(observe):
    observed = observe("""<fieldset><legend>Anything else?</legend><span>Optional</span>
        <textarea></textarea></fieldset>
        <fieldset><legend>Your name?</legend><input type="text"></fieldset><button>Next</button>""")
    optional, plain = (q.required for q in extract_page(observed, 0).questions)
    assert optional is False
    assert plain is None


def test_html_required_attribute_is_observed_as_required(observe):
    observed = observe("<fieldset><legend>Your name?</legend><input type='text' required></fieldset><button>Next</button>")
    assert extract_page(observed, 0).questions[0].required is True


def test_same_label_radios_and_grid_cells_keep_their_identity(observe):
    observed = observe("""<fieldset><legend>Pick</legend>
        <label><input type=radio name=a>Same</label><label><input type=radio name=a>Same</label></fieldset>
        <fieldset><legend>Grid</legend><table><thead><tr><th></th><th>Same</th><th>Same</th></tr></thead><tbody>
        <tr><th>Row</th><td><input type=radio name=r1></td><td><input type=radio name=r1></td></tr>
        <tr><th>Row</th><td><input type=radio name=r2></td><td><input type=radio name=r2></td></tr>
        </tbody></table></fieldset><button>Next</button>""")
    choice, grid = extract_page(observed, 0).questions
    assert [o.label for o in choice.options] == ["Same", "Same"]
    assert [o.label for o in grid.options] == ["Same", "Same"]
    assert grid.rows == ["Row", "Row"]
