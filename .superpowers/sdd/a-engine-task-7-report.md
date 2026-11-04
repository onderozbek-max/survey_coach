# Part A Task 7 report

## Scope / checklist
- [x] Read task brief first; verified feature/surveycoach-mvp at fb46ccb.
- [x] Inspected CheckResult, review serialization, scoring, retained-result projection,
  timing, screen labels, and plan decision semantics before implementation.
- [x] Added pure `surveycoach/signals.py` and `tests/test_signals.py` only.
- [x] Focused TDD red/green, full suite, final diff/line-count checks.
- [x] Commit with required subject: `Add member experience signals, strengths and energy map`.

## Implementation
- Six fixed signal groups and labels; weighted ratios use only active rubric criteria
  with explicit assessed/applicable flags and a non-null fraction. Thresholds are
  >= .85 strong / >= .6 mixed / otherwise needs_work. No evidence is unknown,
  or mixed when concerns exist. Open must-fixes override ratios.
- Decisions follow the existing plan semantics: pick/original or keep with a
  nonblank reason stops the open-blocker override. A keep without a reason does not.
- Snapshot timing is recomputed by the existing pure estimate (not old stored time).
  Time uses effective snapshot survey type and rubric targets. Branching explicitly
  warns of uncertainty and excludes retained 2.1 credit/debit and the length rule.
- Half-minute formatting rounds nearest half, ties up. Estimates remain labelled.
- Strengths are at most three POSITIVES strings, full assessed applicable credit,
  no nested or top-level findings, sorted by descending points then criterion ID.
  Absorbed concerns still disqualify strengths; legacy checked lists/scorecard
  summaries never imply passing evidence.
- Energy includes every supplied screen in order, per-screen seconds, estimator
  fatigue zone, worst visible severity, and top-three page IDs (stable screen-order
  tie break). Question location wins over page fallback; survey findings do not
  manufacture screen markers. Navigation uses fingerprint and page-ID lists.
- Headline uses plan open-must-fix and quick-win counts. Subline uses the heaviest
  screen's existing name (including question ranges), without renumbering.

## Verification
1. Initial focused run failed collection because signals did not exist (expected).
2. Public API stubs then produced 36 failing tests. Corrected a builder argument
   typo, reran and confirmed all 36 failed on unimplemented API (red).
3. Implemented feature: 36 focused passed (green).
4. Full suite: 805 passed, 1 skipped, one existing Starlette/httpx deprecation warning.
5. Added five characterization/edge-case regressions: 41 focused passed.
6. Final full suite: **810 passed, 1 skipped**, same deprecation warning, 152.44s.
7. `git diff --check` passed. Module 170 lines; tests 247 lines, both <600.

## Constraints / concerns
- No repository wiring, frontend changes, historical-result mutations, real DB
  access, external calls, delegation, worktree creation, or push.
- Protected `review/` and `uglyhome.png` were already untracked and left untouched.
- No existing tests or safety assertions changed.
- Input screens are expected to be canonical screen_labels for this snapshot;
  the projection deliberately does not silently invent timing for foreign page IDs.
- Partial checked evidence can yield a strong ratio, but summaries qualify it as
  “in what we checked”; unassessed checks contribute neither earned nor possible
  points. Timing is independently available even without a stored review.
- Wiring into detail/enrich remains a later task, intentionally out of scope.
