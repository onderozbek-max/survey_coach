"""Fail-closed URL policy. Validation is pure; DNS is checked separately at launch."""
from ipaddress import ip_address
import json
import re
from urllib.parse import parse_qsl, urlsplit


class UnsafeSurveyURL(ValueError):
    """A generic, deliberately URL-free policy rejection."""


def validate_url(url: str, *, allow_test_local: bool = False, approval: bool = False) -> str:
    """Accept clean RedJade HTTPS URLs, or literal loopback in isolated test mode.

    Queries/fragments are not supported: member identifiers and access tokens must
    never become browser history, diagnostics, logs, or snapshot provenance.
    """
    try:
        if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url) or "\\" in url:
            raise ValueError
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
            raise ValueError
        if not host or "%" in host or host.endswith("."):
            raise ValueError
        if allow_test_local:
            if parts.scheme != "http" or host not in {"127.0.0.1", "::1"}:
                raise ValueError
            _ = parts.port  # validate the port even for loopback
            return url
        if parts.scheme != "https" or parts.port not in {None, 443}:
            raise ValueError
        if not (host == "redjade.net" or host.endswith(".redjade.net")):
            raise ValueError
        if not approval:
            raise UnsafeSurveyURL("Explicit approval is required for an external survey read.")
        return url
    except (ValueError, TypeError) as exc:
        if isinstance(exc, UnsafeSurveyURL):
            raise
        raise UnsafeSurveyURL("Survey URL is not permitted by the reader safety policy.") from None


# Observed read-only RedJade startup GETs -> the single query key each may carry.
READONLY_QUERIES = {
    "/static/locales/languages.json": "cache",
    "/static/locales/localized_languages.json": "cache",
    "/static/locales/client.en_US.json": "cache",
    "/api/v1/surveys/station_status_check": "cache",
    "/api/v1/surveys/current_participant": "lite",
}
SAFE_VALUE = re.compile(r"[A-Za-z0-9_.-]{1,100}")


def request_url(url: str, start: str, *, local=False, approval=True) -> str:
    """Internal GET schema only; input URLs still prohibit every query string."""
    parts, source = urlsplit(url), urlsplit(start)
    if not parts.query:
        return validate_url(url, allow_test_local=local, approval=approval)
    validate_url(parts._replace(query="").geturl(), allow_test_local=local, approval=approval)
    if local or parts.hostname != "app.redjade.net" or origin(url) != origin(start) or parts.fragment:
        raise UnsafeSurveyURL("Startup query is not supported.")
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    params = dict(pairs)
    if len(params) != len(pairs):
        raise UnsafeSurveyURL("Duplicate startup parameters are not supported.")
    key = READONLY_QUERIES.get(parts.path)
    if key and set(params) == {key} and SAFE_VALUE.fullmatch(params[key]):
        return url
    segments = source.path.strip("/").split("/")
    if (parts.path == "/api/v1/surveys/event_meta" and len(segments) == 3
            and segments[0] == "surveys" and params == {"company_token": segments[1], "static_url": segments[2]}):
        return url
    raise UnsafeSurveyURL("Startup query is not supported.")


SIGNIN_PATH = "/api/v1/surveys/online_sign_in_events"
ANONYMOUS_FIELDS = ("participant_code", "verification_code", "external_id", "enc")


def validate_signin(url: str, body: bytes, start: str) -> None:
    """Approved test-participant start: anonymous, exact schema, bound to the input survey.

    Carries no answers or identifiers. Every other write remains blocked by the transport.
    """
    try:
        parts, segments = urlsplit(url), urlsplit(start).path.strip("/").split("/")
        data = json.loads(body)
        expected = {"company_token", "static_url", "event_id", "locale", *ANONYMOUS_FIELDS}
        if (parts.hostname != "app.redjade.net" or origin(url) != origin(start) or parts.path != SIGNIN_PATH
                or parts.query or parts.fragment or len(segments) != 3 or segments[0] != "surveys"
                or not isinstance(data, dict) or set(data) != expected
                or data["company_token"] != segments[1] or data["static_url"] != segments[2]
                or type(data["event_id"]) is not int
                or not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", str(data["locale"]))
                or any(data[field] is not None for field in ANONYMOUS_FIELDS)):
            raise ValueError
    except (ValueError, TypeError):
        raise UnsafeSurveyURL("Participant sign-in request is not the approved anonymous test start.") from None


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def public_addresses(addresses: list[str]) -> bool:
    """Reject mixed public/private DNS answers, mapped IPv6, and empty answers."""
    try:
        return bool(addresses) and all(
            ip_address(address).is_global and not ip_address(address).is_multicast
            and not ip_address(address).is_reserved
            and not getattr(ip_address(address), "ipv4_mapped", None)
            for address in addresses
        )
    except ValueError:
        return False
