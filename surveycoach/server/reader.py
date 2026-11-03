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
            captured = reader(body.url, approval=True,
                              test_session=os.environ.get("SURVEYCOACH_ALLOW_TEST_SESSION") == "1")
            if not captured.snapshot.pages or not captured.snapshot.title.strip():
                update(job_id, "failed", body.survey_id,
                       error="No reviewable pages captured. The link may need authentication or an unsupported reader.")
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
        except UnsafeSurveyURL as error:
            # Policy errors are deliberately URL-free; never echo an arbitrary exception.
            if "resolved" in str(error):
                message = "Could not connect to the survey website. Check your network/VPN and make sure the preview link opens in your browser, then try again."
            else:
                message = "This preview link could not be opened safely. Use an approved RedJade test link; do not use a member invitation link."
            update(job_id, "failed", body.survey_id, error=message)
        except Exception as error:
            reference = job_id[:8]
            logger.error("Reader failure reference=%s type=%s", reference, type(error).__name__)
            update(job_id, "failed", body.survey_id,
                   error=f"The survey could not be read because of an app error. Please report reference {reference}. No completed review was created.")

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
