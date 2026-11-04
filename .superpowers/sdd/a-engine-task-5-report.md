# Part A Task 5 report — survey style

Base: `82a5a77` on `feature/surveycoach-mvp`.

## Checklist
- [x] Read Task 5 brief first; inspect existing model, checks, projection, API and jobs.
- [x] Write all focused tests before production changes; observe RED.
- [x] Add `community_pulse` model/rubric support (5–8 minute targets).
- [x] Keep community emoji with words; flag emoji-only answer labels accessibly.
- [x] Allow isolated caps emphasis in community style; retain CAPS_RUN and multiple-word warnings.
- [x] Add community judge rule; bump prompt version 7 → 8.
- [x] Migrate only nullable survey-level style metadata; keep rename compatibility.
- [x] Support validated title/style PATCH updates and effective style in detail/list/jobs.
- [x] Run focused and full verification; commit using prescribed message.

## Implementation

`surveys.survey_type` is an optional override. Detail and list expose the effective
`survey_type` and `survey_type_chosen`; projection, screen labels, recommendation
guards and review jobs use an effective copy. The raw snapshot stays unchanged.
Existing `Repository.rename()` delegates to `update()` and retains its title-only
response. PATCH still supports title-only callers and rejects empty/invalid updates.

The AI cache key now includes style: content_hash deliberately excludes survey
style, so prompt-version invalidation alone would not prevent a subsequent style
change from replaying a different voice's cached assessment. No model override.

There is no `enrich()` implementation at this base (later task); none was invented
here. Existing projection entry points use effective style. Historical AI evidence
continues to be retained as before; changing metadata does not silently rerun AI.

## Tests

- RED: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q tests/test_survey_style.py`
  → **12 failed, 1 passed** (missing type, PATCH support, update and rubric).
- GREEN focused: style/content/API/prompts/judge-run/projection files → **70 passed**.
- Strengthened list test to require a changed score matching detail, not merely
  unchanged-score equality; style file → **13 passed**.
- Final full: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q`
  → **748 passed, 1 skipped**, 147.26 seconds.
- Existing default emoji tests unchanged. No existing assertion weakened.
- SQLite tests compare all raw versions/reviews/decisions rows before/after style
  and title PATCHes, including stored review JSON bytes. Actual schema column is
  `reviews.data`, not the brief's `reviews.result`.
- Temporary databases only; legacy metadata migration/reopen, rename, invalid
  requests, missing IDs, provider effective-style input and cache isolation covered.

## Constraints / concerns

No live DB opened, no external/model calls, no delegation/worktree/push. Protected
`review/` and `uglyhome.png` were already untracked and remain untouched/untracked.
All changed files are under 600 lines. Known environment warning remains:
Starlette TestClient's httpx deprecation (unrelated dependency change deferred).
The single skipped test is the opt-in real-model test.
