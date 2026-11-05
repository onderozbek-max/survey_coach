# Root-cause prevention and visible review loading

User requests (1) explain and prevent recurring causes behind seven review problems and (2) beautiful transition while reading a pasted RedJade URL. Keep existing non-LD frontend, local only, no vendor rereads.

## Design

Inline progress workspace immediately upon valid submit, before any request resolves. Existing visual tokens; bordered bright surface, atmospheric static/soft-motion phone preview, real captures replacing skeleton, clear actual reading/checking/ready stages. No percentages, invented saving phase, fabricated backend heartbeats or promised durations. Elapsed timer is UI clock, response-age explicitly last confirmed server response. Reduced motion gets static indicators; live announcements only semantic changes, not every tick.

Shared state transitions distinguish submitting, queued/running reading, checking, completed, failed, connectivity uncertainty and safely resumable polling. Never automatically retry POST. No fake cancel. Resume GET for the existing job, never silently create a new participant. Opaque job ID/start-time persistence only; no survey wording/URLs/screenshots in browser storage. Failed preview resets on a new job. Existing recheck review remains intact. Avoid controls enabling duplicate submission while original job still may run. Existing redirects happen without artificial delay.

Root-cause audit follows evidence through shared backend calculations, confidence classification, recommendation contracts and unknown-state handling. Add targeted regression invariants rather than another universal framework; preserve legitimate repeated prose, observations vs proof, known vs unknown and semantic answer distinctions. Explain which adjacent bugs were found and fixed and what remains uncertain.

## Checklist

- [x] Inspect current entry/workflow/status backend and prior fixes; identify first-request feedback gap and unbounded stale polling.
- [x] Backend shared-contract audit: evidence classification, text projections, threshold/copy safeguards; implement proven adjacent bugs with red/green tests.
- [x] UI: test immediate submit, delayed first response, actual stages/capture count, stale/no-new-capture, interrupted connection, failure/completion, reload/resume, no duplicate POST, reduced motion, keyboard and 320px.
- [x] Implement progress component and bounded request/recovery lifecycle, reusable across new review/recheck.
- [x] Independent review, related old tests and full non-live suite, no external survey calls. Full suite: 1327 passed, 1 deselected, 1 existing dependency warning (243.66s). Follow-up clock-rollback regression closes remaining reference-retention edge case; focused verification recorded in loading report.
- [x] Open local page and provide user root-cause explanation, accurate limits and test results. Opened http://127.0.0.1:49307/local.html; no new vendor reads requested.

Workers use isolated named file ownership and commits; preserve pre-existing staged progress and untracked screenshots.
