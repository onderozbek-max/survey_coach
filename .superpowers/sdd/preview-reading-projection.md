# Preview reading projection — coordination contract

Owner: code-puppy-225113. Scope: site/energy.js + tests/test_preview_reading_projection.py only; this report.

## Backend coordination request (needed for numeric evidence)

Please export canonical reading basis on each serialized snapshot page as:

```json
{"reading_basis": {"seconds_per_word": 0.3, "fields": [
  {"text": "Canonical unique concept prose"},
  {"text": "Question text", "question_id": "q1"},
  {"text": "Help text", "question_id": "q1"},
  {"text": "Answer label", "question_id": "q1"}
]}}
```

Fields must come from the same backend canonical projection used by timing (page-local exact overlap subtraction; include all actually counted option/row/scale reading). Keep independent fields separate to preserve scoped replacements and unselected options. Page-level prose must not acquire question scope. Do not mutate original capture text. `seconds_per_word` should come from timing constants, not a second JS constant.

Frontend uses only that basis for its numeric delta; legacy pages without basis return null (unavailable evidence, NOT a zero-change claim), never sum redundant raw + structured captures. Existing numeric comparison remains useful with backend-provided evidence; no separate JS dedup algorithm.

## Results

- Replaced raw/intro/question summing with backend-owned canonical fields + reading rate. No JavaScript deduplication algorithm and no second timing constant.
- Preserved numeric improvement, including dropdown/grid option evidence, independent concept prose, question/page scope, legitimate repeated phrases, and negative deltas for longer copy.
- Added `SC.previewReadingEvidence(page, plan)` for truthful available/unavailable comparison wording.
- TDD: initial run 12 failed / 1 passed; duplicate raw+intro case returned 5 seconds versus 2 for identical structured-only content. Green: 17 passed in 1.49s. Node syntax and named-path diff whitespace checks passed.
- Tests run actual existing model.js/applyFixes and energy.js in Node, with a JS-side immutability assertion. All content synthetic; no browser/live surveys, full suite, pushes, or delegation.

## Integration REQUIRED by parent / backend owner

1. Backend: export the `reading_basis` contract above into each detail.snapshot.pages entry, from the same canonical fields used by timing. Current tests isolate frontend consumption; they do NOT prove backend export exists yet.
2. UI owner: app.js line ~253 currently computes Math.abs(SC.previewReadingDelta(...)) inline. Replace the comparison paragraph content with `SC.previewReadingEvidence(item.page, previewPlan(true))`. Otherwise `Math.abs(null)` misleadingly displays 0 for old reviews. app.js was explicitly outside my owned files, so I did not edit it.
3. Add cross-layer backend fixture/export integration coverage once producer is wired. This isolated commit is NOT an independently shippable end-to-end change without steps 1–2.

Only changed owned paths: site/energy.js, tests/test_preview_reading_projection.py, and this report. No unrelated UI changes.
