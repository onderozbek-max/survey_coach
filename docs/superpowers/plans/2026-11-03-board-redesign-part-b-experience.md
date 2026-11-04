# Board redesign, Part B: the experience (visual system and three chapters)

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans. **Prerequisite:** Part A is merged (`screens`, `plan`, `overview`, `also_affects`,
> `stale_pick` and `survey_type` exist in the detail payload and in `data.js`).

**Goal:** Turn the workspace into one calm story, **See → Improve → Share**, with a light, premium visual system
that non-technical researchers find effortless. Spec: `docs/superpowers/specs/2026-11-03-board-review.md` sections 4, 7 and 8.

**Architecture:** Keep vanilla HTML/CSS/JS and the `SC` namespace. `review.html` becomes a three-chapter shell routed
by URL hash (`#overview`, `#improve`, `#share`). The renderers read the Part A payload and never re-derive numbering,
grouping or signals. Decision saving (`coach.js` → `PUT .../decisions/{fp}`) is reused unchanged.

**Why not React + Living Design:** the Living Design skill exempts existing non-Living-Design codebases. This plan applies
Walmart-grade tokens and WCAG 2.2 AA in the current stack. Revisit only if the product moves to AI Launchpad hosting.

## Global constraints
- Same as Part A (no stored mutation, no fabricated outcomes, files under 600 lines, commit per task).
- **Taste rules (reviewed in every PR):** one primary button per view; at most three type sizes per component;
  default-view paragraphs at most two lines (more goes behind "Details"); colour always paired with an icon and a word;
  meta text at least 12px; motion at most 360ms and disabled under `prefers-reduced-motion`; the test-response note is the only
  inline disclaimer.
- WCAG 2.2 AA: 4.5:1 text, 3:1 UI boundaries; targets at least 24px (aim for 44px); focus never hidden by sticky bars
  (`scroll-padding-top`); "About this review" in the same place on every chapter (consistent help); the recheck link
  is prefilled (redundant entry).
- Existing e2e tests assert old copy and selectors (`Keep mine`, `Use this`, `Compare wording`, `Play as a member`,
  `Copy all changes`, `Share for sign-off`, `Large text`, `Fix before launch`). Update them to the new contract in the same
  task that changes the UI. Keep every safety assertion.
- Update `tests/test_issue_loop_ui.py::open_review` to load `review.html?id=synthetic#improve` and add
  `open_overview()` for `#overview`.

## File map

| File | Status | Responsibility |
|---|---|---|
| `site/design-system.css` | rewrite | Tokens and base components (light theme, single source of colour) |
| `site/styles.css`, `home.css`, `review-studio.css`, `workflow.css` | modify | Use tokens only; delete dead dark-theme rules |
| `site/icons.js` | new | Inline SVG icon set (`SC.icon(name)`) |
| `site/chapters.js` | new | Hash router, chapter nav, focus management |
| `site/overview.js` + `site/overview.css` | new | Chapter 1 |
| `site/energy.js` | new (replaces `journey.js`) | Energy map, full and compact |
| `site/diff.js` | new | `SC.wordDiff` + `SC.renderDiff` |
| `site/toast.js` | new | Toast with Undo, live region |
| `site/queue.js` | new | Improve-chapter queue over `detail.plan` |
| `site/coach.js` | modify | Decision panel markup and copy |
| `site/phone.js` | modify | Margin markers, soft highlight, ghost added answers, `SC.cleanCopy` |
| `site/model.js` | modify | Use `survey.screens` for names; add `SC.cleanCopy` |
| `site/share.js` | new | Chapter 3 |
| `site/about.js` | new | "About this review" and "How we handle data" sheets |
| `site/local.html`, `site/review.html`, `site/index.html` | modify | New shell and copy |
| `scripts/capture_screens.py` | new | Before/after screenshots for the board |

---

### Task 1: Visual foundation (tokens and base components)

**Files:** rewrite `site/design-system.css`; sweep the other CSS files. Test: `tests/test_design_tokens.py`.

- [ ] **Step 1: Failing test**

