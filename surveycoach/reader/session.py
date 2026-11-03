"""Bounded asynchronous Playwright reader with a synchronous public entry point. No live reads happen at import time."""
import asyncio
import json
import logging
import re
import tempfile
import time
from pathlib import Path

from surveycoach.snapshot import SurveySnapshot

from .definition import apply_definition
from .extract import extract_page, fingerprint
from .models import Capture, Coverage, ReadResult
from .observe import OBSERVE
from .policy import validate_url
from .transport import GuardedTransport

FINAL = re.compile(r"\b(submit|finish|complete|done)\b", re.I)
NEXT = re.compile(r"^(next|continue|begin|start)$", re.I)
LINK = re.compile(r"\w+://\S+")
# Real content, not a blank or "Loading..." transition screen (RedJade shows both between pages).
READY = "(old) => { const t = document.body.innerText.trim(); " \
        "return !!t && t !== old && !/^(loading[. …]*|please wait[. …]*)$/i.test(t); }"
logger = logging.getLogger(__name__)


def describe_error(error: BaseException) -> str:
    """Type plus first message line, links removed: diagnosable, never token-bearing."""
    first = (str(error).splitlines() or [""])[0]
    return f"{type(error).__name__}: {LINK.sub('[link]', first)}"[:200]


def patience(transport) -> int:
    """Timeout multiplier: the corporate proxy route is ~5x slower for assets and fonts."""
    return 5 if transport.proxy else 1


def external_progression_stop(*, allow_test_local: bool, participate: bool = False) -> bool:
    """An external Next may write; only owner-approved participant mode permits it.

    Final controls (Submit/Finish) always stop the read, in every mode.
    """
    return not (allow_test_local or participate)


def read_survey(url: str, *, allow_test_local: bool = False, approval: bool = False,
                max_pages: int = 30, participate: bool = False) -> ReadResult:
    """Synchronous entry point; run browser interception on its own event loop.

    ``participate`` lets the reader answer and advance like a respondent (owner-approved).
    """
    return asyncio.run(_read_survey(url, allow_test_local=allow_test_local, approval=approval,
                                    max_pages=max_pages, participate=participate))


