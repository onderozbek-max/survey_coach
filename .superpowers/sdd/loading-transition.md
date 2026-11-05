# Truthful loading transition

Owner: code-puppy-4f5249. Scope: existing non-LD site only; no backend changes.

## Completed
- [x] Immediate inline `Preparing your review` panel before POST or first GET.
- [x] Shared Home/recheck layout: quiet green activity indicator, labelled phone placeholder, real captures only, responsive 320px layout.
- [x] Actual stage evidence: queued has no current/completed step; opening → read screens → check wording & flow → review ready. No invented save stage, percentage, total, fake capture, or worker heartbeat.
- [x] Elapsed timer and last successful status-response age, explicitly distinguished from backend activity. Unchanged capture count with successful polls says waiting for next screen update.
- [x] Requests bounded to 20 seconds including response body. GET retries only; three consecutive failures pause with keyboard-operable Resume checking. 600 polling attempts also pause. Resume uses same opaque job ID.
- [x] Ambiguous POST timeout/transport/server failure keeps submission controls locked and explicitly says status unknown, not safely failed. No automatic POST retry or fake cancellation.
- [x] Concurrency guard covers submit handlers, sample, snapshot picker, URL editing, check-again. Previous review remains present on recheck failure.
- [x] Session-only storage contains either an opaque submission-pending flag/start timestamp or opaque job ID/start timestamp; restores known jobs regardless of age by polling, never resubmitting. Unknown submissions retain their lock across reload without expiring into permission to submit. No URL, snapshot, image, or survey content stored.
- [x] Live region sits outside panel aria-busy; only changed stage/error announcements, never ticking timer announcements. No focus moved on polling. Failed jobs have no current step. New jobs clear old image even before POST returns.
- [x] Terminal completion renders ready and redirects directly without artificial delay or redundant terminal GET.

## Verification
` .venv/bin/python -m pytest tests/test_home_page.py tests/test_loading_progress.py tests/test_workflow_e2e.py -q `

Initial: **15 passed**, 1 existing Starlette/httpx deprecation warning, 11.09s. Reload-safety follow-up final: **19 passed**, same existing warning, 12.73s. JS syntax and diff checks remain clean.

Synthetic browser coverage: held POST; held first GET; ambiguous POST timeout; GET timeout/recovery; repeated HTTP errors/pause/resume; reload restores same job; stale captures despite fresh responses; queued/failed/completed stages; safe literal error text; new job clears image; reduced motion; keyboard activation/resume; mobile 320px overflow; failed recheck preserves old phone workspace. Timing uses Playwright page.clock rather than long sleeps.

Regression run first exposed two old contracts assuming three stages (including invented “Save review”). Updated only stage counts for the new actual four-step flow; rerun green. New lifecycle tests passed on their initial run; no claim of full pre-implementation TDD.

`node --check` passes both changed JS files; `git diff --check` clean. All changed code files <600 lines. Initial custom muted status contrast was 6.50:1; the integration follow-up below replaces these custom colors with shared foundation-token aliases.

No live vendor requests, live model calls, external browser jobs, full suite, deployment, or push. The existing local FakeProvider fixture supplies one sample review for the recheck regression test. Default `python` lacked pytest; attempted uv environment resolution failed DNS; all actual checks then used the existing `.venv` (no new dependencies).

## Integration follow-up
Preserves the three fixes and regression evidence from commit **e4c50e9**.

Reproduced the integration failures first: start-review tests failed four strict selectors because exact error detail appeared in both live status and panel; design-token tests failed the literal component colors and decorative gradient. Fixed without changing `tests/test_design_tokens.py` or `tests/test_start_review_e2e.py`:
- `design-system.css` defines `--read-*` semantic aliases using existing palette, surface, boundary, frame and shadow tokens. Component CSS uses only those tokens and a flat background. No new hardcoded component colors, gradient, or glass.
- Error detail has one source of truth: the existing live status. Panel gets a generic attention/reconnection headline, not repeated detail. Failed render paths update that same status once; workflow suppresses unchanged announcements instead of re-writing the same text. Regression assertions check exact error occurs once and no duplicate live region appears in the error panel.
- POST-timeout test waits until submission-pending storage is written before advancing its deadline. Three isolated reruns passed (1.63s, 1.22s, 1.01s).

Requested combined run: `.venv/bin/python -m pytest tests/test_loading_progress.py tests/test_home_page.py tests/test_start_review_e2e.py tests/test_design_tokens.py tests/test_workflow_e2e.py -q`: **33 passed**, one existing Starlette/httpx warning, 16.13s. Both JS syntax checks and diff check pass. No full suite, live/vendor calls, backend edits, delegation, or push.

## Loading-review follow-up (three requested fixes)
- Accepted records no longer expire. A three-hour-old ID is restored and GET-verified with submission controls locked. HTTP 404 becomes explicit manual uncertainty, retaining the ID and lock; Resume only rechecks that same ID. Only observed completed/failed status clears it. Unknown submission markers likewise have no timer expiry.
- Capture-count observation age is now recomputed by the panel clock during stalled responses and paused/error checking. Text explicitly says this page observed the count, not that the server captured it at that time. It is not a live announcement.
- Reader steps are shown only with reader evidence (`stage:reading` or a positive captured count). Sample/snapshot running jobs without reader stages use neutral supplied-content/checking steps, no opening-test-site claim or promised capture. Immediate initial and restored placeholders are neutral, and persisted record shape is unchanged (no job-kind field).

TDD: added three synthetic regressions before implementation; all three failed for the reported reasons. Implemented fixes and reran loading/home/workflow tests: **22 passed**, one existing Starlette/httpx warning, 16.53s. JS syntax and diff checks clean. Old-record test covers running, 404 uncertainty, and terminal verification; clock test advances 45s stalled +15s paused without rendering another job; sample and snapshot tests intercept both jobs and assert neutral stages before and after reload. Timer assertions allow a one-second scheduling boundary, rather than brittle exact-second text.

No full suite, live/vendor/model calls, delegation, backend edits, or push. Existing shared-test-string failures from the parent's full suite are outside this fix scope.

## Reload-safety follow-up
The ambiguous pre-ID reload gap is closed without backend changes. Before POST, a single sessionStorage key is written with `{submissionPending:true, started}`. A known acceptance atomically overwrites that same key with `{jobId, started}` (no remove/write gap). Explicit client rejection clears it; transport errors, POST timeout, invalid/missing job references and server uncertainty retain it. Reload before acceptance or after timeout restores the lock and says:

> Request status unknown. A test response may already exist. Check My surveys or contact the local pilot owner to verify the request. Do not submit again while it may be running. No job reference was received, so this page cannot resume status checks.

There is no guessed job reference, Resume button, GET to an invented ID, repeated POST, or auto-expiry that could falsely authorize a duplicate. The existing readonly My surveys list remains accessible but is not used to guess which job belongs to the unknown request. If sessionStorage is unavailable, submission still works in the current page, a visible status warns that recovery after reload is unavailable, and terminal jobs unlock normally. No persistent block is created from a storage exception.

TDD follow-up: added failing browser tests first: pre-response reload/retained lock failed (no marker), and unavailable-storage warning failed (missing warning). Implemented marker handling, then green. Extended coverage includes timeout then reload, repeated reload beyond known-job TTL, explicit 422 clearing, atomic transition to accepted metadata, and successful in-page terminal handling with storage blocked. Existing accepted-job reload regression remains green. No backend, vendor, live AI, full suite, delegation, or push.
