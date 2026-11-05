# SurveyCoach product & design review: implementation brief

Date: 2026-11-04 · Reviewed: `review2/` screenshots (10), saved capture `f1b83dc71239445882800fab6e4fbc5d` (Quesadilla Tray concept test, 16 screens, 11 questions), current `site/` and `surveycoach/` code at `3b5ce91`.

Audience: the implementing agent. Every recommendation has an ID, evidence, the intended outcome and acceptance criteria. Do not implement anything marked **Decision** until the product owner chooses an option; use the recommended default only if told to proceed.

Screenshot key: **S1** home (8.17.05) · **S2** overview top (8.17.34) · **S3** overview bottom (8.17.44) · **S4** improve: welcome (8.18.01) · **S5** improve: Q1/Q9 reading (8.18.11) · **S6** improve: Q2, no issues (8.18.22) · **S7** improve: message screen (8.18.35) · **S8** improve: Q4 ten choices (8.19.01) · **S9** All screens drawer + With changes (8.19.31) · **S10** Share (8.20.04).

---

## 0. Non-negotiables for the implementer

1. **Keep truthfulness, move it out of the prose.** Earlier work correctly stopped the product from claiming things it hadn't verified. The fix overcorrected into paragraphs of disclaimers. Honesty must now be carried by *structure* (a status model, a human checklist, confidence labels), not sentences like "configured threshold is a review cue, not a scientific pass/fail". Never reintroduce false certainty while removing the words.
2. Preserve existing safety contracts: no automatic POST retry, same-job recovery, unknown evidence stays unknown, timing is an estimate, rewrites never delete distinct answers, no fabricated rewards/times.
3. **Phase 0 is mandatory:** fix the 18 reproduced defects in `docs/superpowers/internal-audit-2026-11-04.md` (rewrite targeting, duplicate labels, range gap, evidence provenance, state races) before or alongside visual work. A beautiful product that edits the wrong text is worse than an ugly one.
4. Repo rules: colors only via tokens in `site/design-system.css`, no decorative gradients/glass, files < 600 lines (create new modules rather than growing `app.js` at 391 lines or `workflow.js` at 324), WCAG 2.2 AA, offline tests only (no live RedJade, no AI calls in tests), commit per change.
   - `tests/test_design_tokens.py` pins an exact 23-value foundation palette (`test_exact_foundation_palette`). There is no violet token and no celebration accent yet. Adding the You check color and success accent requires adding tokens **and deliberately updating that test in the same commit**, with AA contrast checks.
   - The token test scans only `*.css`; also ban inline color styles in `site/*.js`.
   - The existing score ring uses a conic gradient (`styles.css:18`), which the test allows. Reuse that technique for the progress ring; linear/radial gradients and `backdrop-filter` stay banned.
5. Every user-visible change gets a Playwright check at 1440px, 1024px and 390px widths. **Accessibility scan:** axe-core is not in the repo. Adding it requires approval and a pinned, vendored copy (no CDN). Until approved, use Playwright accessibility snapshots, keyboard-path tests and token contrast tests.

---

## 1. Executive verdict

**Not yet at the bar.** The engine has real substance, and the bones are right (a phone preview, a fix queue, versions). But the product currently reads as an engineer's evidence console, not a delightful replacement for a team of human reviewers.

A business user finishing this flow today could not answer the only three questions they care about:

1. **Can I launch this?** S2 says "86/100", "Provisional", "40% coverage", "No must-fixes found in what we checked", and "Needs attention" at the same time.
2. **What exactly do I change in RedJade?** Several cards end in "Keep as is" or a 120-word paragraph with no copyable fix (S4, S5, S8).
3. **How do I tell my team it's been reviewed?** Share (S10) has no shareable output except "Download summary", and renders a literal `0000`.

The most serious product defect is fidelity. **The "member's eyes" preview hides the concept descriptions** on screens 3, 5, 7 and 9 (verified in the saved capture; see D1). In a concept test, that copy *is* the stimulus. The product's central promise is broken on exactly the content that matters most.

Numbers used as examples in this brief (such as "Improve 5 · You check 4" or "2 of 9 done") are **illustrative only**. Always compute counts from data; never hard-code them.

### What already works—keep it

- The hero promise "See your survey through your members' eyes" is excellent. Make the product earn it.
- Phone preview beside a coach panel is the right core interaction.
- Before/after diffs, the All screens drawer, version history and the honest loading state are good foundations.
- Not over-claiming. The goal is to keep that integrity while making it effortless to read.

---

## 2. Who we serve and the bar we must beat

**User:** non-technical Sam's Club / Member's Mark business owners (insights, merchandising, community) who author surveys in RedJade.

**Today's process being replaced:** share a test link → human reviewers click through → feedback trickles into a Slack channel → author reconciles comments → hopes nothing was missed.

**What the human process gives them that we must match or beat:**

