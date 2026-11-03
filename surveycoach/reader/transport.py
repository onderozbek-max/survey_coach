"""Intercept every request; never let Chromium resolve or follow destinations itself."""
import asyncio
from types import SimpleNamespace
from threading import Lock
import http.client
import json
import re
import socket
import time
from urllib.parse import unquote, urlsplit

from .policy import UnsafeSurveyURL, origin, public_addresses, request_url, validate_url
from .definition import adapt_definition, find_definition
from .proxy import corporate_proxy

FINAL_ENDPOINT = re.compile(r"submit|finish|complet|finaliz|terminate", re.I)


class GuardedTransport:
    """Same-origin GET/HEAD only, pinned public DNS, no redirects or response writes.

    Disallowing all POSTs is intentional: unsupported RedJade initialization or
    progression must stop rather than risk completing a participant response.
    """

    def __init__(self, url, *, local, approval, coverage):
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
        self.deadline = time.monotonic() + 90
        self.requests = 0
        self.bytes = 0
        self.definition = None

    async def handle_async(self, route):
        """Run only HTTP in a worker, never Playwright route objects across threads."""
        request = route.request
        proxy = SimpleNamespace(request=SimpleNamespace(url=request.url, method=request.method, headers=dict(request.headers)))
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

    def block(self, route):
        with self.lock:
            self.coverage.blocked_requests += 1
            if route.request.method == "POST" and urlsplit(route.request.url).path == "/api/v1/surveys/online_sign_in_events":
                warning = "Survey requires participant sign-in; participant creation was blocked."
                if warning not in self.coverage.warnings:
                    self.coverage.warnings.append(warning)
        route.abort("blockedbyclient")

    def __call__(self, route):
        request = route.request
        with self.lock:
            self.requests += 1
        connection = None
        try:
            request_url(request.url, self.start_url, local=self.local, approval=self.approval)
            parts = urlsplit(request.url)
            if (origin(request.url) != self.origin or request.method not in {"GET", "HEAD"}
                    or FINAL_ENDPOINT.search(unquote(parts.path)) or self.requests > 150
                    or self.bytes > 20 * 1024 * 1024 or time.monotonic() > self.deadline):
                return self.block(route)
            port = parts.port or (80 if self.local else 443)
            if self.local:
                connection = http.client.HTTPConnection(self.address, port, timeout=3)
            elif self.proxy:
                # HTTPSConnection verifies the target certificate/SNI after CONNECT.
                # The approved corporate proxy, not local DNS, resolves the upstream.
                connection = http.client.HTTPSConnection(self.proxy.hostname, self.proxy.port, timeout=3)
                connection.set_tunnel(parts.hostname, port)
            else:
                connection = http.client.HTTPSConnection(parts.hostname, port, timeout=3)
                # Keep TLS certificate/SNI validation against the original hostname,
                # but connect only to the vetted address. No DNS rebinding window.
                connection._create_connection = lambda address, timeout, source_address: socket.create_connection(
                    (self.address, port), timeout, source_address)
            headers = {key: value for key, value in request.headers.items()
                       if key.lower() not in {"authorization", "proxy-authorization", "referer", "host"}}
            connection.request(request.method, (parts.path or "/") + ("?" + parts.query if parts.query else ""), headers=headers)
            response = connection.getresponse()
            # All redirects are unsupported, even same-origin. Never follow one.
            if 300 <= response.status < 400:
                return self.block(route)
            content_type = dict((key.lower(), value) for key, value in response.getheaders()).get("content-type", "")
            limit = (8 if "javascript" in content_type or "text/css" in content_type else 2) * 1024 * 1024
            body = response.read(limit + 1)
            if len(body) > limit:
                return self.block(route)
            with self.lock:
                self.bytes += len(body)
            if 200 <= response.status < 300 and request.method == "GET":
                # Do not parse normal HTML/assets (or emit JSON errors for them).
                if body.lstrip().startswith(b"{"):
                    with self.lock:
                        self.observe_response(body)
            response_headers = {key.lower(): value for key, value in response.getheaders()
                                if key.lower() not in {"transfer-encoding", "connection", "content-length", "location"}}
            response_headers["referrer-policy"] = "no-referrer"
            route.fulfill(status=response.status, headers=response_headers, body=body)
        except Exception:
            # Network/browser errors may contain the original token-bearing URL.
            self.block(route)
        finally:
            if connection:
                connection.close()
