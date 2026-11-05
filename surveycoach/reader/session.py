"""Bounded asynchronous Playwright reader with a synchronous public entry point. No live reads happen at import time."""
import asyncio
import json
import logging
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

from surveycoach.snapshot import SurveySnapshot

from .adaptive import AdaptiveReader
from .definition import apply_definition
from .extract import extract_page, fingerprint
from .models import Capture, Coverage, ReadResult
from .observe import OBSERVE
from .progression import advance
from .requirements import UnmetRequirement
from .policy import validate_url
from .transport import GuardedTransport

FINAL = re.compile(r"\b(submit|finish|complete|done)\b", re.I)
NEXT = re.compile(r"^(next|continue|begin|start)$", re.I)
LINK = re.compile(r"\w+://\S+")
# Real content, not a blank or "Loading..." transition screen (RedJade shows both between pages).
READY = "(old) => { const t = document.body.innerText.trim(); " \
        "return !!t && t !== old && !/^(loading[. …]*|please wait[. …]*)$/i.test(t); }"
logger = logging.getLogger(__name__)
# Two traversals may be legitimate repeated trials; a third identical directed
# transition is a bounded cycle. Page/time budgets remain independent backstops.
MAX_TRANSITION_VISITS = 2


def describe_error(error: BaseException) -> str:
    """Type plus first message line, links removed: diagnosable, never token-bearing."""
    first = (str(error).splitlines() or [""])[0]
    return f"{type(error).__name__}: {LINK.sub('[link]', first)}"[:200]


def patience(transport) -> int:
    """Timeout multiplier: the corporate proxy route is ~5x slower for assets and fonts."""
    return 5 if transport.proxy else 1


def progression_controls(observation: dict, *, participate: bool, include_disabled: bool = False) -> list[dict]:
    """One unambiguous forward action; test participation includes Submit/Finish."""
    return [button for button in observation["nav"] if (include_disabled or not button["disabled"]) and
            (NEXT.fullmatch(button["label"]) or (participate and FINAL.match(button["label"])))]


def external_progression_stop(*, allow_test_local: bool, participate: bool = False) -> bool:
    """An external Next may write; only owner-approved participant mode permits it.

    Participant mode also permits submitting/completing approved test responses.
    """
    return not (allow_test_local or participate)


def read_survey(url: str, *, allow_test_local: bool = False, approval: bool = False,
                max_pages: int = 30, participate: bool = False, planner=None,
                rules_path: Path | None = None, on_capture=None) -> ReadResult:
    """Synchronous entry point; run browser interception on its own event loop.

    ``participate`` lets the reader answer and advance like a respondent (owner-approved).
    """
    return asyncio.run(_read_survey(url, allow_test_local=allow_test_local, approval=approval,
                                    max_pages=max_pages, participate=participate, planner=planner, rules_path=rules_path, on_capture=on_capture))


