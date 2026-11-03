"""What the AI judge must answer. Everything is validated, then grounded, before it can touch a score."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from surveycoach.findings import RewriteOption, Severity


class Verdict(BaseModel):
    criterion_id: str
    fraction: float = Field(ge=0.0, le=1.0)   # 1.0 means fully met


class AiFinding(BaseModel):
    criterion_id: str
    page_id: str | None = None
    question_id: str | None = None
    severity: Severity = "worth_improving"
    headline: str
    evidence: str                              # must be quoted verbatim from the survey
    explanation: str
    member_impact: str
    current_text: str | None = None
    suggested_text: str | None = None
    highlight: str | None = None
    options: list[RewriteOption] = Field(default_factory=list)


class BlockerCall(BaseModel):
    blocker_id: str
    triggered: bool


class BatchOutput(BaseModel):
    verdicts: list[Verdict] = Field(default_factory=list)
    blockers: list[BlockerCall] = Field(default_factory=list)
    findings: list[AiFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_decisions(self):
        for items, field in ((self.verdicts, "criterion_id"), (self.blockers, "blocker_id")):
            ids = [getattr(item, field) for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {field} in judge output")
        return self


class Answer(BaseModel):
    text: str
