# Review polish — Tasks 2 + 3

Owner: code-puppy-b9bdb8. Local branch feature/surveycoach-mvp; requested base e4b1cf3.

## Done
- [x] Read actual Review.results / CheckResult and existing scorecard schema before projecting.
- [x] Pure weighted quality projection; canonical enrich/list/report/demo wiring.
- [x] Restrained Overview card, compact Home/header/Share, self-contained downloads.
- [x] Shared native methodology/energy dialog with tap, keyboard, Escape, focus return, route close and unique IDs.
- [x] Survey style below title before assessment, preserving update/refetch behavior and stating saved AI advice is not rerun.
- [x] Energy assumptions serialized from TimingConstants, including question-kind base/option table and route limitations.
- [x] Offline demo exporter, claims guard regression, focused and broad related tests.

## API contract (additive; existing raw scorecard preserved)
`build_quality(review: dict, rubric: Rubric) -> dict` reads `review.results`, keyed by rubric criterion/blocker ID. A CheckResult has `criterion_id`, `fraction: float|null` (0..1), `applies: bool=True`, `assessed: bool=True`, and `findings: list`. Blockers use must_fix findings, not fractions (a successfully assessed blocker can have null fraction).

Top-level `quality` is emitted by canonical `enrich`, detail endpoints, `/api/surveys` list items, and both synthetic demo entries. Fields:
- `score: float|null`: exact sum(weight × assessed fraction) / sum(assessed applicable weight) × 100. Null when assessed weight is zero. No intermediate rounding.
- `earned_points: number`, `assessed_points: int`, `applicable_points: int`, `unchecked_points: int`.
- `coverage_percent: float`: assessed/applicable × 100, zero if no applicable weight.
- `provisional: bool`: no assessed weight, unknown applicable weight, or unverified blocker checks.
- `dimensions: list[{id,name,earned_points,assessed_points,applicable_points,unchecked_points,score}]`, same normalized calculation per rubric dimension.
- `blockers: {flagged:int, unchecked:int, total:int}`. Flagged counts rubric blocker checks containing must_fix evidence independently of decisions; unchecked includes missing or unassessed applicable blockers.
- `basis: "Earned assessed applicable points / assessed applicable points × 100."`
- `method_version: "assessed-weight-normalized-v1"`, `rubric_version: str`.

Explicit N/A excludes weight; absent results remain unknown. Zero-point criteria excluded. Rubric weights are not duplicated. Projection ignores old scorecard values, curated findings counts, and picks/keeps. Detail still follows the existing current-code + retained assessed-AI read projection; no stored evidence mutation. Listing retains legacy `score_checked` for compatibility but UI uses `quality`.

`effort_method` on enriched detail/demo is `dataclasses.asdict(TimingConstants())`: `seconds_per_word`, `page_overhead`, `image_seconds`, `grid_row_seconds`, four cumulative fatigue thresholds, and `kind_base` triples. Browser displays these rather than redefining thresholds. No endpoint/schema migration required.

Downloads use report.py (there is no server/summary.py in this repo). Both summary routes contain quality and dependency-free `<details>` methodology. Display rounding matches JS Math.round including .5 ties; stored projection retains full float precision.

## Test evidence
1. RED `.venv/bin/python -m pytest tests/test_quality.py -q`: missing quality module caused collection ImportError. After module implementation, 6 passed. Additional canonical API/list/download/effort regression then failed specifically on missing detail.quality; wiring made it green.
2. RED `.venv/bin/python -m pytest tests/test_quality_ui.py -q`: 3 failed because quality card absent. GREEN combined quality + UI: 10 passed.
3. Related initial sweep: 173 passed.
4. Extra Home/reopen/route/sample-header + copy guard/deck: 29 passed.
5. Added actual temp-DB pick/keep invariance contract. Broad run: 232 passed.
6. RED half-point download/browser consistency regression: expected 83/100 but got 82/100. Fixed report display rounding.
7. Final exact broad command:

