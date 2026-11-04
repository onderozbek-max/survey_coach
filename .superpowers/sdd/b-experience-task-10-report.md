# Part B Task 10 — Copy sweep and demo regeneration

## Status

Complete on `feature/surveycoach-mvp`, starting at `f7a3eb1`.
Commit message: `Apply the board copy deck and enforce the claims guard`.

## Checklist

- [x] Read the Task 10 brief first, then spec section 8 and current authored copy.
- [x] Add failing targeted copy/export contracts before implementation.
- [x] Apply Must-fix / Idea / Nice to have, Keep as is, Check updated survey,
  Version and Share with stakeholders wording in remaining UI and report paths.
- [x] Remove residual Ready to launch / Almost ready assertions; retain scoped,
  unknown-check and acknowledged-risk safety language.
- [x] Use canonical overview timing copy in the local header; keep scope details
  in About this review rather than the old inline scope disclaimer.
- [x] Update index metadata and hidden zero-change button copy.
- [x] Keep `tests/test_copy_guard.py` active and unchanged: its xfail was already
  removed in B8. No weakening of forbidden-claim coverage.
- [x] Regenerate `site/data.js` with `.venv/bin/python -m surveycoach.demo_export`.
- [x] Verify both committed entries match current canonical screens/plan/overview,
  including all six signals and screen counts matching snapshots.
- [x] Run targeted green contracts, full non-live suite and diff checks.

## Changes and compatibility

Updated authored JS/HTML copy, both server summary renderers, the server's
presentation verdict, and obsolete clean-demo blurb. The clean sample now
accurately describes cached AI evidence instead of falsely saying AI has not run.
The public demo already had enriched fields at this base; regeneration changed
only the corrected blurb. No invented findings or signals were added.

Added `tests/test_copy_deck.py` for retired copy, both summary variants, member-
perspective index metadata, synthetic source provenance, and exact canonical
projection equality for every committed demo entry. Updated two pre-existing
summary assertions to the new text while retaining their escaping, scope, CSP,
and no-readiness-judgement assertions.

API and persistence keys remain unchanged: `round_changes`, `compared_to_round`,
`carried_from_round`, decision payloads, endpoints and stored evidence are intact.
Only visible copy calls these Version. Existing `rounds.js` naming stays internal.

## Export input and safety audit

Inspected the actual exporter, README provenance, sample inputs and pinned cache
layout before export/commit. `SAMPLES` selects only `fixtures/boxer-briefs.json`
(13 pages, `fixture://boxer-briefs`) and `fixtures/coffee-pods.json`
(6 pages, `fixture://coffee`). README identifies both as made-up surveys.
Both fixture roots contain only title/source_url/pages; six pinned AI-cache files
contain blockers/findings/verdicts. The export runs the current engine and
`enrich()` against these fixtures via `ReviewedDemoCache` / `CacheOnlyProvider`.

No `--ai-refresh`, live AI, external services, real database, real survey,
protected-original mutation, delegation or push. Test-created databases are
isolated synthetic temporary fixtures. Existing untracked `review/` and
`uglyhome.png` were left alone and excluded from the commit.

All changed source files are below 600 lines. Generated `data.js` retains the
exporter's stable ASCII single-line JSON format; no line-limit exception needed.

## Verification

- Initial baseline copy-guard/demo tests: **20 passed**.
- TDD red: **15 failed, 7 passed**, expected retired phrases, old summary
  labels, and false clean-sample blurb. Additional index contract separately
  observed failing before its metadata change.
- Targeted copy/guard/demo/committee-rounds/workspace contracts: **54 passed**
  before the additional index contract; final copy/guard/demo run: **36 passed**.
- Full `.venv/bin/python -m pytest -m 'not live' -q`:
  **1006 passed, 1 deselected**, 186.97 seconds.
- `git diff --check`: clean.
- Export freshness is asserted by `test_committed_site_data_is_not_stale`.
- Canonical projection equality and all changed file line limits verified.

## Concerns

No blocking concerns. One existing Starlette/httpx deprecation warning remains;
no dependency changes are part of this copy task. The first full-suite attempt
hit the tool's 120-second limit without failures; a fresh complete run with a
600-second allowance passed. Task 11 visual capture work remains out of scope.
