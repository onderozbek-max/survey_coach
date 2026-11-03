# Controlled reader MVP

```python
from surveycoach.reader import read_survey

result = read_survey("http://127.0.0.1:8765/choices", allow_test_local=True)
snapshot = result.snapshot       # existing surveycoach.snapshot.SurveySnapshot
coverage = result.coverage       # pages_captured, stop_reason, warnings, blocked_requests
captures = result.captures       # page_id, viewport_png, observation_json (Path objects)
```

`read_survey(url, *, allow_test_local=False, approval=False, max_pages=30, participate=False)` is
synchronous. Policy violations raise `UnsafeSurveyURL` without echoing input;
invalid budgets raise `ValueError`. Browser/interaction errors return captured
content and a generic `reader_error`. No unavailable question is inferred.
`ReadResult.model_dump(mode="json")` serializes paths for a caller.

## Managed Mac corporate connection

On the owner's Mac, the configured corporate PAC routes this survey host through `proxy-intlho.wal-mart.com:8080`. Start the local server with `SURVEYCOACH_CORPORATE_PROXY=http://proxy-intlho.wal-mart.com:8080` to use that approved route. The opt-in supports only `app.redjade.net`; arbitrary proxy URLs/credentials are rejected. The corporate proxy owns upstream DNS/network policy on this route; direct mode still validates/pins public DNS. TLS verification against the survey hostname remains enabled. Same-origin, response-size, deadline and no-redirect guards remain in force. Default mode blocks writes and completion-looking endpoints; participant mode explicitly permits survey writes.

## Approved participant mode (off by default)

With the survey owner's permission to submit synthetic answers, start the local server with `SURVEYCOACH_PARTICIPANT_MODE=1`, or call `read_survey(..., approval=True, participate=True)`. The old `SURVEYCOACH_ALLOW_TEST_SESSION` setting is no longer used.

Participant mode forwards same-origin POST/PUT/PATCH bodies up to 256 KiB, including RedJade startup, answer saves and questionnaire submissions. It accepts app-generated same-origin queries and advances through one deterministic path. Each read may create participant records and synthetic responses. Text answers say `SurveyCoach test`; choice-only responses are not separately tagged. Exclude these test responses from research results.

The reader never clicks explicitly labeled Submit/Finish/Complete/Done controls, but **Next and app-generated requests may complete responses**. There is no transport-level completion guarantee in participant mode. Unknown controls, uploads, photos and unsupported widgets stop the read. Fresh browser contexts contain no personal profile; app-issued session cookies/tokens are forwarded only to the same origin. Proxy credentials and cross-origin traffic remain blocked.

## Supported, intentionally narrow

- Visible native radio/checkbox groups with fieldset legends; explicit ARIA
  radiogroups/groups and radio/checkbox controls.
- Native text/textarea, integer-like numeric inputs, single-select dropdowns.
- Native table grids with fieldsets, column headings and row headings.
- Visible `img` dimensions, alt text, load state and object-fit (no original bytes).
- Original rendered wording, viewport screenshot and structured observation JSON.
- One deterministic path: first usable choice per group/row, synthetic text
  `SurveyCoach test`, numeric midpoint. No random or AI-generated answers.
- Next/Continue/Begin/Start with transition verification; final-label stop before
  answering/clicking Submit/Finish/Complete/Done; screen-out wording detection.
- Revealed questions are captured, then reading stops rather than guessing their
  conditional dependencies. Repeated pages, unsupported widgets, missing labels,
  failed transitions and ambiguous navigation stop honestly.

Absent explicit `data-page-id` and `data-question-id`/`data-question-cid`, rendered
IDs are deterministic hashes of observed wording/structure, with positional
occurrence disambiguation. Hashes are **not** RedJade IDs and are not guaranteed
stable across wording changes, randomization or conditional layout changes.
The supplied `SurveySnapshot` model has no coverage metadata: always consume the
wrapper's coverage; a snapshot alone must not be interpreted as a complete read.
Survey type uses the existing model's default; it is not inferred by the reader.

## Safety policy

- Automated tests use synthetic loopback fixtures. Owner-approved live diagnostics have also been run; real captures remain private temporary files.
- External URLs need `approval=True`, HTTPS/443 and a `redjade.net` host or
  subdomain. Queries, fragments, credentials, ambiguous URL syntax, arbitrary
  hosts, private/literal IPs and metadata destinations are denied.
- Test mode permits only literal `127.0.0.1` or `::1` over HTTP. It cannot be
  combined with approval to enable external traffic. No hostname/local-network
  escape hatch; no `localhost` DNS lookup.
