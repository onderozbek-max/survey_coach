# SurveyCoach board review: from rule-checker to the member's advocate

Simulated review meeting, 3 November 2026. Inputs: `review/homepage.png`, `review/survey1.png`,
`review/survey2.png`, `review/survey3.png`, the live isolated workspace (Halloween survey, 17 screens,
46 findings), and the code on `feature/surveycoach-mvp` at `26dc557`.

The board members are fictional composites. Their positions reflect the perspectives requested:
investors, former Meta product and design leaders, and working business researchers.

| Seat | Who | Lens |
|---|---|---|
| Lead investor | Dana Whitfield, General Partner (consumer software) | First 10 seconds, wow, retention loop |
| Investor | Raj Mehta, Partner (enterprise workflow) | Adoption, trust, proof of value |
| Product | Priya Anand, former Director of Product, Meta (in-app feedback and survey tooling) | Narrative, prioritisation, progressive disclosure |
| Design | Marcus Lee, former Design Director, Meta (creation tools) | Visual system, hierarchy, motion, craft |
| Researcher | Elena Ruiz, Senior Consumer Insights Manager (runs RedJade and Qualtrics studies weekly) | Does this help me ship a better survey today? |
| Researcher | Tom Becker, Research Ops Lead (about 40 member surveys per quarter) | Speed, repeatability, defending choices to stakeholders |
| Facilitator | test1 | Evidence, scope, trade-offs |

---

## 1. What the board saw (screen by screen)

### Home (`homepage.png`)
- The hero promises "Launch surveys members **actually finish**". This is an outcome claim we cannot
  measure. It contradicts the product's honesty principle at first contact. (Raj: "The first sentence is the
  one thing your own rules forbid.")
- Five separate caveat paragraphs sit between the input and the fold. The primary action is buried in compliance text.
- The tilted example card, with the strike-through rewrite, is the most elegant moment in the product. Everyone noticed it.
  (Marcus: "This is the product. Show this motion everywhere.")
- "My surveys" shows a card titled **Surveys**: the captured RedJade title is generic. "25 of 39 checked
  points" is jargon to a business user.
- "How it works" and "How your data is handled" repeat the caveats a third and fourth time.
- Dark, glassy "developer console" aesthetic. Elena: "My director would think this is an engineering tool."

### Review workspace (`survey1/2/3.png`)
- **Five competing zones at once**: screen rail, phone, member journey, coach card, and a sticky action bar. There is no
  single place to look. (Priya: "You show everything you know. A story shows only what matters next.")
- Status line: "3 issues to fix before launch · **29 worth a look · 14 polish**". **46 items** is a wall,
  not a plan. Tom: "I would close the tab at 46."
- **Numbering mismatch (bug, confirmed in data):** rail and phone say **Q11**; the card says **Q22 · Screen 12**.
  Screen 9 holds 11 questions. The rail counts question *screens* (`model.js`), the card counts *questions*
  (`issues.js`), and the server uses a third scheme (`rounds.locations`). Elena: "If the numbers disagree, I trust nothing."
- **Duplicate issue cards (confirmed):** "Members who did not shop cannot choose an honest answer" (B2) and "The
  shopping-method question has no answer for nonshoppers" (8.4) are the same root problem on the same question.
- **Rubric IDs leak into prose:** "This finding also covers 4.1 and 4.3."
- **A broken rewrite (bug, confirmed in data):** the welcome rewrite reads "...celebrated! **Next** This takes about
  14 minutes." The reader captured the button label "Next" as page text, and the time rewrite appended to it.
- Original quotes render with large blank gaps: `\n\n\n\n\n\n` from RedJade formatting is preserved verbatim.
- Phone text is interrupted by numbered pins inside sentences ("...this year? (1) Check off all that apply. (2)").
- **Inverted hierarchy:** "Keep mine" is a full-width primary button, and its reason form opens before the researcher sees a fix.
  After "Use this · chosen", both buttons still shout equally.
- "AI · review the advice" is a purple alarm badge on most cards.
- Journey bars are tiny. "Welcome" is clipped to "Velcom", and the colour meaning is unexplained. Yet the best signal
  in the product is hidden there: "Most effort: Q8 (188s)".
- Duplicate controls: two "Next issue" buttons, plus "Previous screen" and "Next screen" text links.
- Footer disclaimers appear twice. "Scope-limited review · not launch approval" appears in the header.
- **Methodology contradicts the mission (confirmed):** **12 of 46 findings are "Emoji in a question/answer"**.
  "DIDN'T" is flagged as shouting. This is a playful Halloween community survey for Sam's Club app members, and the
  product's goal is surveys members find fun. Tom: "Emoji is our house style. You are telling me to make it boring."