```python
import re
from pathlib import Path
SITE = Path(__file__).resolve().parent.parent / "site"
CSS = (SITE / "design-system.css").read_text()

def token(name):
    return re.search(rf"--{name}:\s*(#[0-9A-Fa-f]{{6}})", CSS).group(1)

def lum(hex_):
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

def contrast(a, b):
    hi, lo = sorted((lum(token(a)), lum(token(b))), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

TEXT_PAIRS = [("text", "bg"), ("text", "surface"), ("muted", "surface"), ("muted", "bg"), ("muted", "surface-2"),
              ("accent", "surface"), ("on-accent", "accent"), ("accent", "accent-soft"),
              ("critical", "critical-soft"), ("attention", "attention-soft"), ("positive", "positive-soft")]

def test_text_pairs_meet_aa():
    for fg, bg in TEXT_PAIRS:
        assert contrast(fg, bg) >= 4.5, (fg, bg)

def test_control_boundaries_meet_3_to_1():
    assert contrast("line-strong", "surface") >= 3 and contrast("line-strong", "bg") >= 3

def test_colour_lives_only_in_tokens():
    for css in SITE.glob("*.css"):
        if css.name == "design-system.css":
            continue
        assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", css.read_text()), css.name
```

- [ ] **Step 2: Tokens.** Replace `:root` in `design-system.css` with these values (all verified with the test above:
  muted/surface 5.44, accent/surface 6.09, line-strong/surface 3.77):

```css
:root {
  --bg:#F7F8FA; --surface:#FFFFFF; --surface-2:#F1F4F8; --line:#E3E8EF; --line-strong:#74859A;
  --text:#0F1B2D; --muted:#5B6B80; --accent:#0067A0; --accent-soft:#E6F1F8; --on-accent:#FFFFFF;
  --critical:#B42318; --critical-soft:#FEF3F2; --attention:#B54708; --attention-soft:#FFFAEB;
  --positive:#067647; --positive-soft:#ECFDF3; --mark:#FFF1B8;
  --zone-fresh:#B9D9EC; --zone-builds:#F6D28B; --zone-high:#F2A99F;
  --phone-bg:#FFFFFF; --phone-text:#1D2939; --phone-frame:#0F1B2D;
  --shadow-1:0 1px 2px rgba(16,24,40,.06); --shadow-2:0 4px 16px rgba(16,24,40,.08); --shadow-3:0 16px 48px rgba(16,24,40,.14);
  --font:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --fs-12:12px; --fs-14:14px; --fs-16:16px; --fs-18:18px; --fs-22:22px; --fs-28:28px; --fs-40:40px; --fs-56:56px;
  --r-sm:8px; --r-md:12px; --r-lg:20px; --r-pill:999px;
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-5:24px; --s-6:32px; --s-7:48px; --s-8:64px;
  --ease:cubic-bezier(.2,.8,.2,1); --dur-1:120ms; --dur-2:220ms; --dur-3:360ms;
  --content:1200px; --bar:64px;
}
```

  (`rgba` is permitted only inside `design-system.css`.)
- [ ] **Step 3: Base components** in `design-system.css`: `body` (bg, text, font, 16px/1.5, antialiased,
  `font-variant-numeric: tabular-nums` on `.num`), `h1–h3` (40/28/22, weight 650–700, letter-spacing -0.02em),
  `.btn` (44px, radius md, 0 20px), `.btn-primary` (accent / on-accent), `.btn-secondary` (surface, 1px line-strong,
  text), `.btn-text` (accent, no border), `.card` (surface, 1px line, radius lg, shadow-1, padding 24),
  `.pill[data-tone=critical|attention|positive|neutral]` (soft background + strong text + icon), `.meta` (13px muted),
  `:focus-visible` (3px accent outline, 3px offset), `html { scroll-padding-top: calc(var(--bar) + 72px) }`, and the
  reduced-motion reset. Delete glass, gradients, glow and the dark radial background.
- [ ] **Step 4: Sweep.** Replace every hex and rgba value in the other CSS files with a token. Phone simulation uses `--phone-*`.
  Delete rules for removed UI (rail chrome, journey, duplicate next, review toolbar).
