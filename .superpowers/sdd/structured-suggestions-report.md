# Task 2 — Structured recommendations

Owner: code-puppy-0807de. Parent owns final independent review/integration.

## Checklist
- [x] Inspect actual structural contract/schema and current coach/model.
- [x] Add focused failing synthetic browser tests before production edits.
- [x] Implement semantic question/answers and conservative fallback.
- [x] Verify targeted Improve/phone/stale/copy and broader workspace regressions.
- [x] Check owned source sizes/diff; commit named owned paths only.

## Implementation

- New `site/suggestion.js` exports `SC.bundleParts` and `SC.renderSuggestion`.
- Inspected `surveycoach/judge/prompts.py`: known format is question on first line, one answer per subsequent line. `judge/grounding.py` marks **any** multiline candidate structural, so the flag alone cannot establish question/answers.
- No existing `SC.bundleParts` or equivalent JS model parser existed at task start. Reused existing `SC.renderDiff`, `SC.h`, and original/choice model paths rather than duplicating them.
- Recognize only structural, non-add-answer candidates on a uniquely located captured choice question. Following independent review, partial stem/answer overlap is no longer sufficient: changed answers require exact explicit `Question: …`, `Answer choices:`, and `- …` list-line syntax; legacy unlabelled candidates require the complete captured answer sequence unchanged and in order. All other multiline structural candidates remain verbatim. Unmarked wording remains a wording diff; no punctuation/sentence heuristics.
- Recognized bundles show Question and Answer choices headings, the proposed question alone, and a semantic named `ul`/`li` list. They do not interleave deleted answers into the proposed list. Existing Details → Original remains the discoverable complete old wording/answers, now preserving line breaks visibly.
- Plain wording retains the existing word-level diff. Add-answer retains its existing action heading plus explicit Answer choice label, without presenting/replacing the question.
- Alternative switches rerender presentation using the selected text. Copy/save handlers and `choice.text` remain untouched (including whitespace/CRLF); no persistence migration, preview changes, fingerprint changes, or text reconstruction.
- All content uses existing text-node DOM helper (no HTML interpretation). Token-only existing styles, mobile wrapping, native keyboard-operated alternatives/Details.
- Script wired before coach in both demo `index.html` and saved-review `review.html`.

## Verification (exact runs)

Initial `python -m pytest tests/test_structured_suggestions_ui.py -q` could not start because global Python lacks pytest; used existing `.venv` thereafter (no dependency installation).

RED:
- `.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py -q` timed out at 120s, partial `FFF.FFF.` due to missing expected locators.
- `.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py -xq` → **1 failed**, expected missing Question heading (0 vs 1), 1.26s.

First implementation run:
- `.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py -q` → **9 passed, 1 failed**, 2.91s. The malicious fixture changed all captured wording and correctly took conservative fallback; corrected fixture to retain Vanilla so it specifically exercises structured escaping rather than the separate fallback contract.

GREEN targeted:
```sh
.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py tests/test_improve_ui.py tests/test_improve_navigation_ui.py tests/test_improve_safety_ui.py tests/test_answer_addition_ui.py tests/test_answer_additions.py tests/test_phone_preview.py tests/test_phone_first_workspace.py tests/test_with_fixes_preview.py tests/test_copy_guard.py tests/test_copy_deck.py tests/test_clean_copy.py tests/test_stale_pick.py tests/test_issue_loop_ui.py tests/test_design_tokens.py -q
```
**112 passed in 22.86s.** Includes all 10 new cases: desktop/mobile semantic structure, original removals, keyboard alternatives + stale pick + exact CRLF clipboard/persisted text, plain wording diff, add-answer exact text, four ambiguity/fallback cases, malicious string escaping/copy.

Broader related (not full suite):
```sh
.venv/bin/python -m pytest tests/test_site_e2e.py tests/test_share_ui.py tests/test_share_state_ui.py tests/test_final_races_ui.py tests/test_final_fixes_ui.py tests/test_ui_primitives.py tests/test_workspace_decisions.py tests/test_workspace_contracts.py tests/test_workflow_e2e.py tests/test_unified_workspace.py -q
```
**122 passed, 1 warning in 30.27s.** Warning: existing Starlette TestClient/httpx deprecation.

