"""Findings and check results. Plain English, member-first."""
from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field, model_serializer

Severity = Literal["must_fix", "worth_improving"]


class RewriteOption(BaseModel):
    """One way to fix the wording, for example Neutral, Shorter, or Friendlier."""

    label: str
    text: str


class Finding(BaseModel):
    """One problem, worded so a researcher can act on it.

    `headline` names the problem (never the rubric criterion). `current_text` and `suggested_text`
    are a before/after the researcher can paste into RedJade; they are only set when a check can
    really produce one. `highlight` is the exact word or phrase in the survey that is at fault.
    """

    criterion_id: str
    severity: Severity
    headline: str
    evidence: str
    explanation: str
    member_impact: str
    page_id: str | None = None
    question_id: str | None = None
    element_id: str | None = None
    current_text: str | None = None
    suggested_text: str | None = None
    highlight: str | None = None
    options: list[RewriteOption] = Field(default_factory=list)   # AI findings offer several rewrites to choose from
    structural: bool = False   # the fix spans more than one text element (for example answer choices): copy it, do not preview it
    edit_kind: Literal['rewrite', 'add_answer'] = 'rewrite'
    source: Literal["auto", "ai"] = "auto"

    @property
    def root_identity(self) -> tuple[str, str, str]:
        """Conservative duplicate key: same location, evidence and named root problem."""
        normalize = lambda text: re.sub(r"\s+", " ", text).strip().lower()
        return (self.question_id or self.page_id or "survey", normalize(self.evidence), normalize(self.headline))

    @property
    def fingerprint(self) -> str:
        """Identifies the same issue across re-checks: rubric ID, location, normalized evidence."""
        evidence = re.sub(r"\s+", " ", self.evidence).strip().lower()
        raw = f"{self.criterion_id}|{self.page_id}|{self.question_id}|{evidence}"
        return hashlib.sha1(raw.encode()).hexdigest()[:12]


class CheckResult(BaseModel):
    """One rubric criterion or blocker. `fraction` is 0..1 of the rubric points earned.

    None means the check could not judge (it stays unchecked). Blockers use findings only.
    `applies=False` means there was nothing to judge (for example, no images): no earned points,
    no provisional flag, and never listed as a strength. `assessed=False` marks a partial
    blocker check that cannot positively clear the wider risk.
    """

    criterion_id: str
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    applies: bool = True
    assessed: bool = True
    findings: list[Finding] = Field(default_factory=list)
    note: str | None = None   # why a check could not judge (unknown evidence); never a finding, never advice

    @model_serializer(mode="wrap")
    def _omit_empty_note(self, handler):
        """Most results have no note: keep their saved and served shape exactly as it was."""
        data = handler(self)
        if data.get("note") is None:
            data.pop("note", None)
        return data