| Human reviewers provide | SurveyCoach must provide |
|---|---|
| "Someone actually clicked through it" | A faithful play-through of every screen exactly as members see it |
| Typos, confusing wording, broken flow | Same, with exact copy-paste fixes |
| "This question should only show if they said Yes" | Logic/routing checks it can infer, and a short list of things to verify by hand when it can't |
| "Took me ~8 minutes" | Time estimate with a target for this survey type |
| A Slack thread proving review happened | A one-click review post and sign-off record |
| Judgment on research quality (leading questions, order bias) | Research-quality checks phrased as a smart colleague would |

**Our advantages:** instant, consistent, every screen, before/after verification, version comparison, no waiting for reviewers.

**Emotional target:** *"It caught something I'd have launched with. It told me exactly what to change. I posted proof of review in 30 seconds."*

---

## 3. Diagnosis: five systemic problems

1. **No verdict.** Score, coverage, provisional state, must-fix count and category states compete. Nothing says "here's where you stand."
2. **Defensive engineer copy.** Words such as *assessed, heuristic, configured threshold, captured path, saved assessment, provisional, coverage, reader, snapshot, partial test participant* are everywhere. They create the second-guessing the product is meant to remove.
3. **Recommendations without actions.** A large share of cards end with "verify", "ask the study owner" or "Keep". Business users need either text to paste or 1–3 concrete steps, plus a way to mark the item done.
4. **Preview infidelity and broken status semantics.** The preview omits stimulus copy, shows "Optional" based on a missing HTML attribute, and labels categories "Looking good" with 1 of 7 checks assessed.
5. **No narrative arc or ending.** Home → Overview → Improve → Share feels like four disconnected tools. There's no story of the survey, no momentum while fixing, and no satisfying finish (sign-off, team post, celebration).

---

## 4. North-star experience

### 4.1 The narrative: four acts, one header

`Check → See the verdict → Fix → Sign off & share` (with a loop: Fix → Check again).

**Extend the existing sticky app bar** (`review.html:7` brand link, `:13` "My surveys", sticky via `review-studio.css:3`) into one complete header. Brand and My surveys exist in markup but were not visible in S2/S10; first find out why (hidden at this width, or scrolled/overlapped) and fix it. The header replaces the stacked "Version 1 · You make changes in RedJade / Improve / Surveys / Rename" block (S4–S7):

```
[logo → home]  Quesadilla Tray concept test    v2 · checked 4 min ago     ① Verdict ② Fix ③ Sign off     [Check again]
```

- Logo and "My surveys" are always visible and return home.
- Survey name is editable inline. Remove the separate "Name this survey" and "Rename" links.
- One version chip with relative time. Remove the duplicated version lines (S2 shows two).
- Step labels change from "Overview / Improve / Share" to **Verdict / Fix / Sign off**, which describe outcomes rather than places.
- "Check again" is always available and opens the updated-link dialog. Remove the unstyled bottom-left button (D3).

### 4.2 One status language across the whole product

Every check, card, screen and list item uses exactly four states, each with an icon and color token, never color alone:

| State | Meaning | Visual |
|---|---|---|
| **Fix before launch** | Confirmed problem that will hurt data or members | red, filled warning |
| **Worth improving** | Confirmed, lower impact | amber, outlined dot |
| **You check** | Can't be verified automatically; a 10-second human check | violet, eye icon |
| **Looks good** | Checked and passed | green, check |

"Unassessed/unknown" is *never* shown as good. Where it matters, it becomes a **You check** item with a precise instruction such as "Open screen 16 on your phone: does the thank-you image appear?" This replaces "40% coverage", "Provisional" and "5 risk checks unverified" with something a user can act on.

**You check budget (recommended default, owner to confirm as D-Checklist):** the saved capture has 22 unassessed criteria plus unvisited paths. Turning all of them into tasks would make "Ready" unreachable and the list unusable. Generate You check items only from a curated, high-value list, grouped by theme, with at most about 6 per survey:

1. Images and media load on a phone.
2. Display logic for questions whose wording assumes a previous answer.
3. Randomization of repeated concept blocks.
4. Key questions are required.
5. "Other (please specify)" shows a text box.
6. One timed run-through.

All remaining unassessed criteria appear in a collapsed "Not checked automatically" list in methodology. They are not counted as passes and do not block sign-off. "Ready for sign-off" requires no open Fix items and every curated You check ticked.

**State mapping (required; implement as one table in code, e.g. `surveycoach/status.py`, consumed by signals, verdict, fix list and drawer):**

| Source | 4-state result |
|---|---|
| Finding severity `must_fix`, confirmed | Fix before launch |
| Finding severity `worth_improving` / quick win with a concrete fix | Worth improving |
| Finding whose evidence is unverified (e.g. B7 image not verified, unknown requiredness) or whose only action is a human judgement (e.g. 6.2 long choice list) | You check |
| Criterion assessed, applicable, full credit, no open finding | Looks good |
| Criterion unassessed and not on the curated list | Not shown as a state; listed under "Not checked automatically" |

A category card takes the worst state among its items. It may show "Looks good" only if at least one of its checks was actually assessed and passed, and no item in it is Fix, Improve or You check.

### 4.3 The verdict (replaces Overview top, S2)

Hero card, first thing seen after a check:

- **Verdict headline:** one of
  - **Fix before launch:** "2 things to fix before launch"
  - **Almost ready:** no fix-before-launch items, but open You check or Worth improving items: "Almost ready: 3 quick improvements and 4 things to check yourself"
  - **Ready for sign-off:** nothing open: "Ready for sign-off"
- **The survey's story** in one sentence, generated deterministically from detected structure (no AI required): *"Members get a friendly welcome, answer 1 warm-up question, see the meal kit idea, react to 3 quesadilla trays, then wrap up with 3 questions. About 6 minutes."* Generate it only from detected sections; omit any part that cannot be detected.
- **Three tiles:** `Fix 0` · `Improve 5` · `You check 4`. Each opens the fix flow filtered to that set.
- **Primary CTA:** "Start fixing (5)", or "Sign off" when ready. Secondary: "Play it as a member".
- **Time:** "About 6 min · concept tests usually take 6–10." Use the target for the confirmed survey type. Over-target time uses the same **Worth improving** state, not a red alarm (S2 currently shows red "Needs attention" while the plan calls it a quick win). Note: this capture was auto-classified as `non_ihut_product` (`survey_type_chosen: False`) although it is a concept test. A "Concept or services" type (`services_concept`, 6–10 min in `rubric-v2.yaml`) already exists. With the correct type, the over-time warning likely disappears.

**Decision D-Score: the 86/100 number.** Today it dominates S2 while being provisional at 40% coverage, and S2 says choices don't change it. That inverts its value.
- *Recommended:* remove the numeric score from Verdict, Home and Share. Keep it inside "How we check" methodology for experts.
- *Alternative:* show it only when every applicable check is assessed, as a secondary badge.

### 4.4 Member journey strip (replaces Energy map, S3, and the toolbar mini-chart, S4–S9)

The current chart double-encodes height = per-screen effort and color = *accumulated* effort. Users will read yellow as "problem". The legend shows "High" but never uses it, labels skip every other bar, the heaviest screen's label (Q11) is missing, and the toolbar copy is broken (D12).

Replace it with a single horizontal **journey strip**:
- One segment per screen; **width = estimated seconds** (one encoding).
- Section labels above, for this survey: *Welcome · Warm-up (Q1) · The idea (concept + Q2) · Tray 1 · Tray 2 · Tray 3 · Wrap-up · Thanks*. Detect sections from info screens, screens with stimulus copy (D1) and repeated question blocks. A question screen with its own stimulus is its own section, not "Warm-up". If detection is uncertain, fall back to neutral labels ("Screens 1–4") rather than guessing.
- Status pins on segments use the 4-state language.
- Hover/focus tooltip: "Q4 · ~35 sec · 1 thing to improve". Click jumps to that screen.
- Running time marker under the phone uses the same strip, not the blue→yellow→red bar that implies danger at the end.

Use this strip on Verdict as the journey overview, and compactly in the Fix header for navigation.

### 4.5 Fix flow (replaces Improve, S4–S9)

Layout at ≥1024px: **left:** fix list (or journey) · **center:** phone · **right:** fix card. At <1024px, stack as phone → fix card, with the list in a drawer.

**Fix list:** one ordered list of open items (Fix → Improve → You check), each showing a screen chip, short title and state icon. Replace the three tabs with inconsistent counters ("Quick wins 2/5", "3/5", "5", "4/5" plus "0 of 5 handled") with **one progress indicator: "2 of 9 done"**, using an animated ring.

**Phone:** renders the exact member screen, including stimulus copy and any captured images (D1). If a concept screen has no captured image, do not invent one; create a You check ("Does this idea show a picture? Check it loads on your phone."). The issue location is highlighted with a numbered pin matching the card. Add a realistic device frame (status bar, safe areas, scroll indicator when content overflows, sticky Next button). Replace "Aa" with a labeled "Text size" control inside Preview tools.

**Fix card anatomy:** must be identical for every finding:

1. **State chip + title in member language:** "Members may struggle to read this question".
2. **Why it matters (one line):** "Long, technical wording slows people down and blurs answers."
3. **The fix**, exactly one of:
   - **Paste-ready text:** the clean "After" text first, with "Show changes" for the diff and a **Copy** button. Show a field-location hint such as "RedJade → Q1 → Question text".
   - **Steps:** a 1–3 item checklist with concrete verbs.
   - **You check:** one question and one place to look.
4. **Actions:** `Add to my changes` (primary when a fix exists) · `Mark done in RedJade` · `Keep as is…`, which asks for an optional reason chip such as "Intentional", "Owner decided" or "Not applicable". Rename today's ambiguous "Use / Keep" (S5).
5. **Details** (collapsed): methodology and evidence, where the honest nuance now lives.

**Hard copy limit:** visible fix card body text ≤ 45 words. Anything longer goes into Details. Today's S8 card is about 120 words and repeated verbatim twice.

**"My changes" tray:** a persistent bottom sheet showing "My changes · 3". It lists accepted text changes in RedJade order, with `Copy all` and per-item copy. This becomes the hand-off into RedJade.