- [ ] **Step 5:** Run the full suite. Visually check `local.html` and `review.html` at 1440 and 390 (screenshots in Task 11).
- [ ] **Step 6: Commit:** `Introduce light design tokens and token-only styling`

### Task 2: Icons, diff, toast (small shared primitives)

**Files:** create `site/icons.js`, `site/diff.js`, `site/toast.js`. Test: `tests/test_ui_primitives.py` (Playwright,
evaluate in page).

- [ ] **Step 1: Tests:** `SC.wordDiff("How satisfied are you with the taste and price?", "How satisfied are you with the taste?")`
  returns exactly `[{type:'same',text:'How satisfied are you with the taste'},{type:'del',text:' and price'},{type:'same',text:'?'}]`. `SC.icon("check")` returns an
  `svg` with `aria-hidden="true"` and `focusable="false"`. `SC.toast("Copied", {undo})` renders `#toast` inside a polite live region; clicking
  `#undo` calls `undo` once; the toast dismisses after 6s or on Escape.
- [ ] **Step 2: `diff.js`**

```js
/* Word-level before/after, shared by the decision panel, the change list and nothing else. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.wordDiff = (before, after) => {
    const tokens = s => (s || '').split(/(\s+|[.,!?;:]+(?=\s|$))/).filter(Boolean);   // trailing punctuation is its own token
    const a = tokens(before), b = tokens(after), n = a.length, m = b.length;
    if (n * m > 40000) return [{type:'del', text:before}, {type:'ins', text:after}];
    const dp = Array.from({length:n + 1}, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = [], push = (type, text) => {
      const last = out[out.length - 1];
      if (last && last.type === type) last.text += text; else out.push({type, text});
    };
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { push('same', a[i]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) push('del', a[i++]);
      else push('ins', b[j++]);
    }
    while (i < n) push('del', a[i++]);
    while (j < m) push('ins', b[j++]);
    return out;
  };
  SC.renderDiff = (before, after) => h('p', {class:'diff'}, SC.wordDiff(before, after).map(s =>
    s.type === 'same' ? s.text : h(s.type, null, s.text)));
})();
```

  Verified in Node: the taste/price example yields `[same "How satisfied are you with the taste", del " and price", same "?"]`;
  `"...celebrated!"` → `"...celebrated! This takes about 14 minutes."` yields one `ins` segment. Use both as test cases.
- [ ] **Step 3: `icons.js`:** `SC.icon(name, {size=18})` returns an inline 24×24 SVG, with `stroke="currentColor"`, stroke-width
  1.75, round caps, built with `document.createElementNS`. The set covers check, alert, clock, sparkle, lock, copy, undo,
  arrow-right, eye, play, pause, chevron-down, list, share, download, text-size, dot and minus. Draw them in the style of the existing
  inline SVGs in `local.html` (simple strokes, no fills).
- [ ] **Step 4: `toast.js`:** a single `#toast-region` (`role="status"`, `aria-live="polite"`) appended to `body`, with one toast at a time.
- [ ] **Step 5: Commit:** `Add icon, word-diff and toast primitives`

### Task 3: Chapter shell and router

**Files:** create `site/chapters.js`; modify `site/review.html`, `site/index.html`, `site/app.js` (call into chapters,
remove the toolbar, rail container and journey mount). Test: `tests/test_chapters_ui.py`.

- [ ] **Step 1: Tests:** opening `review.html?id=synthetic` shows `#chapter-overview`, with `#chapter-improve` and
  `#chapter-share` hidden. `#chapter-nav a[data-chapter=overview]` has `aria-current="step"`. Clicking Improve updates the
  hash, moves focus to the chapter `h2`, and Back returns to Overview. A `surveycoach-focus-finding` event switches to Improve.
  At 390px the nav fits with no horizontal overflow.
- [ ] **Step 2: Markup (`review.html`, replacing the body content of `<main>`):**

