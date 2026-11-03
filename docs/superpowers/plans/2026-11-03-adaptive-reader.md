# Adaptive Reader Implementation Plan

**Goal:** Execute documented rules first, ask Wibey for constrained strategies on failure, and learn only verified progressions locally.

**Architecture:** Existing guarded browser and transport remain authoritative. A typed plan executor accepts observed controls only; a private SQLite store caches scoped provisional rules. The existing Wibey provider supplies JSON, never executable code. Planning receives a separate bounded budget and extends transport deadlines only by actual bounded planning time.

**Constraints:** Approved participant mode only. No arbitrary file uploads, shell actions, DOM JavaScript from the model, credential fields, or cross-origin navigation. All files under 600 lines. Learned rules store structural selectors and synthetic answers, not question wording. Unknown strategies cannot override transport policy.

- [ ] Add typed strategy models, scoped widget signature, and local rules storage. Tests reject arbitrary operations, selectors and secret-bearing values; verify success/failure counters.
- [ ] Add executor and planner integration. Tests exercise fake-model fallback, validation-only non-success, learned reuse, failed-rule quarantine, and passive-mode isolation.
- [ ] Wire reader session and server provider with bounded calls/time, preserving captures and honest coverage. Run full suite.
- [ ] Trace real media widget state privately, repair observed save sequence, add synthetic regression. Never infer successful completion from upload HTTP status.
- [ ] Document rules and lifecycle; run code review, tests and authorized live checks; commit and restart local server.

Verification commands: `.venv/bin/python -m pytest -q` and `git diff --check`. Live diagnostics output only counts/state, not survey wording or tokens. Rule success requires source-page/question transition or terminal evidence, not changed validation text.
