"""The intentionally synthetic Q1 demo showcases the explicit generation contract."""
import json

from surveycoach.demo_export import AI_CACHE, build_demo_data
from tests.test_issue_loop_ui import focus, open_review
from tests.test_site_e2e import base_url, browser

CACHE = AI_CACHE / 'bb2f6eed757f0750e04e879bef7ce59e.json'
ORIGINAL = "Which Member's Mark Boxer Briefs did you buy?\nNavy 3-pack\nBlack 3-pack\nGrey 6-pack"


def q1(findings):
    return next(f for f in findings if f.get('question_id') == 'q1' and f['criterion_id'] == 'B2')


def test_synthetic_q1_fixture_and_export_keep_original_but_label_all_suggestions():
    raw = q1(json.loads(CACHE.read_text())['findings'])
    assert raw['current_text'] == ORIGINAL
    assert len(raw['options']) == 3
    for text in [raw['suggested_text'], *[option['text'] for option in raw['options']]]:
        lines = text.splitlines()
        assert lines[0].startswith('Question: ')
        assert lines[1] == 'Answer choices:'
        assert all(line.startswith('- ') for line in lines[2:])
        assert len(lines[2:]) == 6
    exported = q1(build_demo_data()['surveys'][0]['review']['findings'])
    assert exported['current_text'] == ORIGINAL
    assert exported['suggested_text'] == raw['suggested_text']
    assert exported['options'] == raw['options']
    assert exported['structural'] is True


def test_exported_synthetic_q1_renders_structured_and_preserves_exact_copy(browser, base_url):
    context, page, detail, writes, errors = open_review(browser, base_url)
    finding = q1(detail['review']['findings'])
    focus(page, finding)
    box = page.locator('#coach .fix-paste')
    assert box.get_by_role('heading', name='Question', exact=True).count() == 1
    assert box.get_by_role('list', name='Answer choices').locator('li').all_inner_texts() == [
        'Navy 3-pack', 'Black 3-pack', 'Grey 6-pack', 'Another pack',
        "I did not buy Member's Mark Boxer Briefs", "I don't remember"]
    page.get_by_role('button', name='Copy the new wording', exact=True).click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.startsWith('Copied')")
    assert page.evaluate('navigator.clipboard.readText()') == finding['suggested_text']
    page.locator('#use-change').click()
    page.wait_for_function("document.querySelector('#toast')?.textContent.includes('Added to My changes')")
    assert writes[-1]['picked_text'] == finding['suggested_text']
    assert not errors
    context.close()
