# Home redesign ("launch pad")

Date: 2026-11-03. Scope: `site/local.html` (My surveys) only. The review page keeps its layout.

## Problem (from `uglyhome.png`)

- Five grey disclaimer paragraphs compete with one input; nobody reads them.
- Two identical primary buttons (Start review vs. sample), plus a third demo link in the header.
- Content hugs the right; the left 30% of the screen is empty.
- Errors render as plain body copy under helper text.
- Nothing shows the payoff (score, fixes) before the researcher commits a link.
- The empty "My surveys" state is a single sentence.

## Direction

Stays in the dark Studio family (continuity with the review workspace), elevated:

1. **Header**: brand plus a "Private · saved on this computer" pill. No demo link (moved to the footer).
2. **Hero, two columns** (one column under 960px):
   - Left: eyebrow, headline "Launch surveys members actually finish.", one-sentence promise,
     **command bar** (visible label "RedJade preview link", URL input plus inline **Start review**,
     the only primary button), one helper line, then a quiet secondary row:
     "No link handy? Try a sample survey" (ghost button `#sample-start`) and the
     "Import a snapshot file" disclosure (label "Survey snapshot file (.json)").
   - Status `#import-status` (role=status) becomes a toned callout: `progress` (indeterminate bar),
     `error` (red, icon), or info.
   - Right: an **Example result** card (score ring, readiness chip, one must-fix with
     before/after, member minutes). Exposed as one `role="img"` with a descriptive label and
     visibly marked "Example", so it is never mistaken for a real review.
3. **How it works**: three steps: read like a member, score against the rubric (checks plus
   Wibey AI), copy fixes and check again (SurveyCoach never edits RedJade).
4. **My surveys**: responsive card grid. Each card is one link: title, readiness chip,
   must-fix count, version, relative "updated" time. Empty state: a dashed card pointing to
   the hero (no duplicate CTA).
5. **How your data is handled**: three compact items replacing the paragraphs, with no safety
   meaning lost: stays on this computer; AI sees survey wording only (no member responses or
   personal information); approved test links only (the reader may answer and submit synthetic
   test responses, which should be excluded from results; coverage is partial; it never edits
   RedJade). Footer: local pilot, not a launch approval; link to the static demo.

## Data

`GET /api/surveys` adds `readiness`, `must_fix`, and `score_checked` (earned out of checked
points) from the latest review of the latest version, or null if not reviewed. It applies the
same partial-coverage downgrade as `detail()` (one shared helper, no duplicated rule).

## Constraints

- No new dependencies, frameworks, or external fonts/assets (CSP, offline). New `home.css`
  is scoped to `body.home`; `styles.css` and `workflow.css` stay untouched for other pages.
- WCAG 2.2 AA: contrast of at least 4.5:1 for text, 44px targets, visible focus,
  `prefers-reduced-motion`, labelled controls, a status region, no horizontal scroll at 390px.
- Existing contracts: label "RedJade preview link", button "Start review" (exact),
  "Survey snapshot file (.json)", `#import-form`, `#sample-start`, `#import-status`,
  `#survey-list`, and existing error texts.

## Testing

- Existing Playwright suites (start review, workflow, server contracts) stay green.
- New: list API returns readiness fields; home renders a card with a readiness chip and
  must-fix count; an error renders as `data-tone="error"`; no horizontal overflow at 390px;
  the example card is labelled as an example.