async def _read_survey(url: str, *, allow_test_local: bool, approval: bool,
                       max_pages: int, participate: bool = False, planner=None,
                       rules_path: Path | None = None, on_capture=None) -> ReadResult:
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
    adaptive = AdaptiveReader(planner=planner, path=rules_path, url=url, coverage=coverage,
                              transport=transport) if participate and rules_path is not None else None
    slow = patience(transport)
    directory = Path(tempfile.mkdtemp(prefix="surveycoach-reader-"))
    result = ReadResult(snapshot=SurveySnapshot(title="", source_url=url, pages=[]),
                        coverage=coverage, capture_dir=directory)
    if participate and not allow_test_local:
        coverage.warnings.append("Participant mode permits synthetic answer saves and advancement "
                                 "(text answers say 'SurveyCoach test'), including Submit/Finish and "
                                 "completed test responses. Only the captured path is reviewed.")
    elif not allow_test_local:
        coverage.warnings.append("Approved external read: page loads can create partial participant data. All writes are blocked.")
    from playwright.async_api import async_playwright

    async def capture(page, observed):
        number = len(result.captures)
        model = extract_page(observed, number, existing_pages=result.snapshot.pages)
        png = directory / f"page-{number:02d}.png"
        observation = directory / f"page-{number:02d}.json"
        await page.screenshot(path=str(png), timeout=3000 * slow)
        observation.write_text(json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf-8")
        png.chmod(0o600)
        observation.chmod(0o600)
        result.snapshot.pages.append(model)
        result.captures.append(Capture(page_id=model.id, viewport_png=png, observation_json=observation))
        coverage.pages_captured = len(result.captures)
        if on_capture is not None:
            on_capture(number, model, png)

    async def close_socket(socket):
        await socket.close()

    async def dismiss_dialog(dialog):
        await dialog.dismiss()

    try:
        async with asyncio.timeout(max(0, transport.deadline - time.monotonic()) + (90 if adaptive else 0)), async_playwright() as playwright:
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
                last_fp = None
                transitions = Counter()
                for _ in range(max_pages):
                    if time.monotonic() >= transport.deadline:
                        coverage.stop_reason = "time_limit"
                        break
                    observed = await page.evaluate(OBSERVE)
                    if not observed['text'].strip() or (not observed['groups'] and not observed['nav'] and re.fullmatch(
                        r'upload successful[.! …]*', observed['text'].strip(), re.I,
                    )):
                        # An upload toast is not a survey page or completion evidence.
                        try:
                            await page.wait_for_function("() => { const text=document.body.innerText.trim().toLowerCase(); return text && text !== 'upload successful' && !/^(loading[. …]*|please wait[. …]*)$/i.test(text); }", timeout=15000)
                        except Exception:
                            coverage.stop_reason = 'blocked'
                            coverage.warnings.append('A blank/loading/upload status screen did not resolve into a survey page.')
                            break
                        observed = await page.evaluate(OBSERVE)
                    result.snapshot.title = result.snapshot.title or observed["title"]
                    fp = fingerprint(observed)
                    if participate:
                        # A generic follow-up may recur after different concepts.
                        # Count rendered transitions, never synthetic capture IDs.
                        transition = (last_fp, fp)
                        if last_fp is not None:
                            transitions[transition] += 1
                        if fp == last_fp or transitions[transition] > MAX_TRANSITION_VISITS:
                            coverage.stop_reason = "loop"
                            coverage.warnings.append("Repeated rendered transition exceeded the bounded visit limit; later pages were not read.")
                            break
                    elif fp in previous:
                        coverage.stop_reason = "loop"
                        break
                    previous.add(fp)
                    last_fp = fp
                    await capture(page, observed)
                    if transport.definition is not None:
                        coverage.stop_reason = "definition_captured"
                        break
                    if observed["screenout"]:
                        coverage.stop_reason = "screen_out"
                        break
                    if not participate and any(FINAL.search(button["label"]) for button in observed["nav"]):
                        coverage.stop_reason = "final_control"
                        break
                    if adaptive and len(result.captures) < max_pages and await adaptive.replay(page, directory):
                        continue
                    if observed["unsupported"]:
                        if adaptive and len(result.captures) < max_pages and await adaptive.recover(page, directory, 'unsupported controls'):
                            continue
                        coverage.stop_reason = "unsupported"
                        break
                    if not observed["groups"] and not observed["nav"] and re.search(
                        r"\bthank\s+you\b|\bresponse\s+(?:has\s+been\s+)?(?:received|recorded)|\bsurvey\s+(?:is\s+)?complete\b",
                        observed["text"], re.I,
                    ):
                        coverage.stop_reason = "path_end"
                        break
                    nav = progression_controls(observed, participate=participate, include_disabled=True)
                    if len(nav) != 1:
                        if adaptive and len(result.captures) < max_pages and await adaptive.recover(page, directory, 'missing or ambiguous forward control'):
                            continue
                        coverage.stop_reason = "unsupported"
                        break
                    if len(result.captures) >= max_pages:
                        coverage.stop_reason = "page_limit"
                        break
                    if external_progression_stop(allow_test_local=allow_test_local, participate=participate):
                        coverage.stop_reason = "external_progression_unverified"
                        coverage.warnings.append("External advancement disabled: Next can write or finalize a response; passive content never authorizes advancement.")
                        break
                    try:
                        outcome = await advance(page, observed, controls=progression_controls,
                                                participate=participate, slow=slow, upload_dir=directory)
                    except UnmetRequirement as error:
                        coverage.warnings.append(str(error))
                        if adaptive and await adaptive.recover(page, directory, str(error)):
                            continue
                        coverage.stop_reason = "unmet_requirement"
                        break
                    if outcome == "same_page_change":
                        # Preserve newly revealed wording; recovery of conditional widgets is bounded.
                        await capture(page, await page.evaluate(OBSERVE))
                        coverage.stop_reason = "same_page_change"
                        break
                    if outcome != "advanced":
                        if adaptive and await adaptive.recover(page, directory, outcome):
                            continue
                        coverage.stop_reason = outcome
                        coverage.warnings.append("Progression failed after bounded requirement recovery; later pages were not read.")
                        break
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
