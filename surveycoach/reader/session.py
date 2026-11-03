"""Bounded synchronous Playwright reader. No live reads happen at import time."""
import json
import re
import tempfile
import time
from pathlib import Path

from surveycoach.snapshot import SurveySnapshot

from .definition import apply_definition
from .extract import answer_groups, extract_page, fingerprint
from .models import Capture, Coverage, ReadResult
from .observe import OBSERVE
from .policy import validate_url
from .transport import GuardedTransport

FINAL = re.compile(r"\b(submit|finish|complete|done)\b", re.I)
NEXT = re.compile(r"^(next|continue|begin|start)$", re.I)


def external_progression_stop(*, allow_test_local: bool) -> bool:
    """An external Next may write/finalize; even a definition never authorizes it."""
    return not allow_test_local


def read_survey(url: str, *, allow_test_local: bool = False, approval: bool = False,
                max_pages: int = 30) -> ReadResult:
    """Read one visible path into the existing SurveySnapshot.

    URL-policy errors raise UnsafeSurveyURL; invalid budgets raise ValueError.
    Browser failures return a partial result with a generic (URL-free) warning.
    Captures are private temporary files; the caller owns deletion/retention.
    """
    validate_url(url, allow_test_local=allow_test_local, approval=approval)
    if type(max_pages) is not int or not 1 <= max_pages <= 30:
        raise ValueError("max_pages must be an integer between 1 and 30")
    coverage = Coverage()
    transport = GuardedTransport(url, local=allow_test_local, approval=approval, coverage=coverage)
    directory = Path(tempfile.mkdtemp(prefix="surveycoach-reader-"))
    result = ReadResult(snapshot=SurveySnapshot(title="", source_url=url, pages=[]),
                        coverage=coverage, capture_dir=directory)
    if not allow_test_local:
        coverage.warnings.append("Approved external read: page loads can create partial participant data. All writes are blocked.")
    from playwright.sync_api import sync_playwright

    def capture(page, observed):
        number = len(result.captures)
        model = extract_page(observed, number)
        png = directory / f"page-{number:02d}.png"
        observation = directory / f"page-{number:02d}.json"
        page.screenshot(path=str(png), timeout=3000)
        observation.write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf-8")
        png.chmod(0o600)
        observation.chmod(0o600)
        result.snapshot.pages.append(model)
        result.captures.append(Capture(page_id=model.id, viewport_png=png, observation_json=observation))
        coverage.pages_captured = len(result.captures)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=[
                "--disable-background-networking", "--disable-quic", "--no-proxy-server",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--host-resolver-rules=MAP * ~NOTFOUND",
            ])
            try:
                context = browser.new_context(viewport={"width": 393, "height": 852},
                                              is_mobile=True, has_touch=True, service_workers="block",
                                              accept_downloads=False, permissions=[])
                context.set_default_timeout(3000)
                context.route("**/*", transport)
                context.route_web_socket("**/*", lambda socket: socket.close())
                page = context.new_page()
                page.on("dialog", lambda dialog: dialog.dismiss())
                page.goto(url, wait_until="domcontentloaded", timeout=10000)
                page.wait_for_timeout(200)
                previous = set()
                for _ in range(max_pages):
                    if time.monotonic() >= transport.deadline:
                        coverage.stop_reason = "time_limit"
                        break
                    observed = page.evaluate(OBSERVE)
                    result.snapshot.title = result.snapshot.title or observed["title"]
                    fp = fingerprint(observed)
                    if fp in previous:
                        coverage.stop_reason = "loop"
                        break
                    previous.add(fp)
                    capture(page, observed)
                    if transport.definition is not None:
                        coverage.stop_reason = "definition_captured"
                        break
                    if observed["screenout"]:
                        coverage.stop_reason = "screen_out"
                        break
                    if any(FINAL.search(button["label"]) for button in observed["nav"]):
                        coverage.stop_reason = "final_control"
                        break
                    if observed["unsupported"]:
                        coverage.stop_reason = "unsupported"
                        break
                    nav = [button for button in observed["nav"] if NEXT.fullmatch(button["label"]) and not button["disabled"]]
                    if len(nav) != 1:
                        coverage.stop_reason = "unsupported"
                        break
                    if len(result.captures) >= max_pages:
                        coverage.stop_reason = "page_limit"
                        break
                    if external_progression_stop(allow_test_local=allow_test_local):
                        coverage.stop_reason = "external_progression_unverified"
                        coverage.warnings.append("External advancement disabled: Next can write or finalize a response; passive content never authorizes advancement.")
                        break
                    answer_groups(page, observed)
                    revealed = page.evaluate(OBSERVE)
                    if fingerprint(revealed) != fp:
                        # Capture newly revealed wording, but do not guess dependencies.
                        capture(page, revealed)
                        coverage.stop_reason = "same_page_change"
                        break
                    page.locator(f'[data-surveycoach-id="{nav[0]["id"]}"]').click()
                    try:
                        page.wait_for_function(
                            "old => document.body.innerText.trim() !== old", arg=observed["text"], timeout=2000)
                    except Exception:
                        coverage.stop_reason = "blocked"
                        break
                    page.wait_for_timeout(100)
                else:
                    coverage.stop_reason = "page_limit"
            finally:
                browser.close()
    except Exception:
        coverage.stop_reason = "reader_error"
        coverage.warnings.append("Browser read could not finish; no unavailable content was inferred.")
    if transport.definition is not None:
        transport.definition.snapshot.source_url = url
        apply_definition(result, transport.definition)
    coverage.warnings.append(f"Read stopped: {coverage.stop_reason}. " + (
        "Definition wording is available; only captures have rendered evidence."
        if coverage.definition_available else "Review only the captured pages."))
    if coverage.blocked_requests:
        coverage.warnings.append("Requests were blocked by safety policy; content or progression may be missing.")
    return result
