"""Real engine grouped findings, distinct questions on the same captured screen."""
from copy import deepcopy
from scripts.capture_screens import pattern_snapshot
from surveycoach.snapshot import SurveySnapshot
from surveycoach.review import run_review
from surveycoach.server.present import enrich
from surveycoach.server.report import summary_packet
from surveycoach.labels import finding_label
from surveycoach.rubric import load_rubric
from tests.test_issue_loop_ui import open_review, focus
from tests.test_site_e2e import base_url, browser


def test_exact_question_labels_topics_and_share_match_download(browser, base_url):
    snap = pattern_snapshot()
    pages = snap['pages']
    questions = [deepcopy(p['questions'][0]) for p in pages[1:-1]]
    questions[1]['label'] = 'Research B'
    questions.insert(1, {'id':'info','kind':'info','text':'A little context'})
    pages[1]['questions'] = questions
    snap['pages'] = [pages[0], pages[1], pages[-1]]
    snapshot = SurveySnapshot.model_validate(snap)
    assessed = run_review(snapshot, provider=None)
    review = assessed.model_dump(mode='json')
    for encoded, finding in zip(review['findings'], assessed.findings):
        encoded['fingerprint'] = finding.fingerprint
    detail = enrich({'id':'synthetic','version':2,'title':snapshot.title,
                     'snapshot':snapshot.model_dump(mode='json'), 'review':review,
                     'decisions':{}, 'versions':[]}, load_rubric())
    detail['timeline'] = [{'seconds':0} for _ in snap['pages']]
    detail['total_seconds'] = 60
    def prepare(d):
        d.clear(); d.update(deepcopy(detail))
    context, page, returned, writes, errors = open_review(browser, base_url, prepare=prepare)
    group = next(i for i in detail['plan']['quick_wins'] if i['count'] == 3)
    members = [f for f in detail['review']['findings'] if f['fingerprint'] in group['fingerprints']]
    focus(page, members[0])
    for f in members:
        label = finding_label(f, detail['screens'])
        row = page.locator(f'.pattern-row[data-fingerprint="{f["fingerprint"]}"]')
        assert row.locator('.location').inner_text().startswith(label)
        q = next(q for q in questions if q['id'] == f['question_id'])
        assert ' '.join(q['text'].split()[:5]) in row.locator('.location').inner_text()
    page.locator('#use-all').click()
    page.locator('#undo').wait_for()
    page.locator('[data-chapter=share]').click()
    text = page.evaluate('SC.shareChangesText(SC.workspaceDetail)')
    packet = summary_packet(page.evaluate('SC.workspaceDetail'), download=True)
    for f in members:
        label = finding_label(f, detail['screens'])
        assert label in text and label in packet
        assert label in page.locator('#change-list').inner_text()
    assert not errors
    context.close()
