# SurveyCoach self-review, round 4

Reviewed baseline: `4c42be3`. Scope: development status, consolidated backlog, and product trust. Review only; no runtime changes.

## Evidence gathered

- Fresh full suite: **274 passed, 1 skipped**. The live-model smoke test remains opt-in.
- Live GitHub Pages checked in Chromium: no page errors during tested interactions; no horizontal overflow at 320px or 390px.
- Live copy interaction instrumented by replacing the clipboard writer in the test browser only: choosing Your original still copies the Neutral suggestion.
- Reloading the live page loses the explicit original selection and reselects Neutral.
- Scoring boundary probe: supply a non-triggered CheckResult for every blocker but no point-bearing criterion results. Output is score=100, unchecked_points=100, readiness=ready.
- Node probe: applyFixes with from='fit', to='fit' leaves the text unchanged but records the finding as a hit.
- Independent reviewer reproduced a reachable failure case, then the chair verified it: run_review on Coffee Pods with wording passing and story/flow throwing simulated LlmError returns readiness=ready with 37 points unchecked.
- Chair verified duplicate blocker calls [B1=true, B1=false] discard a valid grounded B1 finding without any dropped warning.
- These failure probes do not claim the saved demo cache currently contains outages or contradictory calls.

## Development status

| Area | Current state |
|---|---|
| Spikes, Plan 0 | Completed feasibility work, not a production reader |
| Review engine, Plan 1 | Implemented and tested against snapshots |
| AI judge, Plan 2 | Implemented: fixed model, parallel batches, grounding, cache, CLI integration, Ask helper |
| Backend, Plan 3 | Not built: no survey/version persistence, API or job streaming |
| Frontend, Plan 4 | Static Studio workspace demo built ahead of plan; production application and API integration remain |
| Reader, Plan 5 | Spikes only; production CrawlReader, Survey Zoo, coverage and replica pipeline remain |
| Workflow, Plan 6 | Not built: re-check, version comparison, sign-off export, editable guidelines |
| Polish, Plan 7 | Partial: device/large-text controls, timeline, browser tests; member playback/crops remain |
| Learning, Plan 8 | Deferred: performance import, predicted-versus-actual and accuracy feedback |

Verdict: a working review engine plus a deployed demonstration, not a self-service survey-review product yet. No defensible percentage-complete estimate: remaining infrastructure, reader safety and research validation dominate uncertainty.

## Ranked findings

### High: readiness can depend on unearned points

`surveycoach/scoring.py:32-70` credits unchecked criteria internally, then passes the inclusive total into readiness. The UI subtracts unchecked points for the ring, but the readiness rule does not. A constructed input with all criteria unchecked returns ready after blocker results are present.

The independent review also found a reachable failure path: story and flow outages leave Coffee Pods labeled ready with 37 points unchecked; the chair reproduced it via run_review and FakeProvider. Recommendation: model checked, earned, unchecked and readiness evidence explicitly; establish a coverage gate before Ready and distinguish intentionally deferred image checks from failed judge batches. Preserve the distinction between unavailable evidence and a failed criterion. Add partial-evaluation and high-unchecked boundary tests. This needs an explicit product/scoring decision, not a silent denominator change.

### High: fixes are text-scoped, not question-scoped

The survey-wide preview plan (`site/app.js:18-23`) carries from/to strings without question or element targets; `site/model.js:19-23` applies them wherever the text matches. A rewrite of one question's Yes option can change another question's Yes option. The chair verified the shared helper applies that replacement without any target context. Dedupe also keys rewrite ownership by text alone, suppressing independent rewrites at different locations.

Recommendation: include stable page/question/element identity in both replacement and dedupe keys, with tests for repeated stems and option labels.

### High: contradictory blocker calls can clear a real blocker

`judge/schemas.py` accepts duplicate blocker IDs. Grounding gathers triggered IDs first but then overwrites their results in list order (`grounding.py:136-142`). The chair reproduced a grounded B1 finding silently disappearing for calls [true, false]. Recommendation: reject duplicate/contradictory verdict and blocker IDs or conservatively reconcile them; never silently last-write-wins.

### Medium: Ask helper has an untrusted-content boundary gap

`judge/ask.py:24-38` emits finding-derived text after the survey data delimiter, outside the two blocks the system identifies as untrusted. Source survey text can therefore reappear outside its protected context. This is a verified prompt-construction defect, not demonstrated successful model exploitation. The helper is not exposed in the demo UI. Recommendation: delimit and escape the finding block too, and test delimiter/instruction-looking text in every finding field.

### Medium: keep-original and copy behavior conflict

