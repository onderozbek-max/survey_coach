"""Helpers for the Verdict journey, setup and version-delta UI tests (3B). Synthetic detail, intercepted writes, no live calls."""
from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from tests.test_issue_loop_ui import open_review


def add_journey(detail):
    """What a regenerated site/data.js carries: the journey and its sections, built by the same code as the server."""
    detail["presentation"] = enrich(detail, load_rubric())["presentation"]


def add_setup(detail, *, confirmed=False, kind="services_concept", reward=None):
    """What the repository adds to every detail: the type detection (with its confirmed flag) and the reward answer."""
    detail["survey_type_detection"] = {"type": kind, "confidence": 0.62, "label": "medium", "reasons": ["concept copy before intent questions"],
                                       "confirmed": confirmed}
    detail["reward"] = reward or {"has_reward": None, "text": ""}
    if confirmed:
        detail["survey_type"] = kind


def open_verdict(browser, base_url, width=1280, prepare=None, derived=True):
    """The Verdict of the synthetic survey with a journey. `prepare(detail)` runs after the journey is added."""
    def both(detail):
        add_journey(detail)
        if prepare:
            prepare(detail)
    return open_review(browser, base_url, width=width, chapter="overview", prepare=both, derived=derived)


def delta(counts=(4, 1, 0, 1)):
    """A version_delta payload shaped exactly like 3A's, with before/after on fixed items."""
    fixed, still, new, uncertain = counts
    item = lambda i, resolution, **extra: {"fingerprint": f"f{i}", "criterion_id": "3.1", "headline": f"Item {i}", "location": f"Q{i} · Screen {i + 1}",
                                          "resolution": resolution, **extra}
    return {"from_version": 1, "to_version": 2, "counts": {"fixed": fixed, "still": still, "new": new, "uncertain": uncertain},
            "summary": f"{fixed} fixed · {still} still open · {new} new · {uncertain} couldn't compare",
            "caveat": "Fixed = no longer flagged by our checks.",
            "fixed": [item(i, "No longer flagged", before=f"Before {i}", after=f"After {i}", by_rewrite=i == 0) for i in range(fixed)],
            "still": [item(10 + i, "Still flagged") for i in range(still)],
            "new": [item(20 + i, "New") for i in range(new)],
            "uncertain": [item(30 + i, "Not verified: changed context") for i in range(uncertain)]}


def open_flow_verdict(browser, flow, width=1440, height=900):
    """The Verdict of the real synthetic concept survey served by a localhost server (see fixflow_helpers.flow). (context, page, errors)."""
    base, survey_id = flow
    context = browser.new_context(viewport={"width": width, "height": height}, permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{base}/review.html?id={survey_id}#overview")
    page.wait_for_function("SC.reviewReady === true", timeout=30000)
    page.locator("#journey").wait_for()
    return context, page, errors


def confirm_type_on_patch(page, detail, writes):
    """The stand-in server for the type override: store the type, flag the detection confirmed (as the real PATCH does), record the write."""
    def handle(route):
        if route.request.method != "PATCH" or not route.request.url.endswith("/api/surveys/synthetic"):
            return route.fallback()
        payload = route.request.post_data_json
        writes.append(payload)
        detail.update(payload)
        if "survey_type" in payload:
            detail["survey_type_detection"]["confirmed"] = True
        return route.fulfill(json=payload)
    page.route("**/api/surveys/synthetic", handle)


def reward_endpoint(page, detail, writes, fail_times=0):
    """PUT /api/surveys/{id}/reward: store the answer like the real endpoint, record each write; the first `fail_times` calls answer 503."""
    calls = {"n": 0}

    def handle(route):
        if route.request.method != "PUT":
            return route.fallback()
        calls["n"] += 1
        if calls["n"] <= fail_times:
            return route.fulfill(status=503, json={"detail": "Reward not saved. Try again."})
        payload = route.request.post_data_json
        writes.append(payload)
        detail["reward"] = {"has_reward": payload["has_reward"], "text": payload.get("text", "")}
        return route.fulfill(json={"id": "synthetic", "survey_id": "synthetic", "reward": detail["reward"]})
    page.route("**/api/surveys/synthetic/reward", handle)
    return calls
