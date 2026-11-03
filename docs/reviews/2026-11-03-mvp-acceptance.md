# MVP candidate acceptance, 2026-11-03

## Delivered and exercised
- Trust regressions: failed AI parts cannot approve; duplicate model decision IDs rejected; scoped rewrites; no-op preview; keep-original copy behavior; prompt boundaries.
- Local FastAPI/SQLite workflow: immutable review-input versions, persistent decisions/reasons/manual done, async review and reader jobs, failed-job preservation, background interruption recovery, same-origin writes and bounded JSON.
- My surveys, file-free synthetic trial, snapshot import, approved link intake, grouped work list/copy-all, preview integration, Ask, new-version comparison and escaped summary export.
- Safe bounded reader against synthetic local survey zoo; passive definition extraction from allowed GET payloads. Captured PNGs available through position-only routes; no arbitrary filesystem serving.
- Reordered-save regression, metadata-only image fix version regression, stale AI/local attempt regression, unknown rewrite rejection.

## Verification
- Full suite: **411 passed, 1 skipped**. One dependency deprecation warning (Starlette TestClient/httpx).
- Chromium acceptance: snapshot import → explicit choice+reason → reload persistence → phone preview → updated import → version comparison, at 390px; no page errors/sideways overflow.
- Existing demo browser tests pass. Demo export replay stays offline and unchanged.
- Independent QA: private home readable at 320/390/1280, no horizontal overflow, visible keyboard focus, accessible labels, empty submit status. No axe runtime available to that agent; not a new full WCAG certification.
- Actual Wibey on synthetic Coffee Pods: wording/story/flow completed, no failed batches, no findings; two image judgments remain unchecked. No real survey sent.
- Independent review found decision ordering, incomplete version identity, late review publication, invalid picked text, and missing local navigation; reproduced with tests and fixed.

## Explicitly NOT accepted as complete
- Real RedJade compatibility has not been exercised in this build. Vendor/test-participant prerequisites and approved clean preview URL are required. No live survey was crawled during development.
- External answer writes/Next clicks remain disabled. Initial state or passive known definition only. Query/token links/authentication are not supported; unknown types/locales/coverage must remain explicit.
- No complete path/visual/image verification. Phone remains reconstructed. Actual captures are only visited viewports.
- Version comparison says newly/still/no-longer flagged; it does not certify resolution when checks are incomplete.
- Director-graded 20–30 survey accuracy calibration remains a pilot gate.
- No hosted authentication/multi-user support; loopback service only. Cross-tab decision conflict handling is last-arrival-wins (same-page stale writes protected).
- Capture retention is operator-managed; snapshots and summary packets contain survey wording and belong in approved internal storage.

## Product conclusion

Substantial working local MVP candidate, ready for synthetic/local workflow testing. Do not equate passing tests with successful real-survey ingestion or research validity. Full owner-described MVP acceptance still requires an approved real-survey pilot and research validation. Public Pages is still the synthetic static demo.
