"""Local Studio API. Start with create_app(db_path, provider=None)."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from surveycoach.server.repository import Repository
from surveycoach.server.security import LocalRequestGuard
from surveycoach.server.service import metadata, run_job, summary_packet
from surveycoach.snapshot import SurveySnapshot

SITE = Path(__file__).resolve().parents[2] / "site"


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot: SurveySnapshot
    ai: StrictBool = False

    @model_validator(mode="after")
    def bounded_snapshot(self):
        pages = self.snapshot.pages
        questions = self.snapshot.all_questions()
        if not pages or len({p.id for p in pages}) != len(pages):
            raise ValueError("Supply at least one page with unique page IDs")
        if len({q.id for q in questions}) != len(questions):
            raise ValueError("Question IDs must be unique across the survey")
        if len(self.snapshot.pages) > 500 or len(self.snapshot.all_questions()) > 2000:
            raise ValueError("Snapshot exceeds 500 pages or 2000 questions")
        if not self.snapshot.title.strip() or len(self.snapshot.title) > 1000:
            raise ValueError("Supply a title of 1 to 1000 characters")
        # Imported snapshots are data, not permission to inspect arbitrary local files.
        def reject_asset_paths(value):
            if isinstance(value, dict):
                if value.get("asset_path"):
                    raise ValueError("Local asset_path is not supported by snapshot import")
                for item in value.values():
                    reject_asset_paths(item)
            elif isinstance(value, list):
                for item in value:
                    reject_asset_paths(item)
        reject_asset_paths(self.snapshot.model_dump())
        return self


class TitleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["pick", "original", "keep", "open"]
    picked_text: str | None = Field(default=None, max_length=50000)
    reason: str = Field(default="", max_length=10000)
    manual_done: StrictBool = False
    client_id: str | None = Field(default=None, max_length=100)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def coherent_decision(self):
        if self.action == "keep" and not self.reason.strip():
            raise ValueError("Keeping a finding requires a reason")
        if self.action == "pick" and not (self.picked_text or "").strip():
            raise ValueError("Picking a rewrite requires picked_text")
        if self.action != "pick":
            self.picked_text = None
        return self


class StudioStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        # Static fallback must never turn unknown API paths into Studio HTML.
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, 404)
        if path in {"", "."}:
            path = "local.html"
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(db_path, provider=None) -> FastAPI:
    repository = Repository(db_path)

    @asynccontextmanager
    async def lifespan(app):
        yield
        repository.close()

    app = FastAPI(title="SurveyCoach Local Studio", lifespan=lifespan)
    app.state.repository = repository
    app.state.provider = provider
    app.add_middleware(LocalRequestGuard)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    @app.exception_handler(KeyError)
    async def missing(request: Request, error: KeyError):
        return JSONResponse({"detail": error.args[0]}, 404)

    @app.exception_handler(ValueError)
    async def invalid_value(request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, 422)

    @app.get("/environment.js")
    def environment():
        return Response("window.SURVEYCOACH_LOCAL = true;", media_type="text/javascript", headers={"Cache-Control": "no-store"})

    @app.get("/api/metadata")
    def get_metadata():
        return metadata()

    @app.get("/api/surveys")
    def list_surveys():
        return {"surveys": repository.list_surveys()}

    def submit(body, tasks, survey_id=None):
        result = repository.submit(body.snapshot, body.ai, survey_id)
        if result.pop("scheduled"):
            tasks.add_task(run_job, repository, result["job_id"], provider)
        return result

    @app.post("/api/samples/{name}", status_code=202)
    def sample(name: str, background_tasks: BackgroundTasks):
        if name != 'boxer-briefs':
            raise KeyError("Sample not found")
        snapshot = SurveySnapshot.model_validate_json((SITE.parent / "fixtures" / f"{name}.json").read_text())
        from surveycoach.server.example import run_example
        result = repository.submit(snapshot, ai=False)
        if result.pop('scheduled'):
            background_tasks.add_task(run_example, repository, result['job_id'])
        return result

    @app.post("/api/surveys", status_code=202)
    def import_snapshot(body: ImportRequest, background_tasks: BackgroundTasks):
        return submit(body, background_tasks)

    @app.post("/api/surveys/{survey_id}/recheck", status_code=202)
    def recheck(survey_id: str, body: ImportRequest, background_tasks: BackgroundTasks):
        return submit(body, background_tasks, survey_id)

    @app.get("/api/surveys/{survey_id}")
    def latest(survey_id: str):
        return repository.detail(survey_id)

    @app.patch("/api/surveys/{survey_id}")
    def rename(survey_id: str, body: TitleRequest):
        return repository.rename(survey_id, body.title)

    @app.get("/api/surveys/{survey_id}/versions/{version}/change-sheet")
    def changes(survey_id: str, version: int):
        detail = repository.detail(survey_id, version)
        return {"round": version, "changes": detail["change_sheet"],
                "round_changes": detail["round_changes"]}

    @app.get("/api/surveys/{survey_id}/versions/{version}")
    def version_detail(survey_id: str, version: int):
        return repository.detail(survey_id, version)

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        return repository.job(job_id)

    @app.get("/api/surveys/{survey_id}/versions/{version}/decisions")
    def decisions(survey_id: str, version: int):
        return {"decisions": repository.detail(survey_id, version)["decisions"]}

    @app.put("/api/surveys/{survey_id}/versions/{version}/decisions/{fingerprint}")
    def decide(survey_id: str, version: int, fingerprint: str, body: DecisionRequest):
        return repository.save_decision(survey_id, version, fingerprint, body.model_dump())

    @app.get("/api/surveys/{survey_id}/versions/{version}/summary", response_class=HTMLResponse)
    def summary(survey_id: str, version: int):
        html = summary_packet(repository.detail(survey_id, version))
        return HTMLResponse(html, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})

    from surveycoach.server.ask import router as ask_router
    app.include_router(ask_router(repository, provider))
    from surveycoach.server.reader import router as reader_router
    app.include_router(reader_router(repository, app))

    # Workflow assets can be added to site without changing the API/static boundary.
    if SITE.is_dir():
        app.mount("/", StudioStaticFiles(directory=SITE, html=True), name="studio")
    return app


__all__ = ["create_app"]