### What everyone agreed is genuinely strong
1. The phone is the soul. Seeing the survey as a member sees it is the differentiator.
2. The before/after strike-through pattern (home example card).
3. Honest estimates, explicit decisions, and immutable history: the trust engine underneath is real.
4. The effort journey concept. It needs to be bigger, labelled, and promoted, not removed.
5. Rounds, with "what changed since last time", form the retention loop investors want.

## 2. Board scorecard (1-10, today)

| Dimension | Score | One-line reason |
|---|---|---|
| First impression | 5 | Strong hero type, buried by caveats; an outcome claim we can't back up |
| Narrative clarity | 3 | No story. Five zones and 46 items at once |
| Signal quality | 6 | Good raw signals (time, effort, honest answers), presented as defects only |
| Visual craft | 5 | Polished components, dev-tool mood, weak hierarchy, small grey text |
| Trust | 6 | Honest engine undermined by visible numbering, duplicate and "Next" bugs |
| Time to value | 4 | It takes too long to find "what do I fix first?" |

## 3. The core insight

> **SurveyCoach shows everything it knows. It must instead tell one story, in three chapters:**
> **See** how the survey will feel to a member → **Improve** the few things that matter most → **Share** with confidence.

North-star sentence for every screen: *"See your survey through your members' eyes."*