`git diff --check` clean. Owned source line counts: coach89, suggestion35, CSS113, index55, review58; new test122. No file approaches600.

## Independent review fixes (two P2s)

Read `.superpowers/sdd/structured-suggestions-review.md`. Both reported cases fixed in owned `site/suggestion.js`, with regressions in the existing owned test file; no other source paths changed in this follow-up.

1. Removed partial-overlap classification. Added exact review examples (original stem plus authoring instruction; one answer plus explanatory prose), an additional partial-overlap variant, changed unlabelled answers, and malformed explicit-label variants. Changed-answer positive fixtures now explicitly label the Question and Answer choices and mark each list item. Added an unchanged-complete-answer legacy positive case. This intentionally sacrifices automatic formatting for ambiguous unlabelled answer edits; no typed server schema or persistence was introduced.
2. Selected single-line candidates now receive `SC.renderDiff` even if another alternative sets the finding-wide structural flag. Shared captured-question lookup supplies the original stem, not `originalOf`'s expanded answer bundle. Keyboard mixed-alternative test checks only try→buy is diffed, answers are absent from the diff, and exact copied/persisted text is unchanged.

Exact follow-up red/green runs:
- Before production edits, `.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py -q` → **4 failed, 9 passed in 2.95s**: all three partial-overlap prose variants wrongly produced lists, and mixed alternative had no diff.
- After updating positive fixtures to require explicit labels and adding complete-answer legacy coverage, before production edits, `.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py -q --tb=no` → **8 failed, 6 passed in 33.34s** (includes unsupported explicit-format assertions).
- After parser/diff fix, `.venv/bin/python -m pytest tests/test_structured_suggestions_ui.py -q` → **14 passed in 3.38s**.
- Added three additional conservative fallback guard cases, then reran the **same exact targeted command above** → **119 passed in 23.71s** (17 structured suggestion cases).
- Reran the **same exact broader-related command above** → **122 passed, 1 warning in 30.53s**. Existing Starlette/httpx warning remains. Shell also emitted a partial ephemeral static HTTP fixture request-handler exception during teardown; both pytest processes exited0, no failed test. No full-suite run.

Follow-up `git diff --check` clean. Parser47 lines; tests158 lines. Only parser, owned tests, and this report in follow-up commit. Existing staged progress untouched. All verification remains synthetic browser assertions, not visual design judgment.

## Generation contract integration — reviewer notification

Parent identified that generation still requested the legacy unlabelled bundle. Reviewer: please review the prompt-generation contract alongside the conservative parser fixes, rather than treating UI-only explicit-format fixtures as proof of generated-format alignment.

Read actual `judge/prompts.py`, `judge/grounding.py`, `judge/schemas.py`, `recommendations.py`, and prompt/grounding tests before editing. No existing typed question/answer discriminator exists in `AiFinding`; no speculative schema field added.

- `surveycoach/judge/prompts.py` now instructs question-plus-answer rewrites to use exact `Question: …`, `Answer choices:`, and `- …` lines in suggested_text and applicable option.text. Single-line question rewrites stay plain. Missing-answer additions explicitly retain the old unlabelled first-line-question/one-answer-per-line contract consumed by `answer_edits.py`. No change to that normalization.
- Prompt cache version bumped8→9, so old generation-cache keys do not masquerade as new-format output.
- Existing grounding already accepts this format unchanged, derives structural=true from newlines, and prevents phone substitution. No production grounding change needed. New synthetic integration exercises schema validation → ground/guard → intercepted UI rendering → actual clipboard and decision payload assertions, including changed question and removed answer. Plain generation still yields a diff; missing-answer generation still yields add_answer.
- No server/reader/persistence migrations or copy reconstruction. Explicit labels/bullets remain exactly in saved/copied text. Historical ambiguous unlabelled changed-answer bundles intentionally retain honest flat fallback.

