"""Bounded link-read jobs. Production never enables the controlled-local-fixture bypass."""
import json
import logging
import os
from uuid import uuid4
from pathlib import Path
from fastapi.responses import FileResponse

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from surveycoach.reader import read_survey
from surveycoach.reader.policy import UnsafeSurveyURL, validate_url
from surveycoach.reader.proxy import APPROVED_PROXY, ReaderProxyConfigurationError
from surveycoach.reader.transport import ReaderDNSFailure, ReaderNetworkFailure

logger = logging.getLogger(__name__)
from surveycoach.server.service import run_job


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=3000)
    approval: StrictBool = False
    ai: StrictBool = False
    survey_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def approved_url(self):
        validate_url(self.url, approval=self.approval)
        return self


def router(repository, app):
    routes = APIRouter()
    with repository.transaction() as db:
        db.execute("CREATE TABLE IF NOT EXISTS captures (survey_id TEXT, version INTEGER, position INTEGER, page_id TEXT, path TEXT, PRIMARY KEY(survey_id,version,position))")
        db.execute("CREATE TABLE IF NOT EXISTS reader_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, "
                   "survey_id TEXT, version INTEGER, error TEXT)")
        columns = {row[1] for row in db.execute('PRAGMA table_info(reader_jobs)')}
        for column, definition in [('stage','TEXT'), ('pages_captured','INTEGER DEFAULT 0'), ('deduplicated','INTEGER DEFAULT 0')]:
            if column not in columns:
                db.execute(f'ALTER TABLE reader_jobs ADD COLUMN {column} {definition}')
        db.execute('CREATE TABLE IF NOT EXISTS reader_previews (job_id TEXT, position INTEGER, path TEXT, PRIMARY KEY(job_id,position))')
        db.execute("UPDATE reader_jobs SET status='failed',error='Server stopped during read; retry safely.' "
                   "WHERE status IN ('queued','running')")

    def update(job_id, status, survey_id=None, version=None, error=None):
        with repository.transaction() as db:
            db.execute("UPDATE reader_jobs SET status=?,survey_id=?,version=?,error=? WHERE id=?",
                       (status, survey_id, version, error, job_id))

    def perform(job_id, body):
        update(job_id, "running", body.survey_id)
        try:
            reader = getattr(app.state, "reader", read_survey)
            options = {"approval": True,
                       "participate": os.environ.get("SURVEYCOACH_PARTICIPANT_MODE") == "1"}
            if options["participate"] and reader.__module__ == "surveycoach.reader.session":
                from surveycoach.llm import WibeyProvider
                provider = app.state.provider if app.state.provider is not None else WibeyProvider()
                from surveycoach.llm.planner import WibeyPlanner
                from surveycoach.llm.base import LlmUnavailable
                try:
                    options["planner"] = (WibeyPlanner(provider.binary)
                                          if isinstance(provider, WibeyProvider) else provider)
                except LlmUnavailable:
                    options["planner"] = None
                options["rules_path"] = Path(os.environ.get("SURVEYCOACH_RULES_PATH",
                    str(Path.home() / "Library/Application Support/SurveyCoach/reader-rules.sqlite3")))
            if reader is read_survey:
                def on_capture(position, model, png):
                    with repository.transaction() as db:
                        db.execute('INSERT OR REPLACE INTO reader_previews VALUES (?,?,?)', (job_id,position,str(png)))
                        db.execute("UPDATE reader_jobs SET stage='reading',pages_captured=? WHERE id=?", (position+1,job_id))
                options['on_capture'] = on_capture
            captured = reader(body.url, **options)
            for kind in ("timeout", "connection"):
                if f"Reader initial connection failed: {kind}." in captured.coverage.warnings:
                    raise ReaderNetworkFailure(kind)
            with repository.transaction() as db:
                db.execute("UPDATE reader_jobs SET stage='checking',pages_captured=? WHERE id=?", (len(captured.snapshot.pages),job_id))
            if not captured.snapshot.pages or not captured.snapshot.title.strip():
                warnings = captured.coverage.warnings
                if 'Reader initial document unavailable: redirect_blocked.' in warnings:
                    message = ('The survey entry page returned a redirect. The reader does not follow redirects, '
                               'so it captured no questions. Ask the survey owner for a direct researcher preview '
                               'or export; no redirect destination was opened.')
                elif any(f'Reader initial document unavailable: http_{code}.' in warnings for code in (401, 403)):
                    code = 401 if 'Reader initial document unavailable: http_401.' in warnings else 403
                    message = (f'The survey entry page returned HTTP {code}. The reader has a fresh session, '
                               'not your browser sign-in. A vendor or network access rule may also be involved. '
                               'Use an owner-provided researcher preview or export; do not share browser credentials.')
                else:
                    message = ('The reader returned empty or untitled content before any reviewable questions '
                               'were available. This does not establish whether sign-in, a blocked startup request '
                               'or unsupported rendering caused it. No completed review was created.')
                logger.warning('Reader empty result reference=%s stop=%s pages=%d blocked=%d',
                               job_id[:8], captured.coverage.stop_reason,
                               len(captured.snapshot.pages), captured.coverage.blocked_requests)
                update(job_id, "failed", body.survey_id, error=message)
                return
            if not captured.snapshot.all_questions() and any(
                "participant sign-in" in warning for warning in captured.coverage.warnings
            ):
                update(job_id, "failed", body.survey_id,
                       error="Connected to RedJade, but this link requires starting a participant session before questions are available. SurveyCoach has not created that session. Use a researcher preview/export, or arrange a test-participant session with the survey owner.")
                return
            if not captured.snapshot.all_questions() and all(
                page.text.strip().lower().rstrip(". …") in {"", "loading", "please wait"}
                for page in captured.snapshot.pages
            ):
                update(job_id, "failed", body.survey_id,
                       error="Connected to RedJade, but SurveyCoach could not load the survey questions. This survey's startup requests are not yet supported. No review was created.")
                return
            created = repository.submit(captured.snapshot, body.ai, body.survey_id)
            coverage = captured.coverage.model_dump(mode="json")
            with repository.transaction() as db:
                db.execute('UPDATE reader_jobs SET deduplicated=? WHERE id=?', (int(created['deduplicated']),job_id))
            with repository.transaction() as db:
                db.execute("INSERT OR REPLACE INTO coverage(survey_id,version,data) VALUES (?,?,?)",
                           (created["id"], created["version"], json.dumps(coverage)))
            with repository.transaction() as db:
                for position, capture in enumerate(captured.captures):
                    path = capture.viewport_png.resolve()
                    if not path.is_relative_to(captured.capture_dir.resolve()):
                        raise ValueError("Capture outside reader directory")
                    db.execute("INSERT OR REPLACE INTO captures VALUES (?,?,?,?,?)",
                               (created["id"], created["version"], position, capture.page_id, str(path)))
            if created["scheduled"]:
                run_job(repository, created["job_id"], app.state.provider)
            checked = repository.job(created["job_id"])
            update(job_id, checked["status"], created["id"], created["version"], checked.get("error"))
        except ReaderDNSFailure:
            update(job_id, "failed", body.survey_id, error=(
                "The local reader's DNS lookup failed before connecting. A browser can use macOS PAC "
                "while this Python reader uses direct DNS; browser connectivity does not verify the reader route. "
                "For app.redjade.net only, restart the local server with "
                f"SURVEYCOACH_CORPORATE_PROXY={APPROVED_PROXY} as shown in README → Managed-network reader setup. "
                "Use your approved corporate network/VPN; other hosts require direct public DNS. "
                "No completed review was created."))
        except ReaderProxyConfigurationError:
            update(job_id, "failed", body.survey_id, error=(
                "The reader proxy configuration was rejected. Only "
                f"SURVEYCOACH_CORPORATE_PROXY={APPROVED_PROXY} is supported, for app.redjade.net only. "
                "See README → Managed-network reader setup. No completed review was created."))
        except (ReaderNetworkFailure, TimeoutError) as error:
            timed_out = isinstance(error, TimeoutError) or error.kind == "timeout"
            reason = "timed out" if timed_out else "connection failed"
            update(job_id, "failed", body.survey_id, error=(
                f"The local reader {reason}. Check the approved corporate network/VPN and reader proxy "
                "setup in README → Managed-network reader setup, then retry an approved test link. "
                "This is not a survey-link safety rejection. No completed review was created."))
        except UnsafeSurveyURL:
            # Never infer DNS failure from policy exception text or echo arbitrary details.
            update(job_id, "failed", body.survey_id, error=(
                "This preview link could not be opened safely: the URL or resolved addresses were blocked "
                "by reader policy. Use an approved RedJade test link; do not use a member invitation link. "
                "Do not bypass address checks with a proxy. No completed review was created."))
        except Exception as error:
            reference = job_id[:8]
            logger.error("Reader failure reference=%s type=%s", reference, type(error).__name__)
            update(job_id, "failed", body.survey_id,
                   error=f"The survey could not be read because of an app error. Please report reference {reference}. No completed review was created.")

    @routes.get('/api/reader/mode')
    def mode():
        participates = os.environ.get('SURVEYCOACH_PARTICIPANT_MODE') == '1'
        notice = ('This reader answers, advances and may submit synthetic test responses. Exclude them from results.'
                  if participates else 'This reader blocks answer writes. Opening a test link may still create a partial test participant.')
        return {'participates': participates, 'notice':notice}

    @routes.get('/api/reader/jobs/{job_id}/preview/{position}')
    def progress_capture(job_id: str, position: int):
        with repository.transaction() as db:
            row = db.execute('SELECT path FROM reader_previews WHERE job_id=? AND position=?', (job_id,position)).fetchone()
        if not row or not Path(row['path']).is_file():
            raise HTTPException(404,'Captured screen unavailable')
        return FileResponse(row['path'],media_type='image/png',headers={'Cache-Control':'no-store'})

    @routes.get("/api/surveys/{survey_id}/versions/{version}/captures/{position}")
    def capture(survey_id: str, version: int, position: int):
        with repository.transaction() as db:
            row = db.execute("SELECT path FROM captures WHERE survey_id=? AND version=? AND position=?", (survey_id, version, position)).fetchone()
        if not row or not Path(row["path"]).is_file():
            raise HTTPException(404, "Capture unavailable")
        return FileResponse(row["path"], media_type="image/png", headers={"Cache-Control": "no-store"})

    @routes.post("/api/reader/jobs", status_code=202)
    def read(body: ReadRequest, background_tasks: BackgroundTasks):
        if body.survey_id:
            repository.detail(body.survey_id)
        with repository.transaction() as db:
            if db.execute("SELECT 1 FROM reader_jobs WHERE status IN ('queued','running')").fetchone():
                raise HTTPException(409, "A survey read is already running. Wait for it to finish.")
            job_id = uuid4().hex
            db.execute("INSERT INTO reader_jobs(id,status,survey_id) VALUES (?,'queued',?)", (job_id, body.survey_id))
        background_tasks.add_task(perform, job_id, body)
        return {"job_id": job_id}

    return routes