`site/coach.js:40-41,66` falls back to the first suggestion when chosenChoice returns null for original. Reproduced on the live page. The button does say Copy suggested text, but the interaction violates the documented principle that the pick drives copy.

Recommendation: disable suggestion-copy when original is picked, or expose clearly separate per-version copy actions. Copy-all must skip original picks as specified.

### Medium: inconsistent blocker counts

`site/app.js:89-101` uses three blocker IDs for the headline but four must-fix findings for the counter. The live screen says Fix 3 things first and 4 must fix simultaneously.

Recommendation: use the same unit in both places, or explicitly label blocker categories versus individual issues.

### Medium: decisions have no durable workflow

`site/app.js:7` stores choices only in memory. Reload loses an explicit pick. There is no done list, keep-on-purpose reason, re-check or proof the issue was corrected in RedJade.

Recommendation: grouped fix list plus version-scoped decision persistence. Distinguish copied, manually marked done, and verified resolved; copying must not imply resolution.

### Medium: preview hit is not always a real change

`site/model.js:19-23` records a hit on substring presence before checking whether the replacement changes text. The normal AI grounding removes unchanged suggestions, so this probe tests the shared helper's boundary, not a reproduced sample regression.

Recommendation: add identity-replacement tests and only record an actual change. Also test later overwrites and question-local targeting before expanding beyond the samples.

### Product trust: source presence is not research validity

A quote establishes that words came from the survey, not that the interpretation, severity, rewrite or score is correct. Two intentionally contrasting synthetic surveys cannot validate precision, recall, stability or time savings.

Recommendation: the already-specified 20-30 survey golden-set gate, independently graded by research leadership. Include good surveys and contextual exceptions, measure false positives and missed blockers, and separately assess rewrite safety. Keep confidential examples internal.

### Low: contradictory status and design documentation

README still says the AI judge is not built. Roadmap Plan 4 and spec visual-design text mention Living Design while the architecture section records the approved custom Studio direction. Remove obsolete statements so the next implementation does not rebuild the rejected direction.

## Consolidated existing backlog

This combines roadmap items, prior review deferrals and unimplemented approved scope. It is not a newly approved build sequence.

### Near-term workflow and rubric
1. Grouped fix list, copy all, durable done state; skip original picks.
2. Severity decision: hurts data versus ordinary improvement/polish; weights and prioritization.
3. Placeholder text as an explicit launch blocker, and NPS 0-10 scale exemption decisions.
4. Keep on purpose / won't fix with saved reason.
5. Projected with-fixes score and timing, based on a reviewed revised snapshot, not optimistic checkbox arithmetic.
6. Re-check, resolved/still-open/new comparison, version timeline and sign-off packet.
7. Production crawler/image verification; distinguish broken source media from fetch failure.
8. Provenance and density polish: conflict note above choices, per-row copy, compact advice with details, ordered pins.
9. Safe composition of overlapping code and AI rewrites.
10. Remaining rule/rewrite coverage from round 2: title case, imperative-as-question, agreement-question rewrite; audit what Plan 2 already covers before building more.

### Remaining delivery plans
11. FastAPI/SQLite backend, surveys/versions/jobs, server-side LLM access, SSE progress and API tests.
12. Production Studio frontend: Home/pipeline, link import/new-version association, survey-type confirmation, reading progress, partial failures, backend integration and Ask UI.
13. Survey Zoo and production reader: navigation strategies/repair, nested sections/loops, image capture, extraction, coverage, replica fidelity and screenshot fallback.
14. Reader safety: approved test links, tagged participant containment, stop before completion, vendor approval and researcher notice.
15. Workflow/library: self-contained printable sign-off HTML, guideline/glossary editing and rubric versioning.
16. Member playback, fatigue presentation, suggested crop/download, motion/reduced motion and remaining theme/accessibility work.
17. v1.5 performance import, predicted-versus-actual, suggestion acceptance and coach accuracy signals.
18. Pre-rollout research validation: 20-30 director-graded surveys and acceptable must-fix agreement.
19. Deployment decision: assisted local pilot versus hosted self-service; approved model provider and authentication if hosted. Public Pages stays synthetic-only.

## Recommended sequence for discussion

1. Small trust-fix pass: failed-batch readiness, target-scoped preview/dedupe, contradictory blocker IDs, Ask prompt boundaries, counts, original/copy semantics and adversarial regression tests.
2. Grouped fix list with durable decisions (existing backlog priority 1).
3. Research calibration in parallel with backend + fixture-based end-to-end integration.
4. Production reader and a contained, approved real-survey pilot.

Do not add more visual effects before proving a researcher can finish one complete review loop safely.
