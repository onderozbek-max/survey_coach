"""Sign off and Slack post on intercepted synthetic reviews (workstream 3C). Payload shapes are the 3A contract
(`.superpowers/sdd/impl-3a-backend.md` sections 3 and 4); the server itself is covered by test_signoff / test_slack_post."""
import json

from surveycoach.server.slack import share_payload
from tests.test_issue_loop_ui import open_review

LINK = 'https://app.redjade.net/s/sunrise'
STAMP = '2026-11-05T19:48:26Z'
OPEN_TILES = {'fix': 1, 'improve': 1, 'you_check': 1}


def verdict(ready):
    tiles = {'fix': 0, 'improve': 0, 'you_check': 0} if ready else dict(OPEN_TILES)
    return {'kind': 'ready_for_signoff' if ready else 'almost_ready', 'headline': 'Ready for sign-off' if ready else 'Almost ready: 3 items open',
            'story': 'Members get a welcome.', 'tiles': tiles,
            'time': {'minutes': 3.5, 'label': 'About 3½ minutes', 'state': 'looks_good'}, 'progress': {'done': 2, 'total': 2 if ready else 5}}


def record(ready, name='Priya N', version=2, at=STAMP):
    open_items = [] if ready else [
        {'id': 'a1', 'state': 'fix_before_launch', 'headline': 'Welcome does not say how long it takes', 'location': 'Welcome · Screen 1'},
        {'id': 'a2', 'state': 'worth_improving', 'headline': 'Q4 asks two things at once', 'location': 'Q4 · Screen 5'},
        {'id': 'a3', 'state': 'you_check', 'headline': 'Images load on a phone', 'location': 'Screen 13'}]
    return {'name': name, 'signed_at': at, 'version': version, 'verdict_kind': 'ready_for_signoff' if ready else 'almost_ready',
            'headline': verdict(ready)['headline'], 'counts': {**verdict(ready)['tiles'], 'done': 2, 'total': 5, 'unverified': 1},
            'acknowledged_open': not ready, 'open_items': open_items,
            'you_check': [{'id': 'images', 'fingerprint': 'you-check:images:1', 'title': 'Images load on a phone', 'where': 'Screen 13',
                           'status': 'done', 'reason': None, 'who': name, 'at': at}]}


def state(ready, signed=False, history=(), name='Priya N', version=2):
    rec = record(ready, name, version) if signed else None
    rows = list(history) + ([{'version': version, 'name': name, 'signed_at': STAMP, 'verdict_kind': rec['verdict_kind'],
                              'acknowledged_open': rec['acknowledged_open'], 'latest': True}] if signed else [])
    return {'signed': signed, 'version': version, 'signed_off_by': name if signed else None, 'signed_off_at': STAMP if signed else None,
            'changed_since': False, 'record': rec, 'history': rows}


def earlier(name='Priya N'):
    return {'version': 1, 'name': name, 'signed_at': '2026-11-04T10:00:00Z', 'verdict_kind': 'almost_ready', 'acknowledged_open': True, 'latest': True}


def open_signoff(browser, base_url, ready=True, width=1280, signed=False, history=(), source_url=None, version=2, extra=None):
    """Open the Sign off step with the 3A payloads injected. Returns (context, page, detail, posts, errors); POSTs to
    /signoff are recorded in `posts` and answered by `page.signoff_reply` (a callable returning (status, body))."""
    def prepare(detail):
        detail.update(version=version, versions=[{'version': n, 'created_at': '2026-11-05 18:00:00'} for n in range(1, version + 1)],
                      signoff=state(ready, signed, history, version=version))
        detail['overview']['verdict'] = verdict(ready)
        if ready:                                       # a ready verdict means every item is handled
            for item in detail['overview']['items']:
                item.update(open=False, handled_kind='done')
        detail['snapshot']['source_url'] = source_url or LINK
        if extra:
            extra(detail)
        # The post, the facts and the link are written by the server's own code from this very detail, never typed in
        # by hand: a hand-typed post once named another survey and another verdict than the card beside it (3E).
        detail['share'] = share_payload(detail)

    context, page, detail, writes, errors = open_review(browser, base_url, width=width, chapter='share', prepare=prepare, derived=False)
    posts = []
    page.signoff_reply = lambda body: (201, state(ready, True, history, body['name'], version))

    def handler(route):
        body = route.request.post_data_json
        posts.append(body)
        status, payload = page.signoff_reply(body)
        if status < 300:
            detail['signoff'] = payload
        route.fulfill(status=status, content_type='application/json', body=json.dumps(payload))
    page.route('**/api/surveys/*/versions/*/signoff', handler)
    return context, page, detail, posts, errors