Every signal must pass five tests (Priya's rule):
1. **Member-centred**: phrased as what a member experiences, not which rule failed.
2. **Evidence-backed**: derived from captured screens or assessed checks, never invented.
3. **Actionable**: one tap takes you to the screen that causes it.
4. **Honest**: estimates say "estimate"; unchecked items say "not checked yet".
5. **Glanceable**: word + icon + colour (never colour alone), readable in two seconds.

## 4. The experience the board wants

### Chapter 0: Home ("one input, one promise")
- Headline: **"See your survey through your members' eyes."**
- Sub: "Paste a RedJade test link. SurveyCoach walks it like a member on a phone, then shows what to fix first,
  with ready-to-paste wording."
- One input, one primary button ("Check survey"), and one line of essential notice: "Test links only · Wording is
  reviewed by Walmart-approved AI · Creates a test response to exclude from results. **How we handle data**".
  "How we handle data" opens a sheet. The test-response note stays visible because it affects real data.
- Secondary: "Try a sample survey".
- Right side: a living version of the example card. The phone shows a question, the phrase highlights, and the rewrite morphs in.
  Motion is reduced to static for reduced-motion users.
- Slim three-step line: **See · Improve · Share**.
- "My surveys": clean cards with title, one status word, six signal dots, and "Version 1 · 4 hours ago". The whole card is clickable.
- Removed from Home: "How it works" cards, "How your data is handled" section, the footer pilot disclaimer
  (moved into the data sheet).

### Chapter 0.5: Reading ("watch it read")
Centred phone filling with captured screens, a single progress line ("Reading screen 6..."), and three quiet steps
(Reading screens → Checking wording → Writing suggestions). The result opens with a short reveal into the Overview.

### Chapter 1: Overview ("the member's view at a glance")
Above the fold, in reading order:
1. Title (inline-editable; a generic title shows **"Name this survey"**) and quiet meta: "Version 1 · checked 4 hours ago".
2. **The headline**: "3 must-fixes before launch, then 6 quick wins."
   Subline: "About 13½ minutes for members (estimate). The heaviest moment is Q8–Q18."
3. Primary: **Start improving**. Secondary: **Preview as a member** (full-screen walkthrough at reading pace).
4. A mini phone showing the first must-fix screen, with the problem phrase highlighted.

Below:
5. **Member experience**: six signal tiles. Each shows a state word, one sentence, and "See n screens":
   **Time · Clarity · Honest answers · Energy & flow · Tone & fun · Phone comfort**.
   States: Looking good / Room to improve / Needs attention / Not checked yet.
   Time compares the estimate with the team target for the survey type from the rubric. Example: "About 13½ min (estimate).
   Community surveys aim for 5 min or less." This is a house standard, not a fabricated benchmark.
6. **Energy map**: the journey strip, now full width. Bars show estimated seconds per screen and are coloured by the existing
   fatigue model (Fresh / Getting tiring / Tiring). Must-fix screens get a marker. Clicking a bar jumps into Improve.
   The caption repeats "estimate"; no drop-off claims.
7. **What members will like**: up to three strengths, only from assessed checks at full credit in this
   review. Examples: "A genuine thank-you", "A nice mix of question types". Never inferred for legacy reviews.
8. **Your plan**: Must-fix 3 → Quick wins 6 → More ideas 37 (collapsed, grouped by pattern).
9. **Survey style** (one question, not a form): "What kind of survey is this?" Community & fun · Product test ·
   Home-use test · Concept or services · Market research. Community & fun treats emoji and playful wording as voice,
   not defects.
10. Footer link: **About this review** (what we checked, what we did not, reconstructed preview, AI note, data handling).

### Chapter 2: Improve ("one thing at a time")
- Slim sticky bar: segmented progress **Must-fix 1/3 · Quick wins 0/6 · More ideas**, plus a compact energy mini-map.
  Right side: "All screens" (drawer with search by Q number or words) and **Original | With changes**.
- Two columns: phone (left, sticky) and decision panel (right). No rail, journey, or second "Next issue".
- The phone uses a soft highlight on the exact phrase, with a small marker in the margin instead of pins inside sentences. Added answer
  options show as a dashed "Suggested" row in **With changes** mode.
- Decision panel, top to bottom: location ("Q5 · Halloween shopping"), tier pill, headline, **Why members care** (one
  sentence), **Suggested change** shown as an inline word diff (deleted/inserted) or as "Add answer option". Alternatives appear as
  chips (Recommended · Shorter · Friendlier). A tiny "AI suggestion" tag has a tooltip. "Also affects" lists absorbed same-root
  issues. "Details" hides the long explanation and evidence.
- Actions: **Use this change** (primary; saves and copies), **Keep as is** (secondary; opens reason chips; a chip
  counts as the reason), and **Skip for now** (text).
- After a decision, the toast says "Copied. Paste it into RedJade." with **Undo**. The panel advances to the next item, and focus moves to
  its headline, announced to screen readers.
- Section complete: "All 3 must-fixes handled", then **Continue to quick wins** or **Go to Share**.
- Grouped patterns, such as "Long question on 6 screens", become one card listing each location with its own diff, plus
  **Use all 6 suggestions**. This explicitly saves six individual decisions.

### Chapter 3: Share ("ready to hand off")
- Summary line: "4 changes chosen · 1 kept on purpose · 2 must-fixes still open".
- **Your changes**: grouped by screen, each with a word diff and a copy button. **Copy all changes** is primary.
- **Share with stakeholders**: **Download summary** saves a self-contained HTML file to email or print to PDF.
  A localhost link is useless to a director, so this replaces "open a localhost page".
- **Check your updated survey**: link prefilled. "We'll compare it with this version and show what changed."

## 5. Debates and how they were settled

| Debate | Positions | Decision |
|---|---|---|
| Light vs dark | Marcus and both researchers prefer light: business tool, screenshots into decks. Dana is neutral | **Light, single theme.** Calm white surfaces, one accent blue, semantic colours only for state |
| A single numeric score | Dana wants a viral "Member Experience Score 72". Methodology and Tom object: false precision invites gaming | **No headline number.** Six signal states plus a plan; points stay in "About this review" |
| Emoji and playful tone | Tom: house style. Methodology: accessibility matters when emoji carries meaning | **Survey style setting.** Community & fun: no emoji or one-word-emphasis findings, except emoji-only answers |
| Remove the screen rail | Priya: yes. Elena: "I edit by Q number in RedJade" | Rail becomes an **All screens drawer** with search; numbering is unified everywhere |
| Auto-advance | Marcus: flow. Elena: fears losing context | Advance after an explicit decision only, always with **Undo**, and focus moves predictably |
| Show all 46 findings | Researchers: "don't hide things from me". Priya: "show a plan" | All findings remain reachable under **More ideas**, grouped. The default view shows must-fix plus up to 6 quick wins |
| React + Living Design rewrite | Raj: enterprise polish. Facilitator: the existing codebase is vanilla and the skill exempts it | **No rewrite now.** Apply Walmart-grade tokens and WCAG 2.2 AA in the current stack. Revisit if hosted on AI Launchpad |
| Product analytics | Dana and Raj want activation metrics. Privacy: local-only tool | Run a moderated five-researcher pilot first; defer instrumentation |

## 6. Methodology changes (so signals serve "fun and appealing")
1. **Survey style drives tone checks.** Add `community_pulse` ("Community & fun") to the survey types, with length target 5/8 min.
2. **Same-root absorption.** A blocker absorbs lesser findings with the same root at the same place: B2 absorbs 4.1, 4.3 and 8.4;
   B1 absorbs 5.1–5.3; B7 absorbs 7.1, 7.3 and 7.6; B5 absorbs 1.4 on the same page. Display-only; history and scores are unchanged.
3. **Rubric bookkeeping never reaches prose.** Sentences such as "This finding also covers 4.1 and 4.3" become an
   "Also affects" line using criterion titles.
4. **Screen copy normalisation.** Strip trailing navigation labels (Next/Continue/Submit...) and collapse blank-line runs
   before checks, rewrites and preview.
5. **Strengths are first-class signals**, but only from assessed, full-credit checks in this review.
6. **Stale picks are explained.** If a refreshed suggestion invalidates a saved pick, say "We improved this suggestion
   since you chose it. Choose again" instead of silently reverting.
7. The AI judge prompt learns the community style. Do not flag emoji, exclamation marks or playful voice unless they obscure meaning.

Signals deliberately **not** offered yet (they need data we do not have): measured completion or drop-off, branch-aware
time, measured tap targets and contrast, member satisfaction ratings, benchmark comparisons across surveys.

## 7. Visual direction (Marcus's brief)
- **Mood**: calm, editorial, confident. Think a premium consumer app, not a console. Generous white space, one accent.
- **Palette** (WCAG AA verified, see plan Part B Task 8): background `#F7F8FA`, surface `#FFFFFF`, text `#0F1B2D`,
  muted `#5B6B80`, accent `#0067A0` (Sam's Club blue family), critical `#B42318`, attention `#B54708`, positive `#067647`,
  each with a soft tint.
- **Type**: system UI stack (SF Pro on Mac). Hero 56/700, H1 40, H2 28, H3 22, body 16–18, meta 13 (never below 12).
  Tabular numerals for time.
- **Shape**: radius 12 (controls) / 20 (cards). Shadows are soft and low. No glass, glow or gradient text.
- **Motion**: 120/220/360 ms with an ease-out curve. Diff morph, toast, chapter transitions. Everything respects reduced motion.
- **Rules**: one primary button per view. Default view paragraphs are at most two lines; the rest goes behind "Details". Colour is always
  paired with an icon and a word. The test-response note is the only inline disclaimer; everything else lives in "About this review".

## 8. Copy deck (old → new)

| Today | New |
|---|---|
| Launch surveys members actually finish. | See your survey through your members' eyes. |
| Fix before launch | Must-fix |
| Worth a look | Quick win (top 6) / Idea (rest) |
| Polish | Nice to have |
| Use this | Use this change |
| Keep mine | Keep as is |
| Make this screen better | (removed; the panel speaks for itself) |
| Survey screens | All screens |
| Round 1 | Version 1 |
| Check again | Check updated survey |
| Share for sign-off | Share with stakeholders / Download summary |
| Copy all changes (0) | (hidden until there is at least one change) Copy all changes |
| AI · review the advice | AI suggestion (tooltip: "Written by AI. Read it before using.") |
| About 13.5 min on the captured path | About 13½ minutes for members (estimate) |
| Scope-limited review · not launch approval | (moved to About this review) |
| Info 13 | Message · Screen 13 |
| 25 of 39 checked points | (moved to About this review) |
| Rewrite 1 / Rewrite 2 | Recommended · Shorter · Friendlier |

Forbidden in product copy (tested): "actually finish", "completion rate", "drop-off rate", "will finish",
"guarantee", "approved for launch", "launch-ready".

## 9. Success criteria for the redesign (pilot with five researchers)
- 30-second test: 5 of 5 can say what to fix first and why, after 30 seconds on Overview.
- Time from opening a review to the first decision is under 2 minutes (moderated).
- At least 80% of must-fixes are decided in the first session; "I felt overwhelmed" from at most 1 of 5.
- SUS of at least 80. At least 60% of surveys get a second check within a week.
- Zero fabricated outcome claims (forbidden-phrase test), zero numbering mismatches (unified-label test).

## 10. Decisions (approved by Onder, 3 Nov 2026)
1. **Approved:** light theme as the single theme.
2. **Approved:** **Community & fun** survey style with a 5/8-minute target; emoji treated as voice.
3. **Approved:** UI says **Version** instead of Round (the API keeps `round`).
4. **Approved:** default view shows **Must-fix + up to 6 quick wins**.
5. **Hosting: open.** GitHub Pages was considered and rejected for the working tool. Pages serves static files only;
   SurveyCoach needs a running Python server (Playwright reader, SQLite, server-held Wibey credentials). The repo remote is
   public github.com, so a Pages site would be internet-visible regardless of who is expected to use it. Options:
   AI Launchpad (internal URL, Walmart sign-in, runs the server) for the tool; Puppy Pages for a static, internal demo only.
   Hosting changes "saved on this computer" into a shared service: it needs per-user data separation and sign-in, plus a
   container with Chromium. This becomes Part C once hosting is chosen.

Implementation: `docs/superpowers/plans/2026-11-03-board-redesign-part-a-engine.md` (trust, signals, curation) and
`docs/superpowers/plans/2026-11-03-board-redesign-part-b-experience.md` (visual system and the three chapters).
