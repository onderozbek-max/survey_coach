# Internal audit: evidence, recommendations and UI boundaries

Baseline: `040076e`. Audit-only: no production fixes, vendor requests, AI calls, actual review access or history mutations. Existing staged progress and screenshots preserved.

## Method

Trace shared evidence across producers, scores, projections and UI rather than relying on passing feature tests. Use adversarial synthetic equivalent representations, missing metadata, interrupted jobs, duplicate labels and delayed saves. Three independent read-only reviews cover engine, reader and UI; main agent independently reran their executable probes plus recommendation/media probes. Prior acknowledged heuristic calibration risks are not counted as new discoveries.

## Confirmed findings and remediation order

Priority 1–3 below means proposed remediation order, not incident severity. Most source findings are medium/P2; no security exploit or universal false-ready result is claimed.

### Priority 1: protect research content and evidence integrity

1. **Answer rewrite targets other text.** A replacement for answer `Yes` also rewrites `Yes or no?` and matching help text. Question-level location is insufficient; use explicit field/option identity throughout planning, rendering, copying and reading projections. Add collisions within one question and across questions.
2. **Duplicate answer labels collapse distinct controls.** Extraction reduces `Same / Same / Other` to `Same / Other`. Retain control identity and preserve duplicates; flag ambiguous labels rather than silently changing captured choices.
3. **Suggested continuous-range repair creates uncovered values.** For dollar choices `0 to 10` / `10 to 20`, suggested `0 to 9` leaves amounts strictly between 9 and 10 with no answer. Never assume integral units from integer-looking boundaries; offer a verified exclusive-boundary edit or scoped manual guidance.
4. **Definition-only evidence appears visually assessed.** A definition containing an image can lose media in adaptation and then clear B7 or mark image checks N/A despite `visual_media_verified=False`. Carry wording-vs-rendered provenance into applicable checks; absent captured media is not proof no media exists.
5. **Missing image measurements get full credit.** Loaded image with unknown natural/rendered dimensions earns assessed 1.0 for 7.3; unknown bytes plus alt text earns assessed 1.0 for 7.6. Preserve assessable subchecks but leave the broader criterion unknown where required evidence is absent.
6. **Deduplicated reread mixes evidence attempts.** New zero-capture/error coverage overwrites version coverage while old capture assets remain served as that version. Bind snapshot/coverage/captures to one attempt or atomically retain the prior evidence bundle. Never rewrite user decisions/history as a shortcut.

### Priority 2: synchronize state and truthful completion

7. **Delayed decision skips the newly selected item.** Save item A, navigate to another category while request is pending, release response: generic advance applies to current item B. Bind completion to the original queue identity and do not advance unrelated navigation.
8. **Alternative rewrite selection does not refresh phone.** Coach selects second wording while phone still shows first wording. One authoritative selected alternative must drive both consumers.
9. **Failed running recheck leaves prior review unloaded.** Direct navigation into a running recheck followed by failure shows status but never initializes the previous saved workspace.
10. **Uncertain submission lock blocks viewing existing reviews.** Submission-pending session marker exits review initialization. Submission safety must block writes/new starts, not unrelated read-only navigation.
11. **Error-only read becomes a completed review.** Titled service-error page with no questions and `reader_error` stop reason passes import gate. Classify supported completion/no-question screen-out/error separately before saving a completed review.
12. **Definition pages inflate capture count.** `pages_captured` uses snapshot page length, including definition-only pages. Report rendered captures separately from wording screens; avoid requesting nonexistent preview indices.
13. **Invisible raw replacement counts as applied.** Hit detection counts raw page text not rendered when structured questions exist. Scope applied/visible claims to actual displayed fields, distinct from raw evidence.

### Priority 3: remove misleading flags and credit

14. **Source resolution becomes a presentation inequality.** Two square image files of 1000px and 2000px, each rendered at 150px, trigger unequal-size advice and lose 7.5 credit. Compare rendered presentation; natural dimensions support resolution checks, not display-size claims. Missing rendered layout should require verification, not guessing.
15. **Unrelated numeric phrases become overlapping answers.** `1 to 2 day delivery` and `1 to 2 year warranty` receive overlapping-range advice. Require common measured quantity/unit and range-shaped labels, or decline automatic judgement.
16. **False missing thank-you from split representations.** A screen-out with nonempty body and thank-you in intro/info question becomes must-fix; flattening identical visible text removes the warning. Use canonical screen copy for detection while retaining exact element targets for edits.
17. **B3 incompletely checked but marked assessed.** Uncalibrated captured effort does not judge late screen-out timing, yet B3 clears its pending state. Preserve independently known copy findings while leaving unverified timing incomplete. This probe does not prove global false readiness: B5 remains pending independently.
18. **Absent answer/grid categories invent earned credit and strengths.** Text-only input gets ten points across checks for absent categories and strengths about tappable/non-overlapping answers. Producers must emit explicit N/A for genuinely absent eligible content, unknown for unavailable metadata. In synthetic D6 projection, score changes from 45.45% to 14.29% with only absent choice/grid categories marked N/A; this is not a proposal to renormalize the raw scorecard.

These are 18 reproduced findings across shared underlying families, not 18 independent architectural failures. Items 4/5 share missing evidence; items 1/13/16 share representation/consumer drift; items 7–10 share asynchronous state/recovery; items 4/5/17/18 share applicability and evidence certainty. Each listed symptom has its own reachable reproduction.

## Reproductions and verification

- `scripts/audit_review_semantics.py`: four synthetic probes; all report `bug_reproduced: true`. Covers missing media measurements, equal displayed size vs different source resolution, unrelated-unit overlap, and continuous monetary range gap. Outputs full evidence, never contacts a host.
- Main agent independently reran `/tmp/surveycoach-reader-audit-probe.py`: confirms reader errors, duplicate options, definition media/counts and stale capture pairing. Full source and observed output are embedded in `.superpowers/sdd/internal-audit-reader.md`.
- Main agent independently reran `/tmp/audit_ui_probe.py`: confirms targeted text collision, invisible hits, save/navigation race, stale alternative preview, failed-recheck initialization and pending-marker read lock. Full source and output in `.superpowers/sdd/internal-audit-ui.md`.
- Main agent extracted and reran engine report's standalone command: confirmed uncalibrated B3 assessment, two equivalent-copy false positives and absent-category credit/strength inflation. Command/output embedded in `.superpowers/sdd/internal-audit-engine.md`.
- Existing related test subset: **88 passed**, despite four reproduced defects. Command: `.venv/bin/python -m pytest tests/test_checks_images.py tests/test_checks_answers_phone.py tests/test_root_cause_invariants.py -q`.
- Reader reviewer independently ran 130 focused tests. No full-suite run in this audit: prior full-suite success cannot establish absence of these new boundary bugs.

## Limits and next implementation contract

These are confirmed synthetic reproductions, not claims that every real saved survey is affected. No remediation or deployment performed. Before a fix, convert its reproduction into a failing regression, implement the smallest shared-boundary repair, then verify related consumer invariants and full non-live suite. Prioritize answer preservation/targeting and evidence provenance before cosmetic advice. Broader scientific calibration of time and layout thresholds remains explicitly out of scope.