```html
<header class="app-bar">
  <a href="local.html" class="brand">SurveyCoach</a>
  <nav id="chapter-nav" aria-label="Review steps">
    <a href="#overview" data-chapter="overview"><span class="step-n">1</span> Overview</a>
    <a href="#improve" data-chapter="improve"><span class="step-n">2</span> Improve</a>
    <a href="#share" data-chapter="share"><span class="step-n">3</span> Share</a>
  </nav>
  <a href="local.html" class="btn-text">My surveys</a>
</header>
<main id="workspace">
  <section id="chapter-overview" aria-labelledby="overview-h"></section>
  <section id="chapter-improve" aria-labelledby="improve-h" hidden></section>
  <section id="chapter-share" aria-labelledby="share-h" hidden></section>
  <footer class="chapter-foot"><button type="button" id="about-review" class="btn-text">About this review</button></footer>
</main>
```

- [ ] **Step 3: `chapters.js`:** `SC.CHAPTERS = ['overview','improve','share']`; `SC.currentChapter()` reads
  the hash (default `overview`); `SC.goChapter(name, options)` uses `pushState` then `SC.showChapter`;
  `showChapter` toggles `hidden`, sets `aria-current`, focuses the chapter heading with `{preventScroll:true}` and scrolls to top
  (instant under reduced motion), then dispatches `surveycoach-chapter` with `{name, options}`; it also listens to `popstate`.
  Each chapter renderer subscribes and renders lazily on first show.
- [ ] **Step 4: Commit:** `Introduce the three-chapter review shell`

### Task 4: Chapter 1, Overview

**Files:** create `site/overview.js`, `site/overview.css`, `site/energy.js` (delete `journey.js` and move
`previewReadingDelta` into `energy.js`). Test: `tests/test_overview_ui.py`.

- [ ] **Step 1: Tests (DOM contract):**
  - `#overview-headline` text equals `detail.overview.headline`; `#overview-subline` equals `subline`.
  - `#signals li[data-signal]` count is 6; each has `.signal-state` with the state label and an icon; tiles are not clickable
    themselves, but `button.signal-link` goes to Improve filtered to that signal's first page.
  - `#energy-map button.energy-bar` count equals the number of screens; each `aria-label` reads like
    "Q8–Q18, about 188 seconds, estimate, tiring, 1 must-fix"; clicking goes to `#improve` on that screen. The caption
    contains "estimate".
  - `#strengths li` count is at most 3 and is absent (no heading) when empty.
  - `#start-improving` is the only `.btn-primary` in the chapter. `#preview-member` is secondary.
  - `#survey-style` radio group with five options. Choosing "Community & fun" sends
    `PATCH {"survey_type":"community_pulse"}`, re-fetches detail, re-renders, and announces "Survey style saved".
  - A generic title (`Surveys`, `Survey`, `Untitled`) shows `button#name-survey` "Name this survey" (inline edit using the
    existing PATCH title).
  - No `.pill` reads "Scope-limited", and no "checked points" text.
- [ ] **Step 2: Layout (desktop ≥ 1100px, container 1200):**
  1. Hero grid `7fr 5fr`. Left: `.meta` "Version {round} · checked {relative time}", `h2#overview-h` = title,
     `p#overview-headline` (28px/650), `p#overview-subline` (18px muted), action row. Right: a mini phone (scale 0.72,
     non-interactive, `aria-hidden`) rendering the first must-fix screen with its highlight, captioned for screen readers by
     the headline.
  2. `h3` "Member experience" and a `ul#signals` 3×2 grid of cards: icon + name (16/600), state pill, summary (14 muted,
     2 lines max), and `signal-link` "See {n} screen(s)".
  3. `h3` "Energy map" and the full-width `#energy-map` (bars height ∝ seconds, max 96px; colour = zone token; a must-fix dot
     above the bar; labels below, never clipped: rotate nothing, truncate with an ellipsis plus a title, and show every other label when
     there are more than 14 screens). Legend: Fresh · Getting tiring · Tiring (swatch + word). Caption: "Heaviest: {name} (about {s}s).
     Reading and tapping estimate; real completion is not measured."
  4. Two columns: `#strengths` "What members will like" (check icons) | `#plan-summary`: three rows (Must-fix n ·
     Quick wins n · More ideas n), each a text button into Improve on that tab.
  5. `fieldset#survey-style` with legend "What kind of survey is this?" and segmented radios: Community & fun · Product test ·
     Home-use test · Concept or services · Market research. Helper: "Sets length targets and how we treat playful voice."
