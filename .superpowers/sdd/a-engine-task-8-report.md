# Part A Task 8 — enrichment wiring

## Checklist
- [x] RED: payload, ordering, carry-over and immutability contract tests
- [x] GREEN: shared read-time enrichment for detail, demo and example
- [x] Focused and full suites; inspect diff and file sizes
- [x] Commit prepared: `Attach screens, plan and overview to every review payload`

## Design
Presentation must run before round comparison/change sheets; plan and overview must
run after final validated and carried decisions. Stored evidence is never enriched.

## Implementation
- `present.enrich` returns a deep detached copy with screens, presented findings,
  plan and overview. Repeated enrichment produces identical output. Pending
  payloads get screens only; no assessment is fabricated.
- Repository presents guarded findings before comparison, validates decisions,
  merges carry-over with explicit current overrides, then enriches once curation
  has its final decisions. Change sheets skip absorbed children, while review
  evidence and round history retain them and their original severity.
- Offline demo and worked example use the same enrichment function. The demo now
  includes fingerprints and assessed `results`, so signals/strengths use real
  retained evidence rather than inferring passes from a checked-criteria list.
- Worked example persists its raw evidence only and returns detached enrichment;
  later GET requests still use the normal repository projection path.
- Regenerated `site/data.js` offline. Compact ASCII serialization keeps this
  generated artifact below 600 lines without splitting one cohesive dataset.

## Verification
- Initial focused RED: **5 failed**, expected missing enrichment contract.
- Full RED: **5 failed, 810 passed, 1 skipped** (151.25s). An initial full run
  exceeded the 120-second tool timeout; rerun completed with a 600-second limit.
- Added compact-bundle regression: RED at 4180 lines, then GREEN after compact
  serialization. No existing safety assertion was weakened or replaced.
- Final focused command: `.venv/bin/python -m pytest -q
  tests/test_enrich_contract.py tests/test_demo_export.py tests/test_present.py
  tests/test_plan.py tests/test_signals.py tests/test_stale_pick.py
  tests/test_review_projection.py tests/test_committee_rounds.py
  tests/test_backend_review_evidence.py` — **160 passed**.
- Full command: `.venv/bin/python -m pytest -q` — **816 passed, 1 skipped**
  (165.27s). Existing Starlette/httpx deprecation warning only.
- Contract tests cover temp-DB sample GET, offline demo, worked-example raw
  persistence, detached/idempotent enrichment, effective survey type, pending
  reviews, presented round entries, absorbed sheet exclusion, final carry-over,
  current reopen overrides, reasonless keep remaining open, immutable DB reads,
  and no change-sheet copy before a choice.

## Scope / concerns
- No delegation, worktree, push, external/live provider calls or live DB access.
  Only temporary test DBs and committed offline model caches were used.
- Protected `review/` and `uglyhome.png` were pre-existing untracked items and
  remain untouched. No migrations, scoring changes or browser/UI changes.
- No blockers. Existing dependency warning remains out of scope.
