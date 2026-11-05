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
- [x] Session-only storage contains either an opaque submission-pending flag/start timestamp or opaque job ID/start timestamp; restores reasonably recent known jobs (<2h) by polling, never resubmitting. Unknown submissions retain their lock across reload without expiring into permission to submit. No URL, snapshot, image, or survey content stored.
- [x] Live region sits outside panel aria-busy; only changed stage/error announcements, never ticking timer announcements. No focus moved on polling. Failed jobs have no current step. New jobs clear old image even before POST returns.
- [x] Terminal completion renders ready and redirects directly without artificial delay or redundant terminal GET.

## Verification
` .venv/bin/python -m pytest tests/test_home_page.py tests/test_loading_progress.py tests/test_workflow_e2e.py -q `

Initial: **15 passed**, 1 existing Starlette/httpx deprecation warning, 11.09s. Reload-safety follow-up final: **19 passed**, same existing warning, 12.73s. JS syntax and diff checks remain clean.

Synthetic browser coverage: held POST; held first GET; ambiguous POST timeout; GET timeout/recovery; repeated HTTP errors/pause/resume; reload restores same job; stale captures despite fresh responses; queued/failed/completed stages; safe literal error text; new job clears image; reduced motion; keyboard activation/resume; mobile 320px overflow; failed recheck preserves old phone workspace. Timing uses Playwright page.clock rather than long sleeps.

Regression run first exposed two old contracts assuming three stages (including invented “Save review”). Updated only stage counts for the new actual four-step flow; rerun green. New lifecycle tests passed on their initial run; no claim of full pre-implementation TDD.

`node --check` passes both changed JS files; `git diff --check` clean. All changed code files <600 lines. Muted status color #465f5a against darkest panel background #f2faf6 calculates **6.50:1** contrast.

No live vendor requests, live model calls, external browser jobs, full suite, deployment, or push. The existing local FakeProvider fixture supplies one sample review for the recheck regression test. Default `python` lacked pytest; attempted uv environment resolution failed DNS; all actual checks then used the existing `.venv` (no new dependencies).

## Reload-safety follow-up
The ambiguous pre-ID reload gap is closed without backend changes. Before POST, a single sessionStorage key is written with `{submissionPending:true, started}`. A known acceptance atomically overwrites that same key with `{jobId, started}` (no remove/write gap). Explicit client rejection clears it; transport errors, POST timeout, invalid/missing job references and server uncertainty retain it. Reload before acceptance or after timeout restores the lock and says:

> Request status unknown. A test response may already exist. Check My surveys or contact the local pilot owner to verify the request. Do not submit again while it may be running. No job reference was received, so this page cannot resume status checks.

There is no guessed job reference, Resume button, GET to an invented ID, repeated POST, or auto-expiry that could falsely authorize a duplicate. The existing readonly My surveys list remains accessible but is not used to guess which job belongs to the unknown request. If sessionStorage is unavailable, submission still works in the current page, a visible status warns that recovery after reload is unavailable, and terminal jobs unlock normally. No persistent block is created from a storage exception.

TDD follow-up: added failing browser tests first: pre-response reload/retained lock failed (no marker), and unavailable-storage warning failed (missing warning). Implemented marker handling, then green. Extended coverage includes timeout then reload, repeated reload beyond known-job TTL, explicit 422 clearing, atomic transition to accepted metadata, and successful in-page terminal handling with storage blocked. Existing accepted-job reload regression remains green. No backend, vendor, live AI, full suite, delegation, or push.
