"""Copy system (brief section 8): the default, visible text of Home, Verdict, Fix and Share never uses
the vocabulary of the machinery. Dialogs and methodology <details> are where that vocabulary lives, so
they are not scanned. Synthetic data only; offline."""
import json
import re

import pytest

from tests.test_issue_loop_ui import open_review
from tests.test_site_e2e import base_url, browser

BANNED = [r'unassessed', r'assessed', r'heuristics?', r'configured', r'thresholds?', r'provisional', r'coverage',
          r'saved assessment', r'captured path', r'readers?', r'snapshots?', r'calibrated', r'verified route',
          r'partial test participant', r'risk checks?', r'rubric',
          r'(?-i:\b[A-PR-Z]\d{1,2}\b)',                     # criterion ids such as B7 (Q4 is a question, not a criterion)
          r'\b\d{1,2}\.\d{1,2}\b(?! ?(?:min|minutes|s|seconds)\b)']   # rubric numbers such as 7.5
BANNED_RE = re.compile('|'.join(f'(?:{pattern})' for pattern in BANNED), re.I)

# Known exceptions that depend on finding copy owned by workstream 1C (backend). Exact visible phrases only;
# this list must shrink to empty once 1C's copy lands. Add nothing here for shell copy: fix the shell.
ALLOWLIST_1C = {
}

VISIBLE_TEXT = """() => {
  const skip = 'dialog, details:not(.signal-more) > :not(summary), script, style';
  const lines = [], walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode());) {
    const el = node.parentElement, text = node.textContent.trim();
    if (text && el && !el.closest(skip) && el.checkVisibility()) lines.push(text);
  }
  return lines;
}"""


def offenders(page):
    found, lines = [], page.evaluate(VISIBLE_TEXT)
    assert len(lines) > 5, 'the scan must actually see the page'
    for line in lines:
        for match in BANNED_RE.finditer(line):
            phrase = match.group(0)
            if not any(allowed in line for allowed in ALLOWLIST_1C.get(phrase.lower(), ())):
                found.append(f'{phrase!r} in {line!r}')
    return found


def test_the_banned_word_check_catches_what_it_should():
    for text in ('Provisional score', '40% coverage', 'saved assessment', 'B7 failed', 'rubric 7.5', 'reader stop code', 'snapshot import'):
        assert BANNED_RE.search(text), text
    for text in ('Q4 asks two things at once', 'About 4½ minutes', 'Q10 · Screen 11', 'Fix before launch', 'about 6.5 minutes'):
        assert not BANNED_RE.search(text), text


@pytest.mark.parametrize('chapter', ['overview', 'improve', 'share'])
@pytest.mark.parametrize('width', [1280, 390])
def test_review_pages_use_plain_words(browser, base_url, chapter, width):
    context, page, detail, writes, errors = open_review(browser, base_url, width=width, chapter=chapter)
    page.locator(f'#chapter-{chapter}').wait_for()
    assert offenders(page) == []
    assert not errors
    context.close()


def test_home_uses_plain_words(browser, base_url):
    page = browser.new_page()
    survey = dict(id='one', title='Holiday snacks', version=1, created_at='2026-01-01 00:00:00', job=None, signals=[],
                  verdict={'kind': 'fix_before_launch', 'tiles': {'fix': 2, 'improve': 1, 'you_check': 3}},
                  tiles={'fix': 2, 'improve': 1, 'you_check': 3}, ready_to_share=False)
    page.route('**/api/surveys', lambda route: route.fulfill(json={'surveys': [survey]}))
    page.goto(base_url + 'local.html')
    page.locator('a.survey-card').wait_for()
    assert offenders(page) == []
    page.close()
