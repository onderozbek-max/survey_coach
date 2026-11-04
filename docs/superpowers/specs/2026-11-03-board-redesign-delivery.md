# Board redesign delivery — Part B Task 11

## Scope and evidence status

Capture tooling and offline evidence are delivered. **Visual acceptance is pending.**
No image was opened with a vision tool or visually inspected by this worker.
Programmatic PNG decoding, dimensions, DOM metrics and passing UI contracts are
not claims about visual quality, five-second comprehension or human usability.
The parent reviewer performs that QA separately.

- Original capture baseline: `5a663c9`, branch `feature/surveycoach-mvp`.
- Final fix/capture baseline: `cddfe9b` (from final review base `899f4ce`).
  All seven reviewed P2s plus modal routing and finite timeout P3s fixed.
  Full report: `.superpowers/sdd/final-fix-report.md`.
- Runner: `scripts/capture_screens.py` (no production UI/style changes).
- Default captures: `review/after/{desktop,mobile}-{home,overview,improve,
  improve-pattern,share,preview-member}.png` (12 files).
- Reduced-motion captures: same names under `review/after/reduced-motion/`.
- Machine evidence: `review/after/evidence.json` and
  `review/after/reduced-motion/evidence.json` (viewport metrics, hashes,
  provenance, browser diagnostics, cleanup, explicit uninspected status).
- Logs: `review/after/capture.log`, `reduced-motion-capture.log`,
  `full-nonlive-tests.log`, and each capture directory's `server.log`.
- Full-page screenshots use 1440×900 and 390×844 browser viewports; image height
  may exceed the viewport. They are not viewport-only crops.

## Reproduce / local QA

From the project directory:

```sh
cd /Users/o0o02dn/Documents/adminAI/survey-coach
.venv/bin/python scripts/capture_screens.py
.venv/bin/python scripts/capture_screens.py --reduced-motion --output review/after/reduced-motion
.venv/bin/python scripts/capture_screens.py --serve --output review/after/manual-qa
```

The last command prints fresh **Home, Overview, Improve, pattern and Share URLs**
and keeps the isolated server running. Open those printed URLs, not URLs from an
old capture log: ports and survey IDs change each run. To see the grouped item,
open the pattern URL and choose **Quick wins** (the synthetic group is generated
from three questions missing multi-select instructions). For walkthrough, open
Overview and choose **Preview as a member**. For a populated Share view, choose
**Use this change** on the sample's first must-fix, then open Share. Stop with
Ctrl-C; the owned server is waited for and its temporary database is deleted.
No persistent review or user database is read or changed.

Options (`--help` lists these):

| Option | Meaning |
| --- | --- |
| `--output PATH` | `review/after/` or a child only; defaults to `review/after/` |
| `--timeout SECONDS` | Positive startup/job deadline; default 60 |
| `--reduced-motion` | Playwright reduced-motion emulation (capture mode) |
| `--serve` | Seed disposable DB, print URLs, wait for manual QA; no screenshots |

For manual reduced motion, use the browser's rendering/accessibility emulation;
`--reduced-motion` configures Playwright contexts, not a user's browser.
Existing output names inside the selected after directory are replaced on rerun.
Neither `review/*.png` nor `uglyhome.png` is an output target. No before images
were created or modified; the supplied originals remain untracked and untouched.

## Programmatically verified

- [x] Started a real uvicorn child on a pre-bound loopback socket; no rebind race.
- [x] Used a new empty temp DB, POSTed the offline sample, polled startup/jobs.
- [x] Sample's first must-fix selected at both viewports. Decisions reset between
  viewport scenarios, so desktop cannot leave mobile at the next issue.
- [x] Group is genuine engine output: a second synthetic snapshot with three
  distinct multi-choice questions missing instructions produces one criterion
  3.3 group. No review/plan/AI output overrides and no copied user's DB.
- [x] Share contains an actual UI-chosen synthetic change. The walkthrough is
  paused local reconstruction, not a vendor screenshot or real member response.
- [x] 12 normal + 12 reduced-motion files produced; hashes recorded. New script
  test decodes all 12 PNGs from another real reduced-motion run and checks sizes.