**Original / With my changes toggle:** label it "With my changes (3)"; disable it with a tooltip at 0. Replace the jargon "Hypothetical preview · not accepted or saved…" (S9) with "Showing your 3 changes. RedJade isn't changed until you edit it there."

**No-issue screens** (S6, S7): don't take over the card with a dead-end. Show a compact "Nothing to fix on this screen" row (check icon) with a "Next item: Q4 →" button. Never leave the user's place in the fix list.

**Completion moment:** when the last item is handled, use a short, tasteful celebration (respect `prefers-reduced-motion`) and transition to Sign off: "All 9 handled. Check your updated survey to confirm."

### 4.6 Check again and versions

- Dialog: prefilled with the last link, "Paste your updated RedJade link" plus `Check updated survey`.
- After the recheck, Verdict leads with a **"Since last version"** delta card: "4 fixed · 1 still open · 0 new · 1 couldn't compare". Each fixed item has a before/after snippet. This is the proof that replaces human re-review.
- **Keep the four existing buckets** from `site/rounds.js` (fixed, still, new, uncertain). Never drop "couldn't compare"; disappearance of a finding is not proof of a correction (`rounds.js:1`). Keep honest wording short: "Fixed = no longer flagged by our checks."

### 4.7 Sign off & share (replaces Share, S10)

This step replaces the Slack channel. It needs:

1. **Review summary card:** survey name, link, version, verdict, counts, time estimate, checked date, and the completed You check list with who ticked it and when.
2. **"Copy Slack post"**, the hero action, which produces formatted text matching the team's channel convention:
   ```
   Survey review: Quesadilla Tray concept test (v2)
   Verdict: Ready for sign-off · ~6 min
   Fixed since v1: 4 (reading level Q1, …) · Kept on purpose: 1 (Q4 list length – owner decision)
   Checked by hand: images load, Q5 shows only after "Yes", concept order randomized
   Link: <RedJade test link>
   ```
   Use Copy and a short toast confirmation. **Decision D-Slack:** a direct Slack post via an approved integration later; v1 is copy only.
3. **Download PDF/HTML summary** as a secondary option for audits.
4. **Sign-off button:** "I've reviewed this survey" records name and timestamp locally, then shows a calm success state.
5. **Remove** "Advanced · local snapshot import" from the business UI (S10). Keep it behind a developer flag.
6. Rewrite the scary line "This reader blocks answer writes. Opening a test link may still create a partial test participant." as "We open your test link like a member would. RedJade may record this as a test response. Exclude test responses before analysis." Place it next to the link field, once.

### 4.8 Home (S1)

- **My surveys** cards: real survey name (D6), verdict chip using the 4-state language, "3 open · checked 1 h ago", and a `Continue` button. Remove the six unlabeled status icons and "Survey Quality · 86/100 · Provisional · 40% coverage".
- If a check is genuinely running, show a live mini progress state; otherwise never show "Checking…" (D10).
- Replace the "See / Improve / Share" strip, which looks like links but isn't, with a three-step "How it works" row using real micro-visuals: phone preview, fix card and Slack post.
- Make the example card an **interactive mini-demo**: tap "Use" and watch the phone text change. Remove the triple-redundant "2 / 2 must-fix issues / 2 must-fix" (S1).
- Ask the two setup questions that drive correctness **before** the check, not after it on Overview (S2):
  - **Survey type**, auto-detected with a confidence label: "Looks like a **concept test**". Today this concept test was auto-classified as `non_ihut_product` ("Product test") and judged against the wrong time target, even though "Concept or services" exists. Improve detection: concept descriptions followed by purchase-intent questions indicate a concept test. Always ask the user to confirm.
  - **Reward:** "Does this survey offer a reward? No · Yes: ___". The S4 card nags about "confirmed reward terms" with no way to answer. Member's Mark Community points may not be redeemable today, so many surveys legitimately have no reward.
- Add a distinctive logo mark. Today it's a plain blue square.

---

## 5. Confirmed defects

All items below were observed in the screenshots, and where noted confirmed in code or the saved capture. IDs are referenced in the acceptance tests.