TDD exact runs:
1. Before prompt edit: `.venv/bin/python -m pytest tests/test_judge_prompts.py -q --tb=short` → **1 failed, 16 passed in0.23s**, missing exact explicit-format example. Regression also checks plain/missing-answer instructions and version change.
2. After prompt edit plus synthetic grounding/UI integration (no LLM):
```sh
.venv/bin/python -m pytest tests/test_judge_prompts.py tests/test_judge_grounding.py tests/test_structured_generation.py tests/test_structured_suggestions_ui.py tests/test_answer_additions.py tests/test_answer_addition_ui.py tests/test_judge_schemas.py tests/test_judge_run.py tests/test_recommendation_quality.py -q
```
→ **114 passed in6.45s**. Expanded integration to changed-stem and plain generation; final same command → **115 passed in6.85s**.

`git diff --check` clean; prompt135 lines, prompt tests139, new integration tests75. Only prompt, prompt tests, new integration tests, and this owned report in contract follow-up commit. No fullsuite/delegation/live/push. Parent's concurrent fullsuite may have started before these prompt changes; rerun final integration gate after this commit. This report is the reviewer handoff; no delegated review initiated.

## Synthetic worked-example Q1 producer update

Read README (two made-up surveys, reviewed synthetic AI cache, offline export), `surveycoach/demo_export.py` (CacheOnlyProvider, pinned exact fixture hashes), the named cache fixture, existing demo export tests, and generated bundle before edits. Confirmed `bb2f6eed757f0750e04e879bef7ce59e.json` is intentionally synthetic demo content, not a private user review.

Changed **only Q1/B2 suggested_text and its three option.text values** in that named fixture to explicit `Question: …\nAnswer choices:\n- …` format. Original current_text, evidence, labels, all other findings/verdicts/blockers remained identical (asserted with parsed before/after dictionaries). Q4 remains historical/unlabelled. Regenerated `site/data.js` using `.venv/bin/python -m surveycoach.demo_export` with no --ai-refresh; exporter cannot call network on this path.

New `tests/test_demo_structured_suggestions.py` verifies fixture and exported Q1 preserve original text/options exactly, then actual synthetic review UI exposes labelled Question and answer list and saves/copies the exact fixture suggestion.

TDD and related checks:
- RED `.venv/bin/python -m pytest tests/test_demo_structured_suggestions.py -q --tb=short` → **2 failed in1.70s**, missing fixture Question label and rendered Question heading.
- GREEN `.venv/bin/python -m pytest tests/test_demo_structured_suggestions.py tests/test_demo_export.py tests/test_structured_generation.py tests/test_structured_suggestions_ui.py tests/test_judge_prompts.py tests/test_judge_grounding.py -q` → **82 passed in6.93s**.
- Broader affected demo/UI `.venv/bin/python -m pytest tests/test_improve_ui.py tests/test_issue_loop_ui.py tests/test_site_e2e.py tests/test_phone_preview.py tests/test_answer_addition_ui.py tests/test_share_ui.py tests/test_copy_guard.py tests/test_stale_pick.py -q` → **87 passed in24.16s**.
- Named-path `git diff --check` clean. New test49 lines; fixture195 lines, generated bundle1 line; all below600.

Commit scope: named fixture, regenerated site/data.js, new demo contract test, this report only. Existing progress/other artifacts untouched. No real DB/external/live/push/fullsuite. Parent should restart the isolated preview **after this producer commit** and perform final integration gate. Existing saved historical real reviews are NOT relabelled or migrated; obtaining new generated labels requires a new review. This demo change is not evidence a live LLM followed the new prompt or a real survey was read.

## Boundaries

No delegation, live survey/external browsing, real database, deployment, push, or server/reader edits. Tests use the existing ephemeral static localhost fixture and synthetic intercepted API responses; actual clipboard assertions run in Chromium. No visual screenshot evaluation or manual aesthetic claims made; automated semantic/keyboard/no-overflow assertions at1280 and390px only. Other worker's signals/overview, staged progress, and parent plan excluded. The final explicitly assigned synthetic producer follow-up owns regenerated site/data.js only, as documented above. Parent should independently review the conservative recognition rule and perform final integration/full nonlive validation.
