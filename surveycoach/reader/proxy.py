"""Explicit managed-network transport; no credentials, PAC execution, or arbitrary proxies."""
import os
from urllib.parse import urlsplit

from .policy import UnsafeSurveyURL

APPROVED_PROXY = "http://proxy-intlho.wal-mart.com:8080"
APPROVED_PROXIES = {APPROVED_PROXY}


class ReaderProxyConfigurationError(UnsafeSurveyURL):
    """An operator-selected proxy route was rejected, not a survey DNS failure."""


def corporate_proxy(target_host: str):
    value = os.environ.get("SURVEYCOACH_CORPORATE_PROXY", "")
    if not value:
        return None
    if value not in APPROVED_PROXIES:
        raise ReaderProxyConfigurationError("Corporate proxy configuration is not approved.")
    # Proxy owns upstream DNS and network policy. Do not broaden this exception
    # to caller-supplied hosts or arbitrary RedJade subdomains.
    if target_host != "app.redjade.net":
        raise ReaderProxyConfigurationError("Corporate proxy reader supports only the approved survey host.")
    return urlsplit(value)