| ID | Pri | Defect | Evidence / root cause | Fix and acceptance |
|---|---|---|---|---|
| D1 | P0 | **Phone preview omits concept/stimulus copy on question screens.** Screen 3 data has "Alright so here's our idea… Member's Mark Quesadilla Meal Kit. Imagine an easy meal at home…" (about 56 words) but S6 shows only the question. Screens 5/7/9 omit tray descriptions of about 54–82 words. No concept images were captured on these screens (`media: []`). | `site/phone.js` renders `page.text` only for info/welcome pages (lines ~150–153). Question pages render questions only. The reader keeps stimulus inside raw `page.text` with no separate field. | Derive a `stimulus` block from raw page text by **reusing** `surveycoach/timing.py` `_unrepresented_text` (line ~81, used through ~122), which already subtracts question, help and option text. Do not write a second subtraction routine. Timing already counts these words: the split must not double-count or drop them (add a parity test). Phone renders stimulus above the question. Checks (reading level, claims consistency) run on stimulus too. **Accept:** synthetic page with body + question renders both in order; timing total unchanged before/after the split. |
| D2 | P0 | **Category states say "Looking good" on tiny or no evidence.** Tone & fun "Looking good (1 of 7 checks assessed)"; Honest answers 3 of 8; Phone comfort "Looking good" while saying the image couldn't be verified; Clarity "Looking good" while citing a Q1 wording problem (S2). | `surveycoach/signals.py` `_ratio_state` (~56–57) and `_signal_state` (~92–101) compute state only over assessed criteria. Summary text picks a finding independently of state. | Implement the state mapping table in §4.2. **Accept:** a synthetic review with 1 of 7 checks assessed never renders Looks good; a card whose summary names a problem cannot show a positive state; B7 unverified image yields You check, not Improve. |
| D3 | P1 | "Check updated survey" renders as an unpadded, square-cornered box at bottom-left (S4–S7). Same problem on the Close buttons in About and Quality dialogs. "Start next version" looks like a text input (S10). | `.btn-secondary` (`design-system.css:47`) has no padding/radius; only `#chapter-share .btn-secondary` (`chapters.css:25`) adds them. `review.html:31`, `about.js:7`, `quality.js:9` lack the base `.btn` class (`overview.js:85` does it right with `btn btn-secondary`). "Start next version" (`review.html:50`) is padded, but surface background + strong border + radius matches input styling. | Add `.btn` everywhere and make the button component visually distinct from inputs (weight, fill or shape). Move Check again into the header. **Accept:** visual snapshot; no button lacks padding/radius; no button is styled like an input. |
| D4 | P1 | Share renders literal **`0000`** (S10). | `site/rounds.js` ~line 21: `list(changes[key]).length && h(...)`. On v1, `round_changes` has four empty arrays, so each `0` renders as text. Same pattern at `coach.js:55` (`f.also_affects?.length && h(…)`). | Use explicit conditionals (`length > 0 ? … : null`). Do **not** make `h()` drop numbers (it would hide real numeric children). Add a static test rejecting `.length && h(` in `site/`. **Accept:** zero-count round shows no stray digits. |
| D5 | P1 | "**Use all 2 suggestions**" when only one item has a suggestion; looks disabled and gives no reason (S5). | `site/coach.js:86` uses `item.count` (findings in group), not the count of applicable suggestions. | Count actual applicable suggestions, pluralize correctly, hide when < 2, and explain why when disabled. |
| D6 | P1 | Every survey is named **"Surveys"** (S1, S2, S4…). | `surveycoach/reader/session.py:163` falls back to `document.title` (from `observe.py:118`), which is RedJade's generic title. The definition title is already used when a definition is available (`definition.py:269`). | Name priority: **user's own name first**, then definition title, then humanized URL slug, then the first stimulus heading (e.g. "Member's Mark Quesadilla Meal Kit"). Treat generic titles ("Surveys", "Survey") as missing. Slug humanizing: split CamelCase and strip only a configured prefix list (start with `Insights`, `HMS`; owner to confirm), giving "Quesadilla Tray". Ask the user to confirm the name on first verdict. |
| D7 | P1 | Contradictory headline: "No must-fixes found…" next to red "Needs attention" Time card (S2). | `signals.py:236–238` takes the worse of the rubric-ratio state and the length-target state. Criterion 1.4 (welcome time/reward wording) is in the Time signal set (`signals.py:16`), so the red card is partly about welcome copy, not duration. | Time card shows duration only; welcome copy findings belong under Tone/Clarity. Use the confirmed survey type's target and the 4-state model; verdict uses the same counts as the tiles. |
| D8 | P1 | "Optional" appears under every question (S5, S6, S8). The capture marks all 11 questions `required=False`. Q11's own text ends with RedJade's visible "Optional" label, so "Optional" appears twice there. | `observe.py:77` infers required only from HTML `required`/`aria-required`. RedJade appears to label optional questions visibly, so absence of the attribute is not proof. | Make `required` three-state (`bool \| None`) in `surveycoach/snapshot.py` (~line 70), `reader/extract.py` (~57) and `reader/definition.py` (~317). Set it from RedJade's visible "Optional" label or a definition field when present, else `None`. Preview shows "Optional" only when verified, and never duplicates RedJade's own label. Unknown requiredness on key questions becomes a curated You check. |
| D9 | P1 | Fix-list counters disagree: "Quick wins 2/5", "3/5", "5", "4/5" and "0 of 5 handled" (S4–S9). The drawer shows 7 flagged screens. | Position counter versus handled counter versus screen flags. | One progress model: "N of M done" (§4.5). Drawer flags use the same items. |
| D10 | P2 | Home card shows "Checking…" on a review checked an hour ago (S1). The six status icons have `role=img` labels but no visible labels. | `site/workflow.js:192` shows "Checking…" whenever there is no live job, no must-fix and `ready_to_share !== true`, which matches this review. | Show a running state only for live jobs with real stage data; otherwise show the verdict chip. |
| D11 | P2 | Energy map: Q11 label missing at the heaviest bar; alternate labels; legend item never used; "selected outline" invisible (S3). | `site/energy.js`. | Replace with the journey strip (§4.4). |
| D12 | P2 | Toolbar mini-chart renders gray blobs overlapping bars (S7). | Selection/scroll rendering in the compact chart. | Removed by §4.4. If kept anywhere, add a visual regression test. |
| D13 | P2 | "No issues found" card: paragraph collides with buttons; buttons touch with no gap (S6, S7). | Missing stack spacing. | Spacing tokens; the card is replaced by the compact row (§4.5). |
| D14 | P2 | Heading hierarchy inverted: H1 "Improve" above H2 survey name; duplicate "Version 1" lines; score repeated twice on one card (S2, S4). | Layout composition. | Header pattern §4.1. One H1 per page equals the survey name. |
| D15 | P2 | Overview phone preview is tiny (~9px text) and floats misaligned (S2). | Layout. | Verdict page uses the journey strip plus a larger "Play it" preview, or none. Never show unreadable text. |
| D16 | P2 | "Version 1" pill on Share looks like a primary button; "First version / 0 no longer flagged · 0 still flagged · 0 new · 0 uncertain" on v1 is meaningless (S10). | `site/rounds.js`. | Hide comparison on v1; show a version timeline only when v ≥ 2, styled as a timeline. |
| D17 | P2 | Drawer "Close" uses a default browser style; search placeholder "Q label or topic words" is jargon; no legend for icons (S9). | Drawer markup. | Icon button with an accessible name, "Search screens", and 4-state icons with text. |

