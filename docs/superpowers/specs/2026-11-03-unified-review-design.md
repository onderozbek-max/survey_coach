# Unified SurveyCoach review — revised design

Status: proposed, incorporating Onder's clarification. Reader bug fix is separate.

## Shared design system

Extract reusable tokens and components from the homepage into a shared stylesheet:
app shell/header, navigation, typography scale, spacing, buttons, panels, score summaries,
readiness chips, notices, focus states and responsive layouts. Homepage, saved review,
phone workspace and exported HTML report consume those definitions. No independent
page-specific reinterpretations of the same component. Keep the existing vanilla stack;
no framework migration. Browser phone content remains visually distinct from app chrome.

## Information architecture

One saved-review workspace replaces the two competing review interfaces. Home and review
completion open the workspace. Existing saved-review links remain valid. Summary shows
checked points, must-fix count, estimated time and honest capture limitations. Screen rail,
phone preview and contextual recommendations form the desktop workspace; mobile switches
between Survey and Recommendations with explicit navigation. All issues is an alternate
view inside the workspace. Recheck, version selection and researcher choices persist.
Export review report is an action, not a competing destination or a purported publicly
shareable local URL. Captured screens remain accessible as evidence, clearly separated
from the reconstructed phone view.

## Image placeholders and mobile reminder

Actual image bytes are not a prerequisite. Render page-, question- and option-level media
as explicitly labelled placeholders. Retain measured natural and rendered dimensions;
use observed rendered proportions when available, natural proportions otherwise. Unknown
dimensions remain unknown, not square by assertion. Landscape images receive a contextual
"Check on mobile" reminder: verify readability, cropping, distortion and content size on
a real mobile device. Orientation alone is a potential risk, not proof of a broken image.
Never automatically crop research stimuli or imply imagery was captured when it was not.
Separate rubric shape preferences from verified broken-image launch blockers.

## Recommendation quality

Reject fill-in-the-bracket rewrites at validation, not just prompting. Do not invent purpose,
invitation reasons, purchases, rewards or outcomes. A finding has one of three presentations:
complete grounded rewrite; explicitly labelled complete starting-point inspiration; or
specific action required with explanation and no rewrite. No fake copy controls or original-
versus-suggestion choices for findings without usable copy. Existing stored/cached placeholder
suggestions must be suppressed too. Prompt-version bump prevents old cached generation reuse.

## Upload-validation bug

Reproduced locally: validation that modifies a prompt changes state_key and was incorrectly
counted as progression; inline media-uploader detection depended on a still-present file
input, allowing Add Media to create an extra empty required answer after input removal.
Targeted fixes reject visible validation as next-page success and identify the inline widget
independently of its file input. Regression tests use synthetic local browser fixtures.
Live RedJade completion remains unverified. Prior saved reviews are not silently rewritten;
new reader behavior requires a fresh reread.

## Acceptance

- Homepage and all local review/report surfaces share tokens and component rules.
- One primary workspace; durable old links and persisted decisions survive.
- Page-level images are no longer omitted; portrait/landscape/unknown placeholders are honest.
- Landscape reminders appear next to imagery without asserting automatic failure.
- No incomplete placeholder recommendations or invented missing facts; old results protected.
- Validation screen is not counted as successful progression, Add Media never creates an
  accidental extra slot for the inline uploader, failed uploads retain partial coverage.
- Feature-isolated API and Playwright tests, mobile/desktop visual inspection, keyboard,
  contrast, touch targets, reduced motion and no horizontal overflow.