```sh
.venv/bin/python -m pytest tests/test_quality.py tests/test_quality_ui.py tests/test_overview_ui.py tests/test_home_page.py tests/test_share_ui.py tests/test_share_state_ui.py tests/test_chapters_ui.py tests/test_enrich_contract.py tests/test_present.py tests/test_demo_export.py tests/test_summary_download.py tests/test_copy_guard.py tests/test_copy_deck.py tests/test_design_tokens.py tests/test_scoring.py tests/test_review_projection.py tests/test_survey_style.py tests/test_stale_pick.py tests/test_backend_review_evidence.py tests/test_server_contracts.py -q
```

**233 passed, 1 warning in 28.42s**. Warning is existing Starlette/httpx TestClient deprecation. Browser tests use installed native Chromium, intercepted synthetic detail, or temp synthetic SQLite only; mobile width390 and desktop1280 tested. Tested focus cycling, Escape, repeated reopen, route-change close, duplicate IDs, score context on all interactive surfaces, null/provisional state, real style persistence existing regression, no horizontal overflow and no writes in explanation tests.

`git diff --check`: clean. `node --check` on quality.js, overview.js, share.js, workflow.js, app.js: clean. All changed source files below600 lines (largest app.js391, repository.py320). `.venv/bin/python -m surveycoach.demo_export` used only pinned offline cache, no --ai-refresh. Claims guard remains active with unchanged forbidden patterns/source scope; added explicit approved-score allowance regression proving adjacent `will finish` is still rejected. No broad exemptions or xfails.

## Integration boundaries / limits
No queue, reader/network, parent plan, staged progress, real DB, original images, or screenshots edited by this task. No delegation, live AI, external survey, push, deploy, or freeze workaround. No new screenshots produced. Existing non-LD architecture and token palette retained. Full suite and independent integration review intentionally left to parent. Full UI explanations are native dialogs (click/tap/keyboard); the Energy info control also has a brief hover/focus tooltip, added in the P2/P3 review follow-up below. Existing About-review technical appendix retains legacy raw evidence text; methodology explicitly distinguishes old raw points from normalized quality.

## P2/P3 review follow-up
Read `polish-quality-review.md` and resolved both findings, without modifying scoring/API schema:
- P2: brief `role=tooltip` Energy explanation appears on pointer hover or keyboard focus; trigger has `aria-describedby` referencing its unique tooltip. Focus never opens a modal. Pointer can move onto the tooltip across a continuous hit area; it remains visible until pointer/focus leaves or Escape dismisses. Escape retains trigger focus and suppresses rediscovery until the interaction resets. Tap/Enter still open the full named dialog; opening it hides the tooltip, and closing returns focus without immediately reopening the tooltip. Chapter changes dismiss transient explanation state.
- P3: full formula now says **each question image and each answer option with media adds 3s**, matching `_question_seconds`: `len(question.media) + sum(1 for option in options if option.media)`. The 3s value still comes from serialized `TimingConstants.image_seconds`, not a new UI constant.

TDD evidence:
1. `.venv/bin/python -m pytest tests/test_quality_ui.py -k 'tooltip or touch' -q`: **2 failed, 5 deselected** before implementation (missing hover tooltip and omitted answer-option wording).
2. Same command after implementation: **2 passed, 5 deselected**.
3. Extended hover regression to width390 as well as1280, explicitly checking pointer traversal, focus discovery, Escape suppression, no modal auto-open, Enter opening, focus return, blur dismissal and overflow. This caught mobile tooltip overflow: focused run **1 failed, 47 passed**. Centering tooltip under its info control fixed it using existing tokens only.
4. Final focused command:

```sh
.venv/bin/python -m pytest tests/test_quality_ui.py tests/test_quality.py tests/test_overview_ui.py tests/test_copy_guard.py tests/test_design_tokens.py -q
```

**48 passed, 1 warning in 9.06s** (same existing Starlette/httpx warning). Touch test uses native Chromium mobile390 context with `has_touch=True` and actual `.tap()`, opening/closing full dialog and verifying return focus/no overflow. Synthetic fixtures only. `node --check site/quality.js` and `git diff --check` clean. Source sizes: quality.js92, quality.css24, quality UI tests154 lines. No full suite, delegation, external survey, live AI, push or deployment. Only quality.js/css, quality UI tests and this report included in follow-up commit; staged progress excluded.