- [x] No horizontal document overflow at either viewport in all captured states.
- [x] Review chapter metrics report one `.btn-primary` and reachable About control;
  Home reports zero `.btn-primary` (its primary styling uses a different class).
  These are DOM observations, not an endorsement of visual action hierarchy.
- [x] No browser page errors or blocked external request attempts in either run;
  interception permits only this server origin and service workers are blocked.
- [x] Server cleanup tested on forced failure: owned process stopped and port
  unreachable. Startup exit/deadline, failed jobs, nonempty DB refusal and output
  path containment are covered. A real `--serve` subprocess SIGTERM test
  confirms clean exit and cleanup evidence; Ctrl-C uses the same cleanup path.
- [x] Full `.venv/bin/python -m pytest -m 'not live' -q`:
  **1051 passed, 1 deselected**, 194.50s, green before final fix commit.
  One existing Starlette/httpx warning. Exact focused command/results and initial
  red evidence are in `.superpowers/sdd/final-fix-report.md`.
- [x] Final normal and reduced-motion capture commands both exited 0 after
  `cddfe9b`; 24 refreshed PNGs and SHA-256 manifests. No page errors, external
  request attempts or horizontal overflow. Owned process/temp DB cleanup confirmed.
- [x] Cross-feature regressions: fingerprint/version Undo after reordered/removed
  findings, delayed writes/clipboard, authoritative Overview after save/restore,
  honest handled-vs-found headline and summary, exact multi-question labels.
- [x] Keyboard DOM evidence: 390x844 real Tab/Shift+Tab geometry/hit-testing in
  normal/reduced motion and enlarged text; single-card Undo restores panel/focus;
  grouped rows retain focus target; About Escape deterministic and route cleanup.
  These checks do not constitute human visual or usability acceptance.

## Board acceptance checklist — pending human visual QA

Every unchecked row remains unaccepted, even where related automated contracts
pass. No fabricated board sign-off.

| Visual / manual criterion | Related passing programmatic evidence | Acceptance |
| --- | --- | --- |
| Overview explains first priority within 5 seconds | Overview headline contracts; captured Overview | [ ] NOT inspected / timed |
| One primary action; default paragraphs at most two lines | Capture primary-class counts; overview responsive/action and signal-details tests | [ ] Visual hierarchy and all paragraph lengths NOT inspected |
| Same Q label in rail, phone, card, changes and summary | `test_labels.py`, phone-preview contracts and real grouped multi-question Improve/Share/download regression | [ ] Cross-surface visual comparison NOT inspected; legacy rail removed by redesign |
| No Next in rewrites; no blank quote gaps | `test_clean_copy.py`, copy-guard contracts | [ ] All rendered quotes NOT inspected |
| No rubric IDs in prose; absorbed issues only in Also affects | Improve absorbed/pin tests, plan exclusion tests | [ ] Visible prose NOT inspected |
| Community & fun suppresses emoji/one-word-caps findings | `test_survey_style.py` contracts | [ ] Manual style-switch scenario NOT performed |
| Default at most 3 + 6 actions; overflow grouped under More ideas | `test_plan.py` quick-win cap/grouping; overview contracts | [ ] Entire default-view action count NOT visually audited |
| Only test-response note inline; About reachable in every chapter | About keyboard-modal contracts, capture About presence | [ ] Disclaimer inventory NOT visually audited |
| Keyboard complete must-fix, Undo, finish via Share; visible unobscured focus | Cross-feature keyboard keep -> Undo -> continue -> Share, grouped focus and mobile hit-test contracts | [ ] End-to-end keyboard-only human run NOT performed |
| 390px no overflow; bottom bar does not cover content | All capture scrollWidths equal viewport; focused-control geometry/hit tests pass at 390x844 | [ ] Sticky-bar occlusion NOT visually inspected |
| Reduced motion: no animation, usable flow | Reduced-motion screenshots and existing computed-style/navigation contracts pass | [ ] Human flow / all motion NOT visually inspected |

## Safety and limitations

No live AI, external services, RedJade reads, real database, delegation, push or
worktree. The worked sample replays committed reviewed cache through OfflineOnly;
the synthetic grouped scenario uses `ai: false`. Existing API security is retained.
Loopback HTTP and the owned local browser/server are the only capture traffic.
Temporary DB and process are not retained; PNG evidence and logs are retained.
No numeric readiness claim or launch approval is introduced.