---

## 6. Recommendation quality: what a great human reviewer would say

### 6.1 Fix today's weak cards

| Card (screen) | Problem | Target |
|---|---|---|
| Welcome: "Intro doesn't say how long it takes and lacks confirmed reward terms" (S4) | Only "Keep as is"/"Skip". The action paragraph ends "A time rewrite is offered only for a calibrated, verified route." | Paste-ready line built from setup answers: "This survey takes about 6 minutes." plus a reward sentence only if the user entered one. Include a confirmation checkbox: "I timed it / the estimate is right." With no reward, never mention rewards. |
| Q1 reading (S5) | The rewrite changes meaning. The "such as" examples (prepared meals or meal kits) become the whole category, which narrows it, and "to **enjoy** at home" becomes "to **heat or cook** at home". The diff is word-fragmented and hard to read. The rewrite comes from a fixed pattern in `surveycoach/checks/reading.py` (~line 18, `simpler_question` / `MEAL_EXAMPLES`). | Fix the pattern in `reading.py`: rewrites must keep the measured behavior, timeframe, category, examples and qualifiers. Add deterministic key-term retention tests (category terms, "at home", the verb "enjoy"). No LLM judge needed. Show the clean After text first; diff behind "Show changes". Example: "How often do you buy ready-to-heat or ready-to-cook meals, like prepared meals or meal kits, to enjoy at home?" |
| Q9 reading (S5) | 90 words about "US school grade 12" and "configured grade-8 threshold"; no rewrite and no highlighted words. | Highlight the 2–4 hard words/phrases in the phone and offer a plain alternative for each, or say "Hard words: *overall idea*…" Grade numbers go in Details. |
| "10 answer choices; review the phone layout", Q4/Q6/Q8 (S8) | About 120 words, identical twice, labelled "Quick win" although it's a judgement call. Ten tappable checkbox rows are normal on phones. | Demote to a single **You check** line: "Scroll Q4 on your phone: are all 10 answers easy to reach?" Group the repeated concept blocks into one card listing Q4, Q6 and Q8. |
| Repeated groups | Same finding repeated per screen with an identical title header twice (S5). | Group identical findings across a repeated block: "Applies to 3 screens (Idea 1–3)". One fix, one action, applied to all. |

### 6.2 Checks a human reviewer would catch here—add them

These come from the actual Quesadilla capture. Each must be phrased as a finding or **You check** using the 4-state model, never as a fabricated fact.

1. **Display logic inferred from wording** (You check). Q4/Q6/Q8 (screens 6/8/10) ask "What about this quesadilla tray has you saying 'Yes, please!'?", which presupposes a positive reaction. It is correct only if each is shown after "Yes" on the preceding add-to-cart question (Q3 → Q4, Q5 → Q6, Q7 → Q8). Card: "Q4 assumes members said Yes on Q3. Check it only shows to Yes answers." The capture does not record which answers the reader chose, so this stays You check. If logic is visible and wrong, it becomes Fix.
2. **Concept order bias** (You check). This capture saw the three trays in one order; randomization is unknown. "Are the 3 trays shown in random order? A fixed order can favor the first one."
3. **Referent before stimulus:** "like this", "this tray" and "this kit" need visible stimulus on the same or previous screen. Q10's "with this quesadilla meal kit" after three different trays is ambiguous. Suggest "with a quesadilla meal kit like these".
4. **Requiredness** (You check, D8): key evaluation questions should be required.
5. **"Something else (please specify)"** is option 10 on Q4/Q6/Q8, but its text box was not captured (`is_other_with_text: None`). You check: "Confirm a text box appears when members pick Something else."
6. **Stimulus quality** (requires D1): concept-copy reading level and length on a phone (about 54–82 words per tray); consistent facts between concept copy and answer options (`$17.48` appears in the three tray descriptions and in the price option; "6 per tray" and "Made in Mexico" also appear in both; flag only mismatches). No concept images were captured; create a You check rather than assuming images exist or are missing.
7. **Near pre/post design awareness:** Q2 (interest in the overall meal kit idea, on screen 3 with its concept) and Q9 ("Now that you've seen a few quesadilla kit ideas… overall idea") form a near pre/post pair around the three trays. Recognize it as a strength ("Measures interest before and after the tray ideas") instead of flagging repetition. The wording differs slightly; do not claim identical measurement.
8. **Strengths must be earned and specific:** replace generic "Answer choices don't overlap / Easy to tap with a thumb / A nice mix of question types" with grounded specifics: "Each tray gets the same 2 questions, so results are comparable." Never list a strength for a category that wasn't checked (audit item 18).

