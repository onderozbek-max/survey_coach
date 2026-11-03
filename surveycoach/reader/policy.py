"""Fail-closed URL policy. Validation is pure; DNS is checked separately at launch."""
from ipaddress import ip_address
from urllib.parse import urlsplit


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