async def _read_survey(url: str, *, allow_test_local: bool, approval: bool,
                       max_pages: int, participate: bool = False) -> ReadResult:
    """Read one visible path into the existing SurveySnapshot.

    URL-policy errors raise UnsafeSurveyURL; invalid budgets raise ValueError.
    Browser failures return a partial result with a generic (URL-free) warning.
    Captures are private temporary files; the caller owns deletion/retention.
    """
    validate_url(url, allow_test_local=allow_test_local, approval=approval)
    if type(max_pages) is not int or not 1 <= max_pages <= 30:
        raise ValueError("max_pages must be an integer between 1 and 30")
    coverage = Coverage()
    transport = GuardedTransport(url, local=allow_test_local, approval=approval, coverage=coverage,
                                 participate=participate)
    slow = patience(transport)
    directory = Path(tempfile.mkdtemp(prefix="surveycoach-reader-"))
    result = ReadResult(snapshot=SurveySnapshot(title="", source_url=url, pages=[]),
                        coverage=coverage, capture_dir=directory)
    if participate and not allow_test_local:
        coverage.warnings.append("Participant mode: this read answered questions as a test respondent and left an "
                                 "incomplete response in the survey tool (text answers say 'SurveyCoach test'). "
                                 "It stops before the final Submit/Finish.")
    elif not allow_test_local:
        coverage.warnings.append("Approved external read: page loads can create partial participant data. All writes are blocked.")
    from playwright.async_api import async_playwright

    async def capture(page, observed):
        number = len(result.captures)
        model = extract_page(observed, number)
        png = directory / f"page-{number:02d}.png"
        observation = directory / f"page-{number:02d}.json"
        await page.screenshot(path=str(png), timeout=3000 * slow)
        observation.write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf-8")
        png.chmod(0o600)
        observation.chmod(0o600)
        result.snapshot.pages.append(model)
        result.captures.append(Capture(page_id=model.id, viewport_png=png, observation_json=observation))
        coverage.pages_captured = len(result.captures)

    async def close_socket(socket):
        await socket.close()

    async def dismiss_dialog(dialog):
        await dialog.dismiss()

    try:
        async with asyncio.timeout(max(0, transport.deadline - time.monotonic())), async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=[
                "--disable-background-networking", "--disable-quic", "--no-proxy-server",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--host-resolver-rules=MAP * ~NOTFOUND",
            ])
            try:
                context = await browser.new_context(viewport={"width": 393, "height": 852},
                                              is_mobile=True, has_touch=True, service_workers="block",
                                              accept_downloads=False, permissions=[])
                context.set_default_timeout(3000 * slow)
                await context.route("**/*", transport.handle_async)
                await context.route_web_socket("**/*", close_socket)
                page = await context.new_page()
                page.on("dialog", dismiss_dialog)
                await page.goto(url, wait_until="domcontentloaded", timeout=12000 * slow)
                await page.wait_for_timeout(200)
                if transport.proxy:
                    try:
                        await page.wait_for_function(READY, arg=None, timeout=15000)
                    except Exception:
                        pass
                previous = set()
                for _ in range(max_pages):
                    if time.monotonic() >= transport.deadline:
                        coverage.stop_reason = "time_limit"
                        break
                    observed = await page.evaluate(OBSERVE)
                    result.snapshot.title = result.snapshot.title or observed["title"]
                    fp = fingerprint(observed)
                    if fp in previous:
                        coverage.stop_reason = "loop"
                        break
                    previous.add(fp)
                    await capture(page, observed)
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
                    if external_progression_stop(allow_test_local=allow_test_local, participate=participate):
                        coverage.stop_reason = "external_progression_unverified"
                        coverage.warnings.append("External advancement disabled: Next can write or finalize a response; passive content never authorizes advancement.")
                        break
                    await _answer_groups(page, observed)
                    revealed = await page.evaluate(OBSERVE)
                    if fingerprint(revealed) != fp:
                        # Capture newly revealed wording, but do not guess dependencies.
                        await capture(page, revealed)
                        coverage.stop_reason = "same_page_change"
                        break
                    await page.locator(f'[data-surveycoach-id="{nav[0]["id"]}"]').click()
                    try:
                        await page.wait_for_function(READY, arg=observed["text"], timeout=2000 * slow)
                    except Exception:
                        coverage.stop_reason = "blocked"
                        break
                    await page.wait_for_timeout(100)
                else:
                    coverage.stop_reason = "page_limit"
            finally:
                await browser.close()
    except TimeoutError:
        coverage.stop_reason = "time_limit"
        coverage.warnings.append("Browser read reached its time limit; unavailable content was not inferred.")
    except Exception as error:
        logger.warning("Reader stopped: %s", describe_error(error))
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


async def _answer_groups(page, observation: dict) -> None:
    """First usable option per native group/row, and clearly tagged synthetic text."""
    for group in observation["groups"]:
        selected = set()
        for item in group["items"]:
            if item["disabled"]:
                continue
            locator = page.locator(f'[data-surveycoach-id="{item["id"]}"]')
            kind = group["kind"]
            if kind in {"single_choice", "multi_choice", "grid_single", "grid_multi"}:
                key = item["row"] or item["name"] or "group"
                if key in selected:
                    continue
                if not item["checked"]:
                    if item["type"] in {"radio", "checkbox"} and await locator.evaluate("e => e.tagName === 'INPUT'"):
                        await locator.check()
                    else:
                        await locator.click()
                selected.add(key)
            elif kind in {"text_short", "text_long"}:
                await locator.fill("SurveyCoach test")
            elif kind == "numeric":
                low, high = float(item["min"] or 1), float(item["max"] or item["min"] or 10)
                await locator.fill(str(int((low + high) // 2)))
            elif kind == "dropdown":
                usable = [o for o in item["options"] if o["value"] and not o["disabled"]]
                if not usable:
                    raise ValueError("No usable dropdown option")
                await locator.select_option(value=usable[0]["value"])
