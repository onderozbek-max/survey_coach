# Part B Task 1: Visual foundation

Base: `ada52ec`. Owner: `code-puppy-8e1dd0`.

## Checklist
- [x] Read task brief first; inspect current styles and UI contracts.
- [x] Activate Living Design (existing non-LD exemption), execution and TDD skills.
- [x] RED: six foundation tests failed against old styles (missing palette, literal colours, gradients and unresolved token).
- [x] GREEN: exact foundation tokens, base components and token-only sweep; eight foundation/browser tests passed.
- [x] Run full offline suite; localhost synthetic rendering checks/captures at 1440 and 390 (image-inspection limitation below).
- [x] Review scope/safety and record evidence. Commit message: `Introduce light design tokens and token-only styling`.

## Changes
- Exact brief palette, typography/spacing/radius/motion/shadow tokens in `design-system.css`.
- Light base body/headings/buttons/cards/status pills; positive status uses a CSS-drawn check (no emoji font dependency).
- Visible accent keyboard focus, 136px scroll padding, reduced-motion reset and tabular numerals.
- Four other stylesheets use semantic tokens only; removed duplicate dark roots, glass, decorative gradients/glows and sub-12px metadata.
- Phone frame/background/text use phone tokens; retained conic score charts (data, not decoration) and flat timing zones.
- Test helper defaults to `#improve`; added `open_overview()` without implementing future chapter routing.

## Verification evidence
- RED: `pytest tests/test_design_tokens.py -q`: six expected failures.
- Additional RED: computed-style tests caught white home focus outline and missing positive status icon.
- GREEN: foundation and computed-style tests: 8 passed.
- First full run: 837 passed, 1 failed, 1 skipped, 1 xfailed. Failure was existing mobile phone-hero position (y=425 versus <422) after the required font increase.
- Root cause verified with DOM geometry; reduced mobile studio top padding by 4px, preserving readable text and the unchanged safety/layout assertion. Focused rerun: 9 passed.
- Final full suite: `SURVEYCOACH_LIVE=0 .venv/bin/python -m pytest -q`: **838 passed, 1 skipped, 1 xfailed, 1 existing dependency warning**, 149.68s. Log: `.superpowers/sdd/b1-full-suite-green.log`.
- Prescribed contrasts: muted/surface 5.44:1, muted/bg 5.12:1, muted/surface-2 4.93:1; accent/surface and on-accent/accent 6.09:1; accent/accent-soft 5.31:1; critical/soft 6.05:1, attention/soft 5.20:1, positive/soft 5.40:1; line-strong/surface 3.77:1 and /bg 3.55:1.
- `git diff --check`: clean.
- All modified CSS and tests remain under 600 lines; no unnecessary component split.

## Local rendering checks
`PYTHONPATH=. .venv/bin/python .superpowers/sdd/b1-visual-check.py` starts an ephemeral app with a temporary SQLite DB, bundled sample and FakeProvider. Browser routing aborts any non-localhost request. It closes browser/server and removes the temporary DB.
- `local.html` and `review.html` rendered at 1440x900 and 390x900.
- Review: no horizontal overflow, no page errors, no attempted external requests; background `rgb(247,248,250)`, card white, phone text `rgb(29,41,57)`.
- Captures (scratch, not committed): `.superpowers/sdd/b1-visual/home-{1440,390}.png` and `review-{1440,390}.png`; geometry/style results in `checks.json`.
- Limitation: this session's image tool permits only concrete user-provided image paths, so generated screenshots were captured but not directly image-inspected. DOM/computed-style and responsive checks were performed; this is not a claim of human visual sign-off.

## Scope and concerns
- No delegation, worktree, push, external calls, live DB or protected image edits. Existing untracked `review/` and `uglyhome.png` left untouched and unstaged.
- Existing rail, journey and toolbar selectors remain until their consuming UI is replaced. This intentionally overrides the brief's premature dead-rule deletion instruction, per the explicit preservation constraint.
- No JS behavior, source survey wording, decision persistence, safety copy or backend changes. Future three-chapter copy/layout and typography cleanup remain later tasks.
- Existing FastAPI/Starlette `httpx` deprecation warning is unrelated; no dependency changes.
- Live model test intentionally disabled; existing expected failure retained.
- Living Design existing non-LD exemption applied; no scaffold/migration. Test/QA skill delegation bypassed only because the task explicitly forbids delegation.