- External DNS must resolve exclusively to public IPs. HTTP transport pins one
  vetted IP while retaining TLS hostname/certificate verification. Chromium does
  not resolve network destinations. No environment proxy is used.
- Every browser HTTP request is intercepted and checked again. Only same-origin
  GET/HEAD are forwarded by default. Participant mode additionally permits bounded
  POST/PUT/PATCH requests and app-generated queries, including submit endpoints.
  Cross-origin traffic, deletes and **all redirects** remain blocked.
  Service workers, WebSockets, downloads, permissions and nonproxied WebRTC are
  disabled/blocked. Fresh browser context for every read; no saved profile.
- **External progression is disabled unless participant mode is explicitly enabled.**
  RedJade's final control may say “Next.” External mode captures its initial
  visible state and stops (`external_progression_unverified`) if it would need
  to advance. A passively captured definition stops immediately after the first
  screenshot (`definition_captured`), without answering or advancing in any mode.
  Blocking writes may prevent initialization entirely.
- Approval does not guarantee side-effect-free GETs: external page loads can
  create partial participant data. This module neither proves nor claims that
  an arbitrary external GET cannot mutate server state. It does not implement
  participant tagging or definition-aware progression. Do not advertise this as
  a production-safe full RedJade crawler.
- Diagnostics contain generic error categories, never arbitrary exception text,
  browser console output, request URLs, headers or response payloads. The initial
  query-free survey URL is preserved as snapshot provenance; page wording is
  preserved verbatim, not scrubbed or rewritten.

Bounds: 1–30 captures, 150 requests, approximately 20 MiB aggregate responses,
2 MiB per response (8 MiB for JavaScript/CSS). Direct connections have a 90-second
deadline and 3-second socket/interaction timeouts. The approved corporate proxy
has a 300-second deadline, 20-second socket and 15-second interaction timeouts.
Downloads retry once on network errors; writes never retry. Text entry allows
RedJade's observed 200 ms debounce to finish before advancement. Screenshot/DOM sizes
and a hostile browser process are not hard OS-level resource-sandboxed. This is
not a general-purpose untrusted-web execution service; deploy behind a proper
network/process sandbox for adversarial use.

## Captures and unsupported formats

Captures are in an OS temporary directory (`surveycoach-reader-*`, directory
mode 0700, files mode 0600), never the repository. Callers own deletion and
retention. Observation JSON contains survey wording and synthetic selections;
treat it as sensitive. No raw HTML, console/network logs, URL-bearing attributes,
whole participant API responses or executable replicas are persisted to disk.
An available questionnaire subtree is retained in memory as `result.definition`;
this may contain sensitive survey configuration, so do not expose it as public API
output or log it. The server integration need not return this field.

## Passive definition API

`GuardedTransport` inspects successful, already-permitted GET response bodies for
`questionnaire.data.pages` or `response.questionnaire.data.pages`. No request is
added or changed. First valid definition wins; malformed/unsupported envelopes
retain rendered-only coverage. `reader.definition.find_definition(payload)` returns
the questionnaire subtree; `adapt_definition(questionnaire, source_url="", locale="en_US")`
returns a `DefinitionRead` with `.snapshot`, `.raw`, `.conditions`, `.warnings`,
`.wording_complete`. `apply_definition(read_result, definition_read)` updates a result.

All definition pages, question prompts and answer labels/IDs are retained in source
array order. Raw source configuration preserves unsupported fields and exact gates;
gates are never evaluated to authorize actions. Unsupported question types use
`unknown`, with warning. Missing locale wording falls back with explicit warning
and `definition_wording_complete=False`; empty wording also marks incomplete.
Requiredness absent from the definition is explicitly warned, not verified.

New coverage fields: `definition_available`, `definition_wording_complete`,
`pages_defined`, `questions_defined`, `definition_conditions`,
`rendered_definition_pages`, `visual_media_verified=False`, `paths_verified=False`.
`pages_captured` remains the actual screenshot count, never the definition page count.
`full_branching_coverage` remains false. Only explicit known page **and question**
IDs permit rendered media/layout merge; text similarity never establishes identity.
Otherwise the snapshot is definition-only, with captures retained separately.

No full branching coverage, branch planning, multi-session
walks, nested loop interpretation, vision fallback, CAPTCHA bypass, sample-code
solving, ranking, custom sliders, constant sums, generic unlabeled button answers,
video analysis, stitched inner-scroll screenshots, CSS backgrounds or hidden
question extraction. Missing formats remain unsupported, not silently synthesized.

Run only synthetic local tests:

```
.venv/bin/python -m pytest tests/test_reader_*.py -q
```
