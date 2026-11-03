"""Explicit managed-network transport; no credentials, PAC execution, or arbitrary proxies."""
import os
from urllib.parse import urlsplit

from .policy import UnsafeSurveyURL

APPROVED_PROXIES = {"http://proxy-intlho.wal-mart.com:8080"}


def corporate_proxy(target_host: str):
    value = os.environ.get("SURVEYCOACH_CORPORATE_PROXY", "")
    if not value:
        return None
    if value not in APPROVED_PROXIES:
        raise UnsafeSurveyURL("Corporate proxy configuration is not approved.")
    # Proxy owns upstream DNS and network policy. Do not broaden this exception
    # to caller-supplied hosts or arbitrary RedJade subdomains.
    if target_host != "app.redjade.net":
        raise UnsafeSurveyURL("Corporate proxy reader supports only the approved survey host.")
    return urlsplit(value)