- [ ] **Step 3: Mobile (< 760px):** single column; mini phone hidden; signals 1 column; energy map horizontally
  scrollable with snap and a visible "Swipe for more" hint; sticky bottom bar with `#start-improving`.
- [ ] **Step 4: Preview as a member.** `#preview-member` opens a full-viewport dialog (`<dialog>`, focus trapped,
  Escape closes) with the phone at 390px advancing at the estimated reading pace, Pause/Play, the elapsed estimate, and the compact energy map
  as a scrubber. Reuse the existing playback timer logic from `app.js` (move it into `energy.js`; do not duplicate it).
- [ ] **Step 5: Commit:** `Add the Overview chapter with signals, energy map and plan`

### Task 5: Chapter 2, Improve (layout, queue, decision panel)

**Files:** create `site/queue.js`; modify `site/coach.js`, `site/issue-list.js` (becomes the All screens drawer), and
`site/review-studio.css`. Tests: `tests/test_improve_ui.py`, plus updates to existing decision e2e tests.

- [ ] **Step 1: Tests:**
  - `#queue-tabs [role=tab]` reads "Must-fix 1/3", "Quick wins 0/6", "More ideas". Counts come from `detail.plan`; absorbed
    findings never appear.
  - The panel shows: `.location` (from `survey.screens`, identical to the phone bar prefix); a `.pill` tier ("Must-fix" /
    "Quick win" / "Nice to have"); `h3.headline`; `p.why` (member impact, one sentence); `.suggested` with
    `SC.renderDiff(original, recommended)` or, for answer additions, "Add answer option" plus the option text; `.alternatives`
    chips when more than one option exists (labels from the option's `label`, defaulting to Recommended/Shorter/Friendlier by position); `.also-affects` listing absorbed
    headlines; `details.more` holding explanation and evidence.
  - `#use-change` saves `pick` and copies the text (existing logic). The toast says "Copied. Paste it into RedJade." with Undo.
    Undo restores the previous decision (PUT the prior object, or `{action:"open"}` if none). The panel then advances to the
    next undecided item; focus lands on its `h3`; the live region announces "Next: {headline}".
  - `#keep-as-is` opens reason chips ("Intentional for this study", "Matches a tracker / keep comparable",
    "Stakeholder requirement", "Not accurate", "Other…"). Choosing a chip saves `keep` with that reason. "Other…"
    requires text. Nothing saves before a choice.
  - `#skip` moves on without saving.
  - `stale_pick` decisions show the note "We improved this suggestion since you chose it. Choose again."
  - Pattern items (`count > 1`) list each location with its own diff and per-row Use/Keep buttons, plus
    `#use-all` "Use all {n} suggestions", which saves n individual picks (assert n PUTs), with one toast and Undo restoring all.
  - With all must-fixes decided, the panel shows "All {n} must-fixes handled" with `Continue to quick wins` (primary)
    and `Go to Share`.
  - There is no `#rail`, `.journey`, `#review-toolbar` or duplicate "Next issue" in the DOM.
- [ ] **Step 2: Layout:** sticky sub-bar (56px, below the app bar): `#queue-tabs` on the left, the compact `SC.renderEnergyMap(...,
  {compact:true})` in the centre, and on the right `button#all-screens` (drawer) plus a segmented `Original | With changes`. Body grid:
  `minmax(340px, 400px) minmax(0, 560px)`, centred, gap 48. The phone is sticky. The panel scrolls with the page.
- [ ] **Step 3: Drawer:** `#screen-drawer` is a `<dialog>` from the left with `input[type=search]` (matches Q label or topic words)
  and a list of screens with name, topic and a small severity dot plus an sr-only count. Selecting a screen closes the drawer, shows that
  screen, and selects its first open item.
- [ ] **Step 4: Copy:** apply the copy deck (spec section 8) to every string in `coach.js` and `issue-list.js`. Hide
  "AI suggestion" unless `f.source === "ai"`; it renders as a neutral pill with a sparkle icon and tooltip "Written by AI. Read it
  before using."
- [ ] **Step 5: Commit:** `Rebuild Improve as a focused one-thing-at-a-time queue`

### Task 6: The phone, quieter and more truthful

**Files:** `site/phone.js`, `site/model.js`. Test: `tests/test_phone_preview.py` (extend the existing preview tests).

- [ ] **Step 1: Tests:**
  - `SC.cleanCopy` passes every case in `tests/fixtures/clean_copy_cases.json` (same file as the Python test).
  - Welcome screen text in the phone contains no trailing "Next" text node. A real `div.next` button still renders once.
  - No `.pin` element sits inside a `p.q-text`. Markers are `.phone-marker` buttons positioned in the right gutter of
    the flagged block, with `aria-label` "Must-fix: {headline}".
  - In With changes mode, an answer-addition finding renders `li.suggested-option` with a dashed border, the text, and the visually
    hidden prefix "Suggested answer:". In Original mode it is absent.
  - Phone bar text equals `{screens[i].name} · Screen {i+1} of {n}`.
  - "Large text" moved into a `button#phone-settings` menu ("Aa"). The menu also holds the device size.
- [ ] **Step 2: Implement:** `SC.cleanCopy` (port of Part A `clean_copy`; identical regex semantics) is used in
  `renderPage`, `SC.pageTexts` and `SC.hitsOn` for `page.text`/`intro_text`. `mark` uses `--mark` background with a 2px
  underline in the tier colour. Remove numbered pins from text flow.
- [ ] **Step 3: Commit:** `Quiet the phone: clean copy, gutter markers, suggested answers`

### Task 7: Chapter 3, Share

**Files:** create `site/share.js`; modify `site/rounds.js` (version comparison moves here), `site/review.html`.
Test: `tests/test_share_ui.py`.

- [ ] **Step 1: Tests:**
  - `#share-summary` reads "{a} changes chosen · {k} kept on purpose · {o} must-fixes still open" (from decisions and plan).
  - `#change-list` is grouped by screen (`h3` = screen name); each `li` has `SC.renderDiff` (or "Add answer option") and a copy button.
    `#copy-all` is the only primary button and is hidden when there are zero changes.
  - `#download-summary` links to `.../summary?download=1`.
  - `#recheck-form` input is prefilled with the last checked link when known; the helper says "We'll compare it with this version
    and show what changed." Submitting uses the existing recheck flow.
  - When `round > 1`, a "Since version {n-1}" block shows fixed / still open / new, using existing `round_changes` data and the
    same honesty labels.
- [ ] **Step 2: Commit:** `Add the Share chapter with change list, download and recheck`

### Task 8: Home

**Files:** `site/local.html`, `site/home.css`, `site/workflow.js` (survey cards, reading state), `site/about.js`.
Test: update `tests/test_home_page.py`.

- [ ] **Step 1: Tests:**
  - `h1` reads "See your survey through your members’ eyes." and contains no forbidden phrase.
  - Exactly one visible notice line under the input:
    "Test links only · Wording is reviewed by Walmart-approved AI · Creates a test response to exclude from results."
    plus `button#data-handling` "How we handle data", which opens a `<dialog>` holding the three former trust cards and the
    pilot note.
  - `#sample-start` "Try a sample survey" still works (existing flow).
  - Survey cards: title (or "Untitled survey"), one status pill ("{n} must-fixes" / "Ready to share" / "Checking…"), six
    signal dots (`aria-label` "Time: Needs attention, Clarity: Looking good, …"), and `.meta` "Version {n} · {relative time}".
    The whole card is a link (one tab stop) to `review.html?id=…#overview`. No "checked points" text.
  - There is no `section.steps` grid; a slim `ol.narrative` reads "See · Improve · Share" with icons.
  - The example figure animates the strike-through to insertion once on load (CSS only) and is static under reduced motion.
  - Reading state: centred phone, `#reading-progress` "Reading screen {n}…", and three steps with check icons driven by
    existing job status; no new backend.
- [ ] **Step 2: Commit:** `Redesign Home around one input and one promise`

### Task 9: About this review (consistent help)

**Files:** `site/about.js`. Test: in `tests/test_chapters_ui.py`.

- [ ] **Step 1:** `#about-review` on every chapter opens a `<dialog>` with: What we checked (n of m checks, from
  `presentation.scope`); What we didn't check (unvisited paths, unchecked checks); Reconstructed preview (verify on a phone
  in RedJade); AI suggestions (written by Walmart-approved AI; read before using); Your data (local only). This is the
  **only** home for those caveats. Delete them from headers, footers and toolbars.
