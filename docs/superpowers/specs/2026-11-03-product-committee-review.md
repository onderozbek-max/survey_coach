# SurveyCoach product and design committee review

Date: 2026-11-03. Requested by Onder ("bar is very high", full creative freedom).
Committee: Design Director (live visual walkthrough, 1440 and 390), Head of Product / IA
(journey and concept model, code-level), Survey Methodology and Respondent-Experience Lead
(checks, rubric, scoring, fixtures), chair synthesis with independent walkthrough.
All reviews were read-only. Claims marked VERIFIED were reproduced on Onder's saved review.

## Verdict

- Craft: 7/10. Strong visual identity; the phone preview is the soul of the product.
- Value: about 5/10. Today it is a strict pre-launch linter with a beautiful face, not yet
  the member's advocate. It models hygiene well and the member's experience poorly.
- Trust: at risk. A researcher who spots one false blocker stops believing the rest.
- The loop is broken: decide, copy, change in RedJade, check again, and nothing remembers
  what you chose or tells you truthfully what you fixed.

North star restated: researchers should feel what a member feels, fix the few things that
matter most, and prove it improved, without reading a manual.

## 1. Trust breakers (fix before anything new)

| # | Problem | Evidence |
|---|---|---|
| T1 | False must-fix "no welcome page" on every live-link read; readers never emit `intro`/`thank_you` page kinds, so B4 fires, B5 never can, intro wording checks never run | VERIFIED: saved review page 1 is a 15-word welcome (`info`), B4 must-fix raised, AI 1.2 simultaneously comments on "the opening". `reader/extract.py`, `reader/definition.py`, `checks/structure.py` |
| T2 | Raw internal IDs shown to researchers (checklist group headings, copy-all output, criterion codes like `B1`, `4.4`) | VERIFIED: All issues heading `q-9d50f...`. `site/workflow.js` |
| T3 | Survey title captured as "Surveys"; no rename | VERIFIED |
| T4 | Phone opens scrolled past the question stem (auto-scroll to selected pin) | VERIFIED desktop and 390 |
| T5 | "What is working" credits criteria that were never examined; four lenient-scoring paths (unchecked, not-applicable, ungrounded deduction, merged-finding all earn full credit). Deliberately broken fixture scores 83 locally | `judge/grounding.py`, `scoring.py` |
| T6 | Method-blind nags: flags 0-10 recommend scales and 9-point hedonic scales (standard in sensory research, i.e. RedJade's home turf), marks Excellent-to-Poor as unbalanced, flags every slider/ranking | `checks/phone.py`, `checks/answers.py` |
| T7 | Contradictory advice on one screen ("add a comment box" vs "too much typing") | fixtures |
| T8 | "Ready to launch" is unreachable for link reads (`full_branching_coverage` hardcoded False) | `reader/models.py`, `repository._qualify` |
| T9 | Code rewrites may contain placeholders; the read-time guard then discards the whole suggestion, losing a valid time correction | `checks/structure.py` REWARD_SENTENCE, `recommendations.py` |
| T10 | AI is told not to repeat code-found issues on the same element, so a cosmetic finding can mask a leading-question finding | `judge/prompts.py` |

Noise: 47 findings on a 17-screen survey, 43 "worth improving", 12 from one criterion as
separate cards (VERIFIED). Every card repeats the same no-rewrite boilerplate; "Worth
improving" sits next to "Action required".

## 2. Concept model: one vocabulary

Today there are nine nouns for a problem, two meanings of "version", four decision states
plus a checkbox, five ways to say "what we did not check" and seven simultaneous caveats.

| Concept | Use | Retire |
|---|---|---|
| A problem | Issue | finding, recommendation, fix, thing to look at, claim |
| Severity | Fix before launch / Worth a look / Polish | must_fix, worth_improving, Action required |
| Suggested text | Rewrite | suggestion, version (for rewrites), chosen fix |
| Decision | Use this / Keep mine (+ reason chip) | pick, original, keep, open, "I made this change" |
| Survey iteration | Round 2 | Version 2 |
| Recheck | Check again | reread, recheck, updated snapshot |
| Scope | What we checked (one line, details on demand) | coverage, checked scope, pending blockers, stop_reason codes |
| Preview | Original / Rewritten | Current / With fixes |

## 3. Experience concept: three moments, one page

No tabs. Two places only: My surveys, and a Survey page.

Moment 1, Start: paste link, Check survey. Consent line at the button (AI wording, possible
test response). Known link starts Round N+1 instead of a duplicate. Wow: "Watch it read":
captured screens drop into the phone live as the reader walks the survey, with a real
counter ("Reading screen 6...").

Moment 2, Review (the member's-eye view):
- Verdict as one sentence: "3 issues to fix before launch, 6 worth a look, about 13 min for
  members." Score moves to details.
- Opens on the first Fix-before-launch screen; question stem always visible.
- Journey strip under the phone (wow): every screen as a bar showing estimated seconds,
  effort and issue severity, fatigue zones from the existing timing model; costliest
  screens obvious at a glance; click to jump.
- "Top issues for members" first, then grouped by question; repeated criteria collapse into
  one card ("Desktop wording, 12 places, fix all").
- Next issue stepper. One decision UI everywhere: Use this (copies and records) / Keep mine.
- Original / Rewritten side-by-side phones with "Play as a member" at estimated reading pace
  and an honest time delta ("about 13:30 to 11:50, estimate") (wow).

Moment 3, Finish:
- Sticky action bar: Copy all changes (n), Check again, Share for sign-off.
- Change sheet: ordered by screen, Q-number, target (question / answer 3 / scale label),
  find and replace text, kept-on-purpose items with reasons.
- Check again pre-fills the link; decisions carry to the next round; result opens on
  "Round 2: 4 fixed, 1 still there, 0 new" with before/after wording; each change-sheet
  line ticks itself off ("Fixed with your rewrite" / "Fixed your way") (wow).
- Share for sign-off: one-page, director-readable in two minutes; technical caveats in an
  appendix.

## 4. Cut / simplify (YAGNI)

Cut from researcher UI: hidden device switcher and other rendered-then-hidden scaffolding
(section eyebrows, preview caption, lead line), snapshot import on the front door (keep API),
"I made this change" checkbox (recheck is verification), Ask the coach (until it can generate
alternatives), static demo footer link and unused coffee-pods endpoint, version select
(becomes round timeline), duplicate checklist decision UI (list view reuses coach card).
Fix: sample runs with cached AI so the first impression is the full product; home example
card must match the real workspace.

## 5. Methodology upgrades (member-love, not just hygiene)

1. Impact triage tiers (Hurts the data / Hurts the experience / Polish) mapped in rubric
   YAML; group by question; blockers absorb same-root findings.
2. Effort and drop-off risk per screen from `timing.PageTiming` (fatigue zones already
   computed and unused).
3. Method-aware exceptions (NPS, 9-pt hedonic, JAR, Excellent-Poor, mandated tracker items).
4. Monotony checks: repeated scales/openings, total grid rows, back-to-back open-ends,
   late heavy grids, straightlining risk.
5. Answer integrity: exclusive "None of these", "Other" without text box (fields exist,
   unused), placeholder/test text as a blocker.
6. Optional research brief (objective, decisions, audience, survey type, reward wording):
   fixes the 5-minute default for IHUTs and enables honest intro rewrites.
7. Measured accessibility and ergonomics from the reader (tap targets, font size, contrast,
   progress indicator).
8. Path-aware timing using `reader/definition.py` conditions.
Later, needs data: "How was this survey?" closing question, completion benchmarks and
calibration of rubric weights and timing constants against real member behaviour.

## 6. Roadmap

| Phase | Theme | Contents | Size |
|---|---|---|---|
| 0 | Trust | T1-T10, title rename, plain-language labels, consent at button | days |
| 1 | Clarity | one vocabulary, triage and grouping, verdict sentence, land on blocker + Next issue, single decision model, sticky action bar, cut list | about 1 week |
| 2 | The loop | decisions carry over, pre-filled Check again, Fixed / Still there / New, change sheet, sign-off one-pager | about 1 week |
| 3 | Wow | journey strip, side-by-side Play as a member, watch it read, method upgrades 2-5 | 1-2 weeks |
| 4 | Proof | research brief, measured accessibility, path timing, member rating and benchmarks | later |

Distribution note: the app currently requires a terminal to start; real researcher adoption
needs hosting (AI Innovation Lab) once Phase 2 lands.

## Decisions needed from Onder

1. Readiness philosophy: separate "what we checked" (caveat) from the judgement so "No
   blockers found in what we checked" is reachable, and let "Keep mine" with a reason clear
   a blocker. Committee recommends yes.
2. Approve Phase 0 + 1 as the next build.
