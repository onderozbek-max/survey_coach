# Task 4 — managed-network reader diagnostics/setup

Owner: code-puppy-2d1587. Scope: Task 4 only. Local changes; no push/deployment.

## Checklist
- [x] Reproduce with DNS-only/platform configuration checks.
- [x] Add failing diagnostics/transport regressions, observe red, implement green.
- [x] Preserve explicit approved proxy and security boundaries; document exact setup.
- [x] Run focused and broader reader security/job suites; review own diff/line counts.
- [x] Leave concurrent UI/quality/queue work and staged progress.md untouched.

## Root cause evidence

Read-only probe on this Mac returned:
- platform: Darwin
- SURVEYCOACH_CORPORATE_PROXY: unset
- socket.getaddrinfo('app.redjade.net', 443, type=SOCK_STREAM): gaierror, errno 8
- /usr/sbin/scutil --proxy (3-second subprocess timeout): ProxyAutoConfigEnable=1;
  ProxyAutoConfigURLString=http://wmtpac.wal-mart.com/proxies/anycast-universal.pac

No PAC was downloaded/executed. No external HTTP/HEAD, survey/session/participant
read, or real database operation was performed. Tests use synthetic temp databases,
mock transports/DNS, and local fixture servers only.

The Python transport does not inherit the browser's PAC route. That explains why
browser access does not establish reader connectivity. PAC enabled at a managed URL
alone does not prove its host-specific routing decision. Automatic selection was
therefore deliberately NOT implemented; the plan permits exact explicit setup when
reliable automatic selection cannot be established.

## Changes

- Add typed, URL-free local DNS and network categories; keep unsafe address/URL
  failures as policy rejections instead of guessing from exception text.
- Surface initial document connection/timeout failures through bounded transport
  coverage warnings, so swallowed browser-route failures become actionable job errors.
- Distinguish rejected operator proxy configuration from target DNS failure.
- Reader job errors provide the exact approved environment setting and README section,
  explain local reader versus browser/PAC routing, and do not assert the user is off VPN.
- README documents process-local setup, host limitation, no generic proxy/PAC fallback,
  unchanged TLS/SSRF/write limits, and troubleshooting without weakening policy.
- Existing approved proxy remains exact-match http://proxy-intlho.wal-mart.com:8080
  for app.redjade.net only. No environment/global settings were changed.

## Tests actually run

1. Initial red:
   `.venv/bin/python -m pytest tests/test_reader_failure_messages.py tests/test_reader_transport.py -q`
   Result: 10 failed, 21 passed (new error categories/actionable messages missing).
2. Final red before implementation:
   `.venv/bin/python -m pytest tests/test_reader_failure_messages.py tests/test_reader_transport.py tests/test_reader_proxy.py -q`
   Result: 12 failed, 31 passed. Includes missing route-warning propagation and job handling.
3. Green, same focused command: **43 passed**, 1 existing dependency warning, 0.71s.
4. Broader suite:
   `.venv/bin/python -m pytest tests/test_reader_*.py tests/test_mvp_reader_api.py tests/test_server_jobs.py tests/test_server_security.py -q -m 'not live'`
   Result: **221 passed**, 1 existing dependency warning, 101.74s.
5. `git diff --check`: passed.
6. Source/test line counts: proxy.py 25; transport.py 219; server/reader.py 185;
   test_reader_proxy.py 68; test_reader_transport.py 108; test_reader_failure_messages.py 90.
   All owned source files remain below 600 lines.

Warning: existing StarletteDeprecationWarning about httpx/TestClient; unrelated to this task.
Focused regressions cover explicit approved proxy/TLS tunnel target preservation,
arbitrary/credential/loopback proxies rejected, fixed upstream restriction, generic
proxy environment ignored, public/private/mixed/empty-address policy, DNS versus
other resolver errors, URL-free messages, initial connection/timeout categorization,
and failed jobs creating no completed review.

## Exact startup instructions (not executed)

From /Users/o0o02dn/Documents/adminAI/survey-coach, stop an existing local server
normally, then launch its replacement:

```bash
SURVEYCOACH_CORPORATE_PROXY=http://proxy-intlho.wal-mart.com:8080 \
  .venv/bin/python -m surveycoach.server \
  --db "$HOME/Library/Application Support/SurveyCoach/mvp.sqlite3" --port 8765
```

Open http://127.0.0.1:8765/local.html. This setting applies only to the newly launched
process and only supports app.redjade.net; other approved RedJade hosts require
direct public DNS. Do not enable participant mode to diagnose connectivity. Do not
use member invitation links. Use approved corporate network/VPN; persistent failure
requires corporate network support, not TLS disabling or alternate proxies.

## Limitations

Connectivity is **not verified/fixed** by this work: no approved-proxy base-host HEAD
or live link was requested. The observed DNS-only failure remains the last actual
network observation. No auto-detection/platform subprocess is used by production
code, so there is no platform-detection fallback to trust. Later asset/startup
failures can still produce partial/unsupported coverage under existing reader rules;
new initial-connection categories are not a universal network diagnostic. Existing
read/session/transport deadlines and request bounds are unchanged. No full-app suite
or independent delegated review was run (Task 4 scope; delegation prohibited).
