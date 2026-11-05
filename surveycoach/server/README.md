# Local Studio backend

Run from the project root:

```sh
.venv/bin/python -m surveycoach.server --db /path/to/studio.sqlite3 --port 8000
```

Open `http://127.0.0.1:8000/local.html` for the private workflow. Root serves the synthetic Studio demo with a visible private-workspace link. The programmatic entry point is `surveycoach.server.create_app(db_path,
provider=None)`. Tests inject the existing `FakeProvider`.

## API contract

All bodies are JSON. Writes without an Origin header are allowed for local CLI
clients; browser writes must be same-origin. Only localhost/127.0.0.1/loopback
IPv6 Host headers are accepted. No CORS is enabled. Bodies are limited to 1 MiB
of actual received bytes. Imported local `asset_path` values are rejected.

- `GET /api/metadata`: `{dimensions, ai_batches, criteria}`, matching demo
  metadata without generating demo reviews or opening the AI cache.
- `GET /api/surveys`: `{surveys: [{id,title,version,content_hash,created_at}]}`;
  one latest-version entry per survey.
- `POST /api/surveys`: `{snapshot: SurveySnapshot, ai: false}` → HTTP 202 with
  `{id,survey_id,version,job_id,deduplicated}`. Creates a survey and immutable
  version 1, then queues its review. `ai` must be a JSON boolean. Link ingestion uses the separate reader route.
- `POST /api/surveys/{id}/recheck`: same request/response. Same engine
  `snapshot.review_hash` (including media, scale, requiredness and other review inputs) reuses an existing version (including historic
  versions), but creates a fresh review attempt. Changed hashes get the next
  integer version. Reusing an old version does not change which version is latest.
  Concurrent identical pending requests reuse their active job.
- `GET /api/jobs/{job_id}`: `{id,survey_id,version,ai_requested,status,error,
  created_at,finished_at}`. Status is `queued`, `running`, `completed`, or
  `failed`. Completion means the review ran, not that all AI checks succeeded;
  inspect `review.ai.failed` and `review.unchecked` too.
- `GET /api/surveys/{id}`: latest version detail.
- `GET /api/surveys/{id}/versions/{version}`: specific version detail.
  Both return `{id,survey_id,title,version,content_hash,snapshot,review,timeline,
  total_seconds,versions,decisions,job}`. `review`, `snapshot`, and timing fields
  follow the demo structure. Review is `null` until the first successful attempt.
  Every finding includes its stable engine `fingerprint` (criterion, page/question
  location, normalized evidence). `versions` is newest first. `job` is the latest
  attempt; a failed recheck does not erase the prior review.
- `GET /api/surveys/{id}/versions/{version}/decisions`: `{decisions: {...}}`,
  keyed by finding fingerprint.
- `PUT /api/surveys/{id}/versions/{version}/decisions/{fingerprint}`:
  `{action,picked_text?,reason?,keep_reason?,manual_done?}`. Actions: `pick` (requires nonblank
  picked_text from the saved finding's options), `done` (author says they fixed it in RedJade; unverified, never
  carried into the next version), `original` (older "mark done", counts as `done`), `keep` (requires a
  `keep_reason` chip: `intentional | owner_decided | not_applicable | other`, or a nonblank `reason`; a note next to
  a chip is at most 200 characters), `open`. Non-pick actions clear picked_text. Every save is also appended to
  the `decision_events` history. Details and example payloads: `.superpowers/sdd/impl-2a-decisions.md`. Returns the saved object plus `fingerprint` and
  server-derived `original`. `manual_done` defaults false. These decisions are
  version-scoped; they never mutate snapshots or automatically improve scores.
- `GET /api/surveys/{id}/versions/{version}/summary`: escaped HTML packet with
  readiness, unchecked checks, findings and decisions. Restrictive CSP; no active
  content. Manual completion is explicitly self-reported, not verified in RedJade.
  `?download=true` adds the Review summary card (name, safe link, verdict, sign-off, You check list).
- `PUT /api/surveys/{id}/reward` `{has_reward: bool|null, text?}`: the owner's reward answer (text only with `true`, at most 120 chars). 422 on bad input.
- `POST /api/surveys/{id}/versions/{version}/signoff` `{name, acknowledge_open?}`: append-only local sign-off, 201 with the sign-off state; 422 while items are open unless `acknowledge_open`.
- Detail also carries `reward`, `signoff`, `share` (Slack post, safe link, download route), `version_delta` (null on v1) and `presentation.journey`. Shapes and examples: `.superpowers/sdd/impl-3a-backend.md`.
- `create_app(..., developer=True)` / `SURVEYCOACH_DEVELOPER=1` / `--developer` tells the page to offer the raw snapshot import (`metadata.developer`, `window.SURVEYCOACH_DEVELOPER`); the import API itself is unchanged.

Unknown records return 404; invalid JSON/model fields return 422; blocked origins
403; unsupported write content type 415; oversized bodies 413; invalid Host 400.

## Additional MVP routes

- `POST /api/samples/{boxer-briefs|coffee-pods}` with `{}` queues a local-only synthetic example.
- `POST /api/reader/jobs` with `{url, approval: true, ai: false, survey_id?: string}` queues a bounded read. Production never accepts the local-fixture bypass. Reader jobs use `/api/jobs/{id}` polling. URL credentials, queries, fragments, non-RedJade and private targets are rejected. External progression/writes remain blocked; passive definition extraction may recover wording without advancing.
- Detail responses include `coverage` (null for manual imports). Branch/visual limitations prevent a ready claim. Captured images are available by saved position at `/api/surveys/{id}/versions/{version}/captures/{position}`; no caller-supplied paths.
- `POST /api/surveys/{id}/versions/{version}/ask` with `{fingerprint, question}` uses Wibey on the saved finding. Explicit user action sends survey wording. Model access stays on server.
- Decision bodies optionally carry `{client_id, revision}` so reordered requests from the same page cannot replace the latest pick. Distinct tabs remain last-arrival-wins; do not edit the same review concurrently across tabs.

## Privacy and lifecycle

Local-only review is the default even if a provider was injected. Only explicit
`ai: true` creates/uses the real Wibey provider (or injected provider). No demo
cache is read/written; the reader only fetches after an explicit approved-link request.
Local reviews explicitly retain `ai: null`, unchecked criteria and provisional
scores. Unchecked/failed checks cannot be labeled Ready by the API adapter.

SQLite stores immutable version snapshots and append-only successful review
attempts. Decisions are mutable and scoped to a version. Jobs execute in-process
using FastAPI background tasks, not a durable external queue. On restart,
interrupted jobs become failed and can be retried. Run **one server process per
SQLite file**; multi-worker deployments/job coordination are out of MVP scope.
This is a loopback-only local tool, not an authenticated multi-user service.
