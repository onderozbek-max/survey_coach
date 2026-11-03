"""Server-only follow-up questions constrained to findings already in a saved review."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from surveycoach.findings import Finding
from surveycoach.judge.ask import ask_coach
from surveycoach.llm import WibeyProvider, LlmError
from surveycoach.snapshot import SurveySnapshot


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Ask a question first")
        return value


def router(repository, provider=None):
    routes = APIRouter()

    @routes.post("/api/surveys/{survey_id}/versions/{version}/ask")
    def ask(survey_id: str, version: int, body: AskRequest):
        detail = repository.detail(survey_id, version)
        finding = next((f for f in (detail["review"] or {}).get("findings", [])
                        if f["fingerprint"] == body.fingerprint), None)
        if finding is None:
            raise HTTPException(404, "Finding not found in this review")
        try:
            selected = provider if provider is not None else WibeyProvider()
            answer = ask_coach(selected, SurveySnapshot.model_validate(detail["snapshot"]),
                               Finding.model_validate(finding), body.question)
        except LlmError:
            raise HTTPException(503, "The coach is unavailable. Your saved review is unchanged.") from None
        return {"answer": answer, "warning": "AI-written. Check before use. SurveyCoach does not change RedJade."}

    return routes
