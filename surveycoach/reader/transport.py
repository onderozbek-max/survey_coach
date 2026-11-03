"""Intercept every request; never let Chromium resolve or follow destinations itself."""
import http.client
import json
import re
import socket
import time
from urllib.parse import unquote, urlsplit

from .policy import UnsafeSurveyURL, origin, public_addresses, validate_url
from .definition import adapt_definition, find_definition

FINAL_ENDPOINT = re.compile(r"submit|finish|complet|finaliz|terminate", re.I)


class GuardedTransport:
    """Same-origin GET/HEAD only, pinned public DNS, no redirects or response writes.

    Disallowing all POSTs is intentional: unsupported RedJade initialization or
    progression must stop rather than risk completing a participant response.
    """

    def __init__(self, url, *, local, approval, coverage):
        self.origin = origin(url)
        self.parts = urlsplit(url)
        self.local, self.approval, self.coverage = local, approval, coverage
        self.address = self.parts.hostname
        if not local:
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
        self.coverage.blocked_requests += 1
        route.abort("blockedbyclient")

    def __call__(self, route):
        request = route.request
        self.requests += 1
        connection = None
        try:
            validate_url(request.url, allow_test_local=self.local, approval=self.approval)
            parts = urlsplit(request.url)
            if (origin(request.url) != self.origin or request.method not in {"GET", "HEAD"}
                    or FINAL_ENDPOINT.search(unquote(parts.path)) or self.requests > 150
                    or self.bytes > 20 * 1024 * 1024 or time.monotonic() > self.deadline):
                return self.block(route)
            port = parts.port or (80 if self.local else 443)
            if self.local:
                connection = http.client.HTTPConnection(self.address, port, timeout=3)
            else:
                connection = http.client.HTTPSConnection(parts.hostname, port, timeout=3)
                # Keep TLS certificate/SNI validation against the original hostname,
                # but connect only to the vetted address. No DNS rebinding window.
                connection._create_connection = lambda address, timeout, source_address: socket.create_connection(
                    (self.address, port), timeout, source_address)
            headers = {key: value for key, value in request.headers.items()
                       if key.lower() not in {"authorization", "proxy-authorization", "referer", "host"}}
            connection.request(request.method, parts.path or "/", headers=headers)
            response = connection.getresponse()
            # All redirects are unsupported, even same-origin. Never follow one.
            if 300 <= response.status < 400:
                return self.block(route)
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                return self.block(route)
            self.bytes += len(body)
            if 200 <= response.status < 300 and request.method == "GET":
                # Do not parse normal HTML/assets (or emit JSON errors for them).
                if body.lstrip().startswith(b"{"):
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