- [ ] **Step 2: Commit:** `Move review caveats into one consistent About sheet`

### Task 10: Copy sweep and claims guard

- [ ] **Step 1:** Apply the copy deck everywhere (including `rounds.js`, `report.py` strings and `index.html`). UI says
  "Version"; the API keeps `round`.
- [ ] **Step 2:** Remove the `xfail` from `tests/test_copy_guard.py` (Part A Task 10); it must pass.
- [ ] **Step 3:** Regenerate `site/data.js` via the demo export so the public demo has `screens/plan/overview`.
- [ ] **Step 4: Commit:** `Apply the board copy deck and enforce the claims guard`

### Task 11: Proof for the board (screenshots and checklist)

**Files:** create `scripts/capture_screens.py`. Output goes to `review/after/` (never overwrite `review/*.png`).

- [ ] **Step 1: Script:** copy the user's DB to a temp file (or start empty and `POST /api/samples/boxer-briefs`), start
  uvicorn on a free port in the background, wait for the job, then capture with Playwright at 1440×900 and 390×844:
  `home`, `overview`, `improve` (first must-fix), `improve-pattern` (a grouped item), `share`, `preview-member`. Stop the server.
  Print the file list.
- [ ] **Step 2:** Run it and open the images. Walk the board checklist and record the results in
  `docs/superpowers/specs/2026-11-03-board-redesign-delivery.md`:
  - [ ] Within 5 seconds on Overview, the headline says what to fix first.
  - [ ] One primary button per view; no paragraph longer than two lines by default.
  - [ ] Rail, phone, card, change list and summary all show the same Q label for the same question.
  - [ ] No "Next" in any rewrite; no blank-line gaps in quotes.
  - [ ] No rubric IDs in visible prose; absorbed issues appear only under "Also affects".
  - [ ] With Community & fun, no emoji or one-word-caps findings.
  - [ ] Default view shows at most 3 + 6 actionable items; everything else lives under More ideas, grouped.
  - [ ] The test-response note is the only inline disclaimer; About this review is reachable from every chapter.
  - [ ] Keyboard-only run: complete one must-fix, Undo it, finish via Share; focus is always visible and never under a sticky bar.
  - [ ] 390px: no horizontal overflow; the bottom action bar does not cover content.
  - [ ] Reduced motion: no animation, and the flow still works.
- [ ] **Step 3:** Run the full suite and commit: `Capture board before/after screens and delivery checklist`

## Sequencing and size guidance for the implementing model
1. Part A Tasks 1–10, in order (each is small and independently green).
2. Part B Tasks 1–2 (foundation), then 3 → 4 → 5 → 6 → 7 (each chapter is shippable on its own), then 8–11.
3. If a task's diff exceeds about 400 lines, split it at a natural seam (markup / behaviour / styles) and commit each.
4. Never introduce a framework, bundler or CDN. Never add network calls beyond the existing API.

## Explicitly out of scope (recorded so nobody "helpfully" builds it)
- A numeric headline score, leaderboards or benchmarks across surveys.
- Measured completion/drop-off, branch-aware timing, or automated tap-target and contrast measurement of RedJade.
- Analytics or telemetry. The pilot is moderated (spec section 9).
- React or Living Design migration, and hosting (separate AI Launchpad track; decision 5 in the spec).
- Dark theme.
