"""Intercept every request; never let Chromium resolve or follow destinations itself."""
import asyncio
from types import SimpleNamespace
from threading import Lock
import http.client
import json
import logging
import re
import socket
import time
from urllib.parse import unquote, urlsplit

from .policy import SIGNIN_PATH, UnsafeSurveyURL, origin, public_addresses, request_url, validate_url
from .definition import adapt_definition, find_definition
from .proxy import corporate_proxy

logger = logging.getLogger(__name__)

FINAL_ENDPOINT = re.compile(r"submit|finish|complet|finaliz|terminate", re.I)
PARTICIPANT_WRITES = {"POST", "PUT", "PATCH"}
MAX_WRITE_BYTES = 256 * 1024


class GuardedTransport:
    """Same-origin only, pinned public DNS (or approved proxy), no redirects, bounded.

    Default: GET/HEAD only, completion-looking endpoints blocked. ``participate``
    (owner-approved) lets the survey's own page act as a respondent: same-origin
    writes, including RedJade's per-answer and per-questionnaire "submit" events.
    Endpoint names cannot tell a section save from completion, so in that mode the
    session's rule (never click a Submit/Finish control) is the completion guard.
    Deletes and cross-origin traffic stay blocked in every mode.
    """

    def __init__(self, url, *, local, approval, coverage, participate=False):
        self.participate = participate and not local
        self.start_url = url
        self.lock = Lock()
        self.origin = origin(url)
        self.parts = urlsplit(url)
        self.local, self.approval, self.coverage = local, approval, coverage
        validate_url(url, allow_test_local=local, approval=approval)
        self.proxy = None if local else corporate_proxy(self.parts.hostname)
        self.address = self.parts.hostname
        if not local and not self.proxy:
            try:
                addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(
                    self.parts.hostname, 443, type=socket.SOCK_STREAM)})
            except OSError:
                raise UnsafeSurveyURL("Survey host could not be safely resolved.") from None
            if not public_addresses(addresses):
                raise UnsafeSurveyURL("Survey host did not resolve exclusively to public addresses.")
            self.address = addresses[0]
        # Large assets via the corporate proxy alone take ~45s; give that route room.
        self.deadline = time.monotonic() + (300 if self.proxy else 90)
        self.requests = 0
        self.bytes = 0
        self.definition = None

    async def handle_async(self, route):
        """Run only HTTP in a worker, never Playwright route objects across threads."""
        request = route.request
        proxy = SimpleNamespace(request=SimpleNamespace(
            url=request.url, method=request.method, headers=await request.all_headers(),
            post_data=request.post_data_buffer))
        outcome = {}
        proxy.abort = lambda *args: outcome.update(abort=args)
        proxy.fulfill = lambda **kwargs: outcome.update(fulfill=kwargs)
        await asyncio.to_thread(self, proxy)
        try:
            if "fulfill" in outcome:
                await route.fulfill(**outcome["fulfill"])
            else:
                await route.abort("blockedbyclient")
        except Exception:
            # A page can close while an in-flight bounded HTTP operation finishes.
            pass

    def observe_response(self, body: bytes) -> None:
        """Inspect an already permitted response only. No new traffic or progression.

        First valid definition wins; later participant responses cannot replace it.
        The transport's existing 2 MiB response cap also bounds passive parsing.
        """
        if self.definition is not None or len(body) > 2 * 1024 * 1024:
            return
        try:
            questionnaire = find_definition(json.loads(body))
            if questionnaire is not None:
                candidate = adapt_definition(questionnaire)
                if not candidate.snapshot.pages:
                    raise ValueError("Empty definition")
                self.definition = candidate
        except (ValueError, TypeError, KeyError, RecursionError):
            warning = "Passive definition payload was unreadable; retaining rendered-only coverage."
            if warning not in self.coverage.warnings:
                self.coverage.warnings.append(warning)

    def write_allowed(self, request) -> bool:
        if not (self.participate and request.method in PARTICIPANT_WRITES
                and len(request.post_data or b"") <= MAX_WRITE_BYTES):
            return False
        with self.lock:
            self.coverage.participated = True
        return True

    def block(self, route):
        with self.lock:
            self.coverage.blocked_requests += 1
            if route.request.method == "POST" and urlsplit(route.request.url).path == SIGNIN_PATH:
                warning = "Survey requires participant sign-in; the reader is not in participant mode."
                if warning not in self.coverage.warnings:
                    self.coverage.warnings.append(warning)
        route.abort("blockedbyclient")

    def __call__(self, route):
        request = route.request
        with self.lock:
            self.requests += 1
        try:
            request_url(request.url, self.start_url, local=self.local, approval=self.approval,
                        any_query=self.participate)
            parts = urlsplit(request.url)
            write = request.method not in {"GET", "HEAD"}
            # Origin/completion checks below run before any write is forwarded.
            if (origin(request.url) != self.origin
                    or (FINAL_ENDPOINT.search(unquote(parts.path)) and not self.participate)
                    or self.requests > 150
                    or self.bytes > 20 * 1024 * 1024 or time.monotonic() > self.deadline
                    or (write and not self.write_allowed(request))):
                return self.block(route)
            # Downloads are idempotent: one retry absorbs proxy stalls. Writes never repeat.
            for attempt in range(1 if write else 2):
                try:
                    status, raw_headers, body = self._exchange(request, parts, write)
                    break
                except (OSError, http.client.HTTPException) as error:
                    logger.warning("Reader request failed (attempt %d): %s", attempt + 1, type(error).__name__)
                    if write or attempt:
                        return self.block(route)
            if status is None:
                return self.block(route)
            with self.lock:
                self.bytes += len(body)
            if 200 <= status < 300 and request.method == "GET":
                # Do not parse normal HTML/assets (or emit JSON errors for them).
                if body.lstrip().startswith(b"{"):
                    with self.lock:
                        self.observe_response(body)
            response_headers = {key.lower(): value for key, value in raw_headers
                                if key.lower() not in {"transfer-encoding", "connection", "content-length", "location"}}
            response_headers["referrer-policy"] = "no-referrer"
            cookies = [value for key, value in raw_headers if key.lower() == "set-cookie"]
            if cookies:
                response_headers["set-cookie"] = "\n".join(cookies)  # Playwright's multi-cookie form
            route.fulfill(status=status, headers=response_headers, body=body)
        except Exception:
            # Network/browser errors may contain the original token-bearing URL.
            self.block(route)

    def _exchange(self, request, parts, write):
        """One HTTP round trip. Returns (None, [], b"") for redirects or oversized bodies."""
        port = parts.port or (80 if self.local else 443)
        timeout = 20 if self.proxy else 3  # corporate proxy stalls mid-download on large chunks
        if self.local:
            connection = http.client.HTTPConnection(self.address, port, timeout=timeout)
        elif self.proxy:
            # HTTPSConnection verifies the target certificate/SNI after CONNECT.
            # The approved corporate proxy, not local DNS, resolves the upstream.
            connection = http.client.HTTPSConnection(self.proxy.hostname, self.proxy.port, timeout=timeout)
            connection.set_tunnel(parts.hostname, port)
        else:
            connection = http.client.HTTPSConnection(parts.hostname, port, timeout=timeout)
            # Keep TLS certificate/SNI validation against the original hostname,
            # but connect only to the vetted address. No DNS rebinding window.
            connection._create_connection = lambda address, timeout, source_address: socket.create_connection(
                (self.address, port), timeout, source_address)
        try:
            headers = {key: value for key, value in request.headers.items()
                       if key.lower() not in {"proxy-authorization", "referer", "host", "content-length"}}
            # Authorization/cookies here are the survey app's own same-origin session
            # (fresh browser context: no user credentials exist to leak).
            connection.request(request.method, (parts.path or "/") + ("?" + parts.query if parts.query else ""),
                               body=request.post_data if write else None, headers=headers)
            response = connection.getresponse()
            # All redirects are unsupported, even same-origin. Never follow one.
            if 300 <= response.status < 400:
                return None, [], b""
            raw_headers = response.getheaders()
            content_type = dict((key.lower(), value) for key, value in raw_headers).get("content-type", "")
            limit = (8 if "javascript" in content_type or "text/css" in content_type else 2) * 1024 * 1024
            body = response.read(limit + 1)
            if len(body) > limit:
                return None, [], b""
            return response.status, raw_headers, body
        finally:
            connection.close()
