# SurveyCoach

Reviews MMC (Member's Mark Community) surveys against the approved rubric, mobile first.
Design: `docs/superpowers/specs/`. Rubric: `docs/rubric/mmc-survey-rubric-v2.md`.
Build plan: `docs/superpowers/plans/2026-11-02-roadmap.md`.

## Live demo

https://onderozbek-max.github.io/survey_coach/

The front door is a short landing page (what SurveyCoach is, how it works, an interactive example). Its button opens
`sample.html`: a saved review of a made-up sample survey, shown with a phone preview, the verdict, the fix flow, the
journey strip and the Sign off step. A banner on the review says it is a sample. In the source tree the landing page is
`site/welcome.html` and the review is `site/index.html`; `scripts/build_pages.py` swaps them for the published bundle. It reads no real surveys
and changes nothing in RedJade. Open it locally with `open site/index.html` (or `cd site && python3 -m http.server`).

GitHub Pages can only serve static files, so it cannot check real surveys. Real reviews need the Python server
(see "Test the private local workspace"), which has no sign-in and must stay on a loopback address. The Pages build
(`python scripts/build_pages.py`) turns the server-only pages (`local.html`, `review.html`) into redirects back to
the sample. To point the sample's banner at a team tool once one exists, set `window.SURVEYCOACH_TEAM_URL` (plain
https only) in `site/environment.js` and re-publish; until then the banner says to ask the owner.

The review data in `site/data.js` is produced by the Python engine, never hand-edited:
`.venv/bin/python -m surveycoach.demo_export` regenerates it, and a test fails if it goes stale.
The page uses the approved custom dark Studio design in plain HTML/CSS/JS. No proprietary Living Design code is bundled. Real surveys belong in the private local workspace, never the public demo.

## Status

Review engine and AI judge are implemented. The public demo replays reviewed synthetic AI cache data; normal exports make no network calls. A local MVP candidate now adds saved surveys/versions/decisions, real review jobs, one contextual issue coach, an effort-by-screen journey, side-by-side wording previews, saved round comparisons, HTML sign-off packets, and a bounded link reader. The legacy Ask API remains compatible but is no longer a competing workspace interface.

**Not yet production validated:** real RedJade compatibility/vendor approval, full visual/branch coverage, and director-graded accuracy calibration. Do not treat this build as automatic launch approval. Hosted multi-user authentication is not implemented; the server must remain loopback-only.

## Test the private local workspace

After installing dependencies below, install Chromium with `.venv/bin/python -m playwright install chromium`, then run:

```bash
.venv/bin/python -m surveycoach.server --db "$HOME/Library/Application Support/SurveyCoach/mvp.sqlite3" --port 8765
open http://127.0.0.1:8765/local.html
```

Choose **Try the worked example** to explore a worked example without external access. Use an approved clean HTTPS RedJade test link for your own survey. **Check survey / Check again** includes approved AI review; the wording/privacy and reader-behaviour notices appear at the action. JSON import remains a developer/test interface, not the primary researcher path.

Reader behaviour depends on `SURVEYCOACH_PARTICIPANT_MODE`: unset blocks answer writes; `1` permits synthetic answers, advancement and Submit/Finish on owner-approved test links. Both may create participant records. The UI fetches the actual configured mode before reading. Never use member invitation links; exclude synthetic test responses from research results.

Choices and keep reasons persist on this computer. Historical snapshots and stored reviews stay immutable: current code checks are projected on read. Historical AI concerns remain visible, but old reviews without per-criterion evidence receive no invented AI passing credit; newly completed reviews retain that evidence. **Use this** records a choice and copies wording, but is not proof of a fix in RedJade. **Check again** compares rounds conservatively: carried decisions remain acknowledgements, and no-longer-flagged issues are not automatically certified fixed. The sign-off report contains survey wording: share only through approved internal channels.

### Managed-network reader setup

