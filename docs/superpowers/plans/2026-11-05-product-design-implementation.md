# Implementation plan: product and design review

Spec (single source of truth): `docs/product-design-review-2026-11-04.md`. Trust-defect source: `docs/superpowers/internal-audit-2026-11-04.md` (18 items, numbered there).

## Owner decisions applied (the brief's recommended defaults)

- D-Score: remove numeric score from Home, Verdict and Share (keep in methodology only).
- D-Slack: copy-only Slack post. D-SignOff: single named sign-off stored locally.
- D-Types: keep `services_concept`; improve auto-detection; always ask the user to confirm.
- D-Checklist: the six curated You check items, max about 6 per survey.
- D-Brand: BLOCKED (owner has not supplied Living Design values). Keep the current palette; add only the tokens this work needs and update `tests/test_design_tokens.py` deliberately.
- D-Axe: NOT approved. Do not add axe-core. Use Playwright accessibility snapshots, keyboard-path tests and token contrast tests.

## Rules for every task

Offline only (no live RedJade, no AI/vendor calls, no real DB mutation; use temporary or in-memory repositories and synthetic fixtures). TDD: failing test first, then the smallest fix. Files under 600 lines (add modules, do not grow `app.js`/`workflow.js`). Colors only through tokens; no linear/radial gradients, no backdrop-filter, no inline color styles in JS. WCAG 2.2 AA. Commit only named files; never touch staged `.superpowers/sdd/progress.md` or untracked `review/` assets. No push or deploy. Preserve the safety contracts: no automatic POST retry, unknown evidence stays unknown, timing is an estimate, rewrites never delete distinct answers.

## Phases (see brief section 12 for exit criteria)

| Phase | Workstreams |
|---|---|
| 0 Trust | 0A engine/checks (audit 3,5,14,15,16,17,18) · 0B reader/snapshot (audit 2,4,6,11,12; D1, D6, D8, survey-type detection) · 0C site state (audit 1,7,8,9,10,13; D4, D5) |
| 1 Clarity | status model (`surveycoach/status.py`), header, verdict, copy system, D3, D7, D9, D14 |
| 2 Fix flow | fix card contract, My changes tray, grouping, no-issue row, D13, D17 |
| 3 Journey and play | journey strip, Play it as a member, D11, D12, D15 |
| 4 Finish line | Check again dialog, since-last-version card, Sign off and Slack post, D16, home redesign |
| 5 Expert checks | brief section 6.2 checks with synthetic positive and negative controls |

Each workstream ends with an independent read-only review before the next phase starts. Reports go to `.superpowers/sdd/impl-<workstream>.md`.