### 6.3 Recommendation contract (enforce in code and tests)

Every rendered finding must have:
- `member_impact` ≤ 20 words (field exists today);
- exactly one action kind: paste text (reuse the existing `suggested_text` / `options` fields; add `field_location`), `steps[1..3]`, or a `you_check` question;
- no banned words (§8) in visible text;
- one state from the §4.2 mapping;
- identical findings across repeated blocks merged.

Define the new optional fields (`action_kind`, `steps`, `you_check`, `field_location`) once on the `Finding` model in `surveycoach/findings.py`. Checks produce them; `surveycoach/recommendations.py` validates them; the site only renders them. Do not duplicate paste text in a new field. Legacy saved findings without these fields render via a fallback: suggested text becomes paste; otherwise the explanation becomes a single step.

Add a test that renders all fixture findings and fails on violations.

**Fixtures:** current fixtures (`fixtures/`) don't cover this flow, and the Quesadilla capture exists only in the local database. Build a **synthetic** fixture that mirrors its structure (welcome, warm-up, concept + question, 3 repeated tray blocks with 10-option select-all and Something else, near pre/post interest, wrap-up, thank-you image) with invented product copy. Do not commit real concept copy.

---

## 7. Visual design direction: "calm confidence, member-first"

Goal: sleek, premium, unmistakably a Sam's Club tool, with joy concentrated at the moments that earn it.

**Brand & tokens**
- Keep the existing vanilla stack. **Decision D-Brand:** align tokens to Living Design's Sam's Club theme values from the official package. Do not hand-guess hex values. Those values cannot be fetched offline; **D-Brand stays blocked until the owner supplies them.** Until then, keep the current palette and add only the tokens this brief needs. Walmart guidance prefers Living Design for banner UIs; a React migration is out of scope unless requested.
- Palette: one confident brand blue for primary actions; neutral canvas (very light cool gray) with white surfaces; a warm celebratory accent used *only* for success moments; the four semantic state colors (§4.2), all AA contrast with icons.
- No decorative gradients or glass, per repo tests. Depth comes from 1px borders, one soft elevation level and generous whitespace.

**Type**
- Use one family with a strong display weight for verdict and hero, plus tabular numerals for counts and time.
- Scale: 40/32/24/20/16/14. Never < 12px, including the phone header (S4 shows ~11px meta text).
- Body text ≤ 70 characters per line in cards.