A browser working through macOS PAC does **not** mean the local Python reader can
resolve the same host. The reader does not execute/download PAC JavaScript, inspect
macOS proxy settings, or use `HTTP_PROXY`, `HTTPS_PROXY` or `ALL_PROXY`. An enabled
managed PAC URL alone does not establish which route its rules select for RedJade,
so there is no automatic PAC-based proxy selection.

For an approved clean test link on **app.redjade.net only**, launch a new local
server process from this repository with the existing approved corporate proxy:

```bash
SURVEYCOACH_CORPORATE_PROXY=http://proxy-intlho.wal-mart.com:8080 \
  .venv/bin/python -m surveycoach.server \
  --db "$HOME/Library/Application Support/SurveyCoach/mvp.sqlite3" --port 8765
```

Stop an existing local server normally before starting the replacement. This inline
variable affects only that new process: it does not change shell profiles, macOS
settings, or an already running server. Do not add participant mode just to diagnose
connectivity. Open `http://127.0.0.1:8765/local.html` afterward. Without that variable,
the normal startup command above keeps the direct route. Other RedJade hosts require
direct public DNS; do not broaden the approved proxy host restriction.

Use the approved corporate network/VPN. Only the exact proxy value above is accepted
(no credentials or alternate proxies); the proxy resolves the fixed upstream host.
Target HTTPS certificate/SNI verification, URL/origin allowlists, write restrictions,
redirect blocking and transport bounds remain enforced. Direct DNS must resolve
exclusively to public addresses. A private/mixed/empty DNS response is a **policy
block**, not a reason to bypass address checks with a proxy.

Reader errors distinguish local DNS lookup failure, rejected proxy configuration,
blocked URL/address policy, and connection failure/timeout. DNS failure is not proof
you are disconnected from VPN. If the approved setup still fails, ask corporate
network support to check the route; do not disable TLS verification or use arbitrary
proxy/tunnel fallbacks. Startup configuration is not proof of connectivity: this
change was verified with mocked transports and DNS-only diagnostics, not a live
survey or participant session.

### Reader boundaries

The reader can passively extract a known questionnaire definition from already permitted same-origin GET responses, preserving question and answer wording without submitting answers. Otherwise it captures visible screens subject to the configured participant mode. Write-blocking mode prevents external answer progression; participant mode may answer, advance and finish an approved test response. Definition wording is not proof of image, layout, or path correctness. Coverage and stop reasons remain visible in the review/packet. Unsupported URLs, authentication, widget types and missing payloads fail closed or remain explicitly partial.

Read `surveycoach/reader/README.md` and `surveycoach/server/README.md` for technical contracts. Browser captures use private temporary directories outside the repository; retention/cleanup is operator-managed. Do not put member responses/PII in this tool.

## Try it

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]" \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com

.venv/bin/python -m pytest -q
.venv/bin/python -m surveycoach review fixtures/boxer-briefs.json   # flawed sample; local checks only
.venv/bin/python -m surveycoach review fixtures/coffee-pods.json    # clean sample
```

## How it works

`SurveySnapshot` (reader-independent) goes through pure checks registered by rubric ID
(`surveycoach/checks/`). Each check returns a score fraction plus plain-English findings.
`surveycoach/data/rubric-v2.yaml` is the only place points live; scoring is a weighted sum
over active criteria totaling exactly 100. Only assessed, applicable criteria earn checked credit; unchecked and not-applicable criteria are reported separately, never strengths. A test keeps the YAML in sync with the approved markdown rubric.

Honest by design: criteria that need the AI judge are reported as unchecked, the score is
flagged provisional, and a survey cannot be called Ready to launch while AI-judged blockers
(B1, B2, B6) are still pending.

Adding a check: write a function in `surveycoach/checks/<module>.py`, decorate it with
`@check("<rubric id>")`, and add tests. `tests/test_review.py` lists the checks not built yet.
