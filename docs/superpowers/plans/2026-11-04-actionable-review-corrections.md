# Actionable review corrections

User approved implementation of seven review clarity/correctness fixes.

- [ ] Timing/welcome: avoid double-counting rendered question copy; clarify member effort vs crawling, heuristic targets and uncertainty; recognize actual topical welcome; grounded missing welcome example without invented promises. Worker owns timing.py/snapshot.py/checks/structure.py/tests.
- [ ] Reading/choices: accessible reading warning with conservative concrete rewrite; long-list threshold not optimum, actionable supplied-choice guidance preserving data distinctions. Worker owns checks/content.py/phone.py/helpers/tests.
- [ ] UI: show actual manual action instead of generic fallback; accurate no-issues/category/handled states; visible compact energy meaning/legend. Worker owns queue.js/energy.js/coach.js/CSS/tests.
- [ ] Images: state observed load not verified; no proven network or size causality; mobile verification, conditional re-upload/compression preserving fidelity; failed dimensions not shape evidence. Parent owns images.py/phone.js/image tests.
- [ ] Integration: independent focused review, fix regressions, full nonlive suite, offline recheck captured approved survey into a NEW temporary local database and server, preserve prior reviews; no further live participant writes needed, no push/deploy, preserve staged progress/screenshots.

Test-first per feature, exact deterministic evidence, no schema migration unless necessary, no fixed survey-specific whole-text hacks, files under600lines. No real captured content committed or sent to browser-QA persistent agent. Rules-only review remains explicitly rules-only.
