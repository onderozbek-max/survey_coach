# Recommendation UI clarity

Owner: code-puppy-7e24bc

## Completed
- [x] Action-only findings show their actual explanation prominently as **Recommended action**, without a fake rewrite or duplicate explanation in Details.
- [x] Screen inspection scopes across all plan categories, question IDs, `also_affects`, and `absorbed_by` references.
- [x] Empty states distinguish checks-run/no findings, filtered/category views, saved decisions, and empty categories. No “All 0 must-fixes handled”. Unqueued findings prevent an all-handled claim.
- [x] Compact effort navigation retains visible Low / Building / High estimated-load legend, height/color/heuristic explanation, and blue-selected-outline explanation on mobile and desktop.
- [x] Synthetic keyboard Enter navigation, focus restoration, selected outline, minimum target sizes, and no document horizontal overflow checked at 320 / 390 / 1280px.

## TDD evidence
Initial focused run: 10 intended missing-feature failures plus one fixture setup error. Corrected the fixture error (question-ID behavior already worked). Implemented after observing intended red assertions. Additional unqueued-finding test failed correctly before adding the guard.

Final command:
```
.venv/bin/python -m pytest tests/test_recommendation_ui_clarity.py tests/test_queue_position.py tests/test_improve_ui.py tests/test_overview_ui.py tests/test_issue_loop_ui.py tests/test_improve_navigation_ui.py -q --tb=short --show-capture=no
```
**60 passed**. Includes 13 new clarity tests. No full suite, external calls, live review reads, or push. Files remain below 600 lines.

## Caveats / handoff
- Existing `test_phone_first_workspace.py` was inadvertently included in an earlier exploratory focused run; it uses its temporary fixture DB, not actual review data. Do not repeat it under the no-DB boundary. Its strict phone-top-position assertions failed with the expanded visible legend (desktop 479px vs <450, mobile 607px vs <430 at that point). Later concurrent CSS spacing changes were not evaluated with that DB-backed test. The mobile toolbar is non-sticky to avoid covering content.
- Concurrent changes appeared in owned energy/CSS files during execution, temporarily collapsing the guide. Restored required always-visible legend/explanation and verified final 60 synthetic tests green. Preserve any independently authored spacing changes already present in those files.
- Existing staged `.superpowers/sdd/progress.md` and unrelated artifacts are intentionally excluded from this commit.
