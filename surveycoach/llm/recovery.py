"""Evidence-based Wibey failure messages and one bounded local sign-in process."""
import re
import subprocess
import tempfile
import threading
import time

from .base import LlmError

class WibeyRecoveryError(LlmError):
    """Sanitized, actionable local connection/sign-in guidance."""


_auth_process = None
_auth_started = 0.0
_lock = threading.Lock()


def classify_failure(detail: str) -> str:
    text = detail.lower()
    if re.search(r'\b(?:401|unauthorized|unauthenticated)\b|not authenticated|token (?:has )?expired|wibey --auth|authentication required|please (?:sign|log) in', text):
        return 'auth'
    if re.search(r'\b(?:enotfound|eai_again|econnrefused|econnreset|etimedout|enetunreach|ehostunreach)\b|network (?:is )?unreachable|failed to fetch|certificate verify failed', text):
        return 'network'
    return 'other'


def _schedule_expiry(process):
    def expire():
        if process.poll() is None:
            process.terminate()
    timer = threading.Timer(300, expire)
    timer.daemon = True
    timer.start()


def start_authentication(binary: str) -> bool:
    """Wibey owns the browser/SSO callback; never read or expose auth output."""
    global _auth_process, _auth_started
    with _lock:
        if _auth_process is not None and _auth_process.poll() is None:
            return True
        if time.monotonic() - _auth_started < 60:
            return False
        try:
            _auth_process = subprocess.Popen([binary, '--auth'], cwd=tempfile.gettempdir(),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
            _auth_started = time.monotonic()
            _schedule_expiry(_auth_process)
            return True
        except OSError:
            return False


def failure_error(detail: str, binary: str) -> LlmError:
    """Never return raw CLI diagnostics, URLs, tokens, or model output to the UI."""
    kind = classify_failure(detail)
    if kind == 'network':
        return WibeyRecoveryError('Wibey could not reach its service. Connect to Walmart VPN or Eagle WiFi, then try again. No sign-in was started.')
    if kind == 'auth':
        started = start_authentication(binary)
        if started:
            return WibeyRecoveryError('Wibey sign-in is required. Started wibey --auth in the background; finish sign-in in the browser Wibey opens, then try again. If no browser opens, run wibey --auth in your terminal.')
        return WibeyRecoveryError('Wibey sign-in is required. Run wibey --auth in your terminal, finish browser sign-in, then try again.')
    return WibeyRecoveryError('Wibey failed without a confirmed network or sign-in cause. Try again; if it persists, check the local Wibey installation. No sign-in was started.')
