# Phone-first review correction

Onder rejected b837cf1's dashboard-like composition and gave creative freedom to restore
phone preview as the product centrepiece, with polished treatment and coherent narrative.

Root causes reproduced: phone top at727px in synthetic saved review, remembered All issues
tab hid preview after reload; review-tools block, duplicate summaries, disclaimers, coach
report and padded boxes displaced the actual experience. Tests previously checked existence,
not the primary experience's prominence.

Narrative: explore the survey, experience it as a member, refine the current screen.

Implementation:
- review-studio.css composes a quiet screen list, unboxed phone stage, contextual coach.
- Compact title/verdict; version/export/bulk-copy are secondary Review tools disclosure.
- Every arrival opens survey view and first actual question, not whole-survey/admin/intro stub.
- Source/read coverage and recheck below preview as honest disclosures; no duplicate coach report.
- Device gets a precise frame, white readable survey surface, soft emphasis and24px pins.
- Unknown response controls get honest explanatory representation, not empty options list.
- Info text preserves line breaks; scale/grid absent data cannot crash the whole phone render.
- Mobile phone first; shorter390px content viewport and immediate coach jump; full content scrollable.
- Checklist finding offers See on the phone, preserving selected location and saved decisions.
- Home and shared design foundations remain; no React rewrite in existing vanilla app.

Acceptance: desktop1440x900 phone top<300px, screen height>=450px; mobile390x844 phone top<430px,
no horizontal overflow; reload always visible phone; persisted decisions/rechecks/export retained.
Use actual saved survey read-only for visual QA, fixtures for browser mutations.
Do not confuse true sparse source content with missing rendering or manufacture member copy.
