# Part B Task 9 — About this review

Base: `6733168`. Required commit: `Move review caveats into one consistent About sheet`.

## Checklist
- [x] Read Task 9 brief first; Task 9 only, existing checkout and branch.
- [x] TDD: observed expected RED, implemented, focused GREEN, full nonlive GREEN.
- [x] Consistent help in all three chapters, saved and static sample shells.
- [x] Accessible labelled native dialog, keyboard disclosure, containment, Escape/Close and trigger focus return.
- [x] Real coverage from `presentation.scope`, including missing/unassessed evidence; no points/findings proxy.
- [x] Centralized caveats without dropping source evidence or submission notice.
- [x] Report and specified local commit; no push.

## Implementation
- `site/about.js` now supports both the existing Home data-handling sheet and the review About dialog. The same footer trigger remains outside chapter routing in both shells, with dialog semantics and a stable control relationship.
- Five sections: What we checked; What we didn't check; Reconstructed preview; AI suggestions; Your data. All payload text is inserted as text nodes, including hostile-looking unchecked-path text.
- Counts are rendered verbatim from `presentation.scope.checked_count` / `total_count`; absent scope/counts say coverage unavailable, never all checked. Detail-update events refresh the sheet. Zero stays zero.
- Backend read-time scope projection counts applicable assessed criterion results, including assessed failures and assessed blocker checks; excludes non-applicable checks. Missing active criteria explicitly listed unchecked stay in the denominator. Unassessed blocker titles are included in unchecked checks, not silently dropped. Payloads without criterion results have unknown counts. No stored review/snapshot mutation or scoring changes.
- Shared enrichment supplies the same scope to offline demo and example payloads; regenerated `site/data.js` with the cache-only exporter (no live AI). Existing repository projection remains compatible.
- Removed Improve reconstruction/strip/checked-summary and Share caveat details/Safe rechecking block. Preserved reader stop explanations, warnings, capture links, checked/unchecked point detail, AI run/failed state and historical score limitations inside About.
- Your data explicitly distinguishes local review/decision storage from survey wording sent to Walmart-approved AI; retains personal-data exclusion, manual RedJade changes, no automatic launch approval and approved-test-link guidance.
- Recheck test-response notice remains visible at submission and describes the link input. Guarded mode notice replacement against absent/blank notice so a malformed response cannot erase the fallback. Reader participation mode notices, approval payload, URL validation, prefilled safe link, consent behavior and decision/copy workflow unchanged.
- Added bottom clearance in the static sample's mobile Overview so the fixed action bar cannot cover the shared help trigger. Dialog styling uses existing tokens only, no animation or new colour literals.
- Updated old e2e selectors/copy to assert the same safety evidence in About, retaining workflow/reader approval assertions.

## TDD and verification
Commands ran in `/Users/o0o02dn/Documents/adminAI/survey-coach`; browser fixtures use intercepted synthetic routes or temporary SQLite and stubbed reader/AI. No live database or external service used.

1. Initial RED: `.venv/bin/python -m pytest tests/test_chapters_ui.py tests/test_enrich_contract.py -k 'about or caveats or scope_' -q --tb=short` — **9 failed, 19 deselected** (missing dialog semantics, no counts/presentation, old scattered caveats).
2. First implementation run of both files — **2 failed, 26 passed**. Located mobile sample help occlusion and missing mode.notice erasing the fallback; fixed their sources, not assertions.
3. Count edge-case RED: `.venv/bin/python -m pytest tests/test_enrich_contract.py::test_scope_available_for_offline_demo_and_enriched_payloads -q --tb=short` — **1 failed** (`46 != 48`, omitted missing unchecked image criteria); corrected denominator.
4. First full nonlive run — **1 failed, 983 passed, 1 deselected**; remaining workflow test expected deleted `#strip`. Moved its local-storage assertion into About; kept all remaining workflow assertions.
5. Strengthened keyboard RED: `.venv/bin/python -m pytest tests/test_chapters_ui.py -k consistent_keyboard_modal -q --tb=short` — **4 failed**: old focus trap skipped native summary control. Included summary in keyboard containment; keyboard now opens technical details.
6. Unchecked-blocker RED: same scope edge-case command — **1 failed**, missing unassessed Broken time promise disclosure. Added actual unassessed result titles to scope; scope file GREEN **7 passed**.
7. Offline regeneration: `.venv/bin/python -m surveycoach.demo_export` — succeeded; cache-only, no `--ai-refresh`.
8. Final focused GREEN: `.venv/bin/python -m pytest tests/test_chapters_ui.py tests/test_enrich_contract.py tests/test_site_e2e.py tests/test_start_review_e2e.py tests/test_share_ui.py tests/test_workflow_e2e.py tests/test_home_page.py tests/test_design_tokens.py tests/test_copy_guard.py -q --tb=short` — **92 passed, 1 warning in 29.05s**.
9. Final full GREEN: `.venv/bin/python -m pytest -m 'not live' -q --tb=short` — **984 passed, 1 deselected, 1 warning in 171.13s**.
10. `git diff --check` clean; every changed file under 600 lines (maximum 388). Token/contrast checks included in focused/full verification. Warning is existing Starlette/httpx TestClient deprecation.

## Boundaries / limitations
No delegation, worktree, push, live test, external request, protected original or image edits. Existing untracked `review/` and `uglyhome.png` untouched. Home layout/content not redesigned; its existing dialog wiring is reused. No claim of manual visual/screenshot audit, screen-reader audit or exhaustive WCAG certification: automated Chromium desktop/mobile, keyboard and DOM checks passed. Unknown historical evidence is disclosed rather than reconstructed into passing credit.
