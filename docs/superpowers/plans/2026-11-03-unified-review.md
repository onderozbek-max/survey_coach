# Unified review implementation plan

Approved direction: docs/superpowers/specs/2026-11-03-unified-review-design.md.
Execute autonomously; existing vanilla UI exemption from Living Design scaffold applies.

- [x] Recommendation guard: test and suppress incomplete template rewrites during grounding and saved-review reads; bump prompt version. Dedicated backend worker owns judge/repository.
- [x] Shared design system: site/design-system.css consumed by home, review, demo, and embedded in exported report; shared shell/header, buttons, chips, panels, notices and typography. Preserve base phone styling.
- [x] Canonical workspace: review.html embeds phone/coach and All issues tab plus recheck. workflow.js retains persisted checklist decisions and recheck. app.js uses same detail/version, links and updates without a second destination. Root serves homepage, index.html?id redirects to canonical review; static demo stays index.html.
- [x] Image reminders: phone.js renders page media plus proportional question/option media, natural/rendered orientation labels and landscape mobile check; unknown size explicit. No image-byte retrieval or auto-crop.
- [x] Verification: isolated Playwright contracts cover canonical navigation, tabs, existing saved records, image proportions/reminders, export style and template-free actionable findings. Run complete pytest and diff checks; inspect desktop/mobile DOM and screenshots where tools permit; commit and restart loopback server.
