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
- Recognize only structural, non-add-answer candidates on a uniquely located captured choice question, with nonempty lines and an unchanged captured stem or at least one unchanged answer. Blank-line/prose/ungrounded bundles remain verbatim; unmarked multiline wording remains a wording diff. This intentionally favors safe fallback when all captured wording changes.
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

## Boundaries

No delegation, live survey/external browsing, real database, deployment, push, or server/reader edits. Tests use the existing ephemeral static localhost fixture and synthetic intercepted API responses; actual clipboard assertions run in Chromium. No visual screenshot evaluation or manual aesthetic claims made; automated semantic/keyboard/no-overflow assertions at1280 and390px only. Other worker's signals/overview/data, staged progress, and parent plan excluded. Parent should independently review the conservative recognition rule and perform final integration/full nonlive validation.