**Layout**
- 8px grid; max content width 1200px; consistent card heights in grids (S2's cards are ragged); consistent link/CTA placement at card bottoms.
- Icons are distinct per category: Time = clock, Clarity = text bubble, Honest answers = scale, Flow = route, Tone = smile, Phone = device. Today five use the same sparkle.

**Phone frame**
- Realistic 390×844 proportions, status bar, rounded screen, fixed bottom Next, visible scroll affordance. Today S8 clips "would enjoy" without a cue.
- Pins match card numbers; highlight with a soft tinted background plus an outline, not the full-question pink wash only.

**Motion:** 150–250ms ease-out for state changes, card transitions and the progress ring; a celebration only at completion and sign-off; respect `prefers-reduced-motion`.

**Empty, loading and error states:** each gets an illustration-light treatment, one sentence and one action. Preserve the loading-state truthfulness already built.

---

## 8. Copy system

Voice: a friendly senior researcher. Short sentences. Grade 6–8. Say what to do.

**Banned in visible UI (allowed inside Details/methodology only):** assessed, unassessed, heuristic, configured, threshold, provisional, coverage, saved assessment, captured path, reader, snapshot, calibrated, verified route, partial test participant, risk checks, rubric, criterion IDs.

| Today | Replace with |
|---|---|
| "Survey Quality · 86/100 · Provisional · 40% coverage" | Verdict and You check count (§4.3) |
| "No must-fixes found in what we checked" | "Nothing blocks launch. 2 improvements and 4 quick checks for you." (counts illustrative) |
| "Updates local length targets and tone checks; does not rerun saved AI advice…" | Removed; type is chosen at setup |
| "Estimated time to this screen: 0:15 of 5:58 on the captured path." | "~0:15 in · 6 min total" |
| "This is not a guarantee that the screen is issue-free; only the checks run are covered." | "Nothing to fix here" with a check icon (detail in methodology) |
| "Hypothetical preview · not accepted or saved…" | "Showing your 3 changes. Edit RedJade to make them real." |
| "Use / Keep" | "Add to my changes / Keep as is…" |
| "Must-fix / Quick wins / More ideas" | "Fix before launch / Worth improving / You check" |

Add a test that scans rendered DOM text on Home, Verdict, Fix and Sign off for banned words, excluding `<details>` methodology content.

---

## 9. Wow moments, in priority order

1. **Survey story + journey strip** (§4.3–4.4): instant comprehension of the whole survey in 3 seconds.
2. **Play it as a member:** full-screen phone play-through with a running clock, the journey strip progressing, and pins popping as issues appear. Press → to advance. This is the "through your members' eyes" promise made literal.
3. **Paste-ready fixes with a "My changes" tray** and `Copy all for RedJade`.
4. **"Since last version" delta card** with before/after snippets and a subtle success animation for fixed items.
5. **One-click Slack post and sign-off record:** the moment users think "thank god this exists."
6. **Smart logic questions** (§6.2): the tool notices "this question assumes they said Yes" like an expert colleague.
7. **Interactive home demo:** try a fix in 5 seconds without a link.

Do not build AI "simulated respondents" or invented persona feedback. They would fabricate evidence and conflict with the truthfulness contract.

---

## 10. Remove or demote

- Numeric score in hero/home/share (D-Score).
- Survey style radio group on Overview; move it to setup.
- Energy map double encoding and the toolbar mini-chart.
- "Advanced · local snapshot import" in the business UI.
- "See / Improve / Share" pseudo-link strip on Home.
- Floating "About this review" / "Quality methodology" links at page bottoms. Replace them with one "How we check" link in the header overflow menu.
- Unlabeled 6-icon row on survey cards.
- Repeated identical findings and repeated titles.

---

## 11. Accessibility and responsive requirements (WCAG 2.2 AA)

- State never relies on color alone (icon plus text label). Contrast ≥ 4.5:1 for text, including meta text on the gray canvas, and ≥ 3:1 for icons/borders.
- Focus visible on all controls; logical tab order (header → fix list → phone → card → tray); `aria-live="polite"` for progress and copy toasts, without duplicate announcements (already fixed for loading; keep it).
- Diff is readable without color: insertions underlined, deletions struck through with "removed/added" screen-reader text.
- Touch targets ≥ 44×44 (WCAG 2.5.8 requires ≥ 24, but use 44 here).
- 390px layout: header collapses to name plus a step menu; phone becomes full-width; the fix card follows; the tray is a bottom sheet; no horizontal scroll.
- The journey strip is keyboard navigable (arrow keys) and has a text-list alternative.

---

## 12. Delivery plan

| Phase | Scope | Exit criteria |
|---|---|---|
| **0: Trust** | Internal audit's 18 items; D1, D2, D8 | Each reproduction becomes a failing test, then passes; full non-live suite green |
| **1: Clarity** | Header (§4.1), 4-state model (§4.2), verdict (§4.3), copy system (§8), D3–D7, D9, D14 | Banned-word test passes; verdict/tiles/fix list counts are always consistent (property test over fixtures) |
| **2: Fix flow** | Fix card contract (§4.5, §6.1, §6.3), My changes tray, grouping, no-issue row, D13, D17 | Every fixture finding renders paste text, steps or You check; ≤ 45 visible words |
| **3: Journey & play** | Journey strip, Play it as a member, D11, D12, D15 | Keyboard/a11y tests; visual snapshots at 3 widths |
| **4: Finish line** | Check again dialog, since-last-version card, Sign off & Slack post, D4, D10, D16, home redesign (§4.8), D6 | Slack text snapshot test; sign-off persists locally; home shows the real name |
| **5: Expert checks** | §6.2 new checks with synthetic fixtures (positive and negative controls) | No new check fires on its negative controls; each has a You check fallback when evidence is missing |

**Definition of done for every phase:** offline tests only; Playwright at 1440/1024/390; accessibility checks per §0.5; no file > 600 lines; tokens only; screenshots of each changed screen saved to `review/after/<phase>/` for owner review; no push or deploy without approval.

---

## 13. Decisions for the product owner

| ID | Decision | Recommended default |
|---|---|---|
| D-Score | Keep 86/100 visible? | Remove from primary UI; methodology only |
| D-Slack | Copy-only Slack post or direct posting integration | Copy-only for v1 |
| D-Brand | Align tokens to the Living Design Sam's Club theme | Yes, tokens only; blocked until owner supplies official values |
| D-SignOff | Does sign-off need a named approver or a second reviewer? | Single named sign-off, stored locally, included in the Slack post |
| D-Types | Survey type detection and time targets | Keep existing "Concept or services" (6–10 min); improve auto-detection and always confirm with the user |
| D-Checklist | Curated You check list and cap (§4.2) | The six items listed, max about 6 per survey |
| D-Axe | Add vendored, pinned axe-core for tests | Yes, after approval |
