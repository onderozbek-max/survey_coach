# SurveyCoach

Reviews MMC (Member's Mark Community) surveys against the approved rubric, mobile first.
Design: `docs/superpowers/specs/`. Rubric: `docs/rubric/mmc-survey-rubric-v2.md`.
Build plan: `docs/superpowers/plans/2026-11-02-roadmap.md`.

## Live demo

https://onderozbek-max.github.io/adminai/

A static page with saved reviews of two made-up sample surveys, shown with a phone preview.
It reads no real surveys and changes nothing in RedJade. Open it locally with
`open site/index.html` (or `cd site && python3 -m http.server`).

The review data in `site/data.js` is produced by the Python engine, never hand-edited:
`.venv/bin/python -m surveycoach.demo_export` regenerates it, and a test fails if it goes stale.
The page uses the approved custom dark Studio design in plain HTML/CSS/JS. No proprietary Living Design code is bundled. Real surveys belong in the private local workspace, never the public demo.

## Status

Review engine and AI judge are implemented. The public demo replays reviewed synthetic AI cache data; normal exports make no network calls. A local MVP candidate now adds saved surveys/versions/decisions, real review jobs, grouped fixes, re-check comparisons, Ask the Coach, HTML review packets, and a bounded link reader.

**Not yet production validated:** real RedJade compatibility/vendor approval, full visual/branch coverage, and director-graded accuracy calibration. Do not treat this build as automatic launch approval. Hosted multi-user authentication is not implemented; the server must remain loopback-only.

## Test the private local workspace

After installing dependencies below, install Chromium with `.venv/bin/python -m playwright install chromium`, then run:

```bash
.venv/bin/python -m surveycoach.server --db "$HOME/Library/Application Support/SurveyCoach/mvp.sqlite3" --port 8765
open http://127.0.0.1:8765/local.html
```

Choose **Try the saved-work flow with a sample** to test without technical files or external access. It runs local checks and explicitly leaves AI unchecked. Alternatively import a SurveyCoach JSON snapshot (developer-assisted), or use an approved clean HTTPS RedJade test link. Normal Start review / Check again includes AI through the fixed Wibey model, with a visible notice before submission; never a fake provider in normal usage. The one-click sample remains local-only. Start review proceeds directly without a checkbox or confirmation dialog. The inline test-link notice remains; automated response writes and final submission are still blocked.

Choices, keep reasons, and manually marked changes persist on this computer. Copying does not mark a fix resolved. Import an updated snapshot or reread the approved link to compare versions. The summary packet contains survey wording: save/share it only through approved internal channels.

### Reader boundaries

The reader can passively extract a known questionnaire definition from already permitted same-origin GET responses, preserving question and answer wording without submitting answers. Otherwise it captures the initial visible page; external progression is disabled because a button called Next can submit the final response. Definition wording is not proof of image, layout, or path correctness. Coverage and stop reasons remain visible in the review/packet. Unsupported URLs, authentication, widget types and missing payloads fail closed or remain explicitly partial.

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
over active criteria totaling exactly 100. A test keeps the YAML in sync with the approved
markdown rubric.

Honest by design: criteria that need the AI judge are reported as unchecked, the score is
flagged provisional, and a survey cannot be called Ready to launch while AI-judged blockers
(B1, B2, B6) are still pending.

Adding a check: write a function in `surveycoach/checks/<module>.py`, decorate it with
`@check("<rubric id>")`, and add tests. `tests/test_review.py` lists the checks not built yet.
