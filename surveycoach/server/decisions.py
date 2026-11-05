"""The decision a researcher records on one item: use our change, mark it done in RedJade, or keep it.

Writing and reading share `clean_text`, so a hostile or hand-edited row can never smuggle control or
text-direction characters into a screen. HTML escaping stays the renderer's job (report.py escapes).
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from surveycoach.status import KEEP_REASONS

KEEP_NOTE_MAX = 200
_UNSAFE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def clean_text(value: str | None) -> str:
    """No control, zero-width or bidi-override characters; newlines and tabs stay."""
    return _UNSAFE.sub("", value or "").strip()


def read_decision(decision: dict) -> dict:
    """A stored decision as served: same keys, safe text, and a chip we recognise."""
    out = dict(decision)
    if isinstance(out.get("reason"), str):
        out["reason"] = clean_text(out["reason"])
    if out.get("keep_reason") is not None and out["keep_reason"] not in KEEP_REASONS:
        out["keep_reason"] = "other"
    return out


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["pick", "done", "original", "keep", "open"]
    picked_text: str | None = Field(default=None, max_length=50000)
    reason: str = Field(default="", max_length=10000)
    keep_reason: Literal[tuple(KEEP_REASONS)] | None = None
    manual_done: StrictBool = False
    client_id: str | None = Field(default=None, max_length=100)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def coherent_decision(self):
        self.reason = clean_text(self.reason)
        if self.keep_reason and self.action != "keep":
            raise ValueError("keep_reason only applies when the action is keep")
        if self.action == "keep" and not (self.reason or self.keep_reason):
            raise ValueError("Keeping an item requires a reason: choose a reason or write a short note")
        if self.keep_reason and len(self.reason) > KEEP_NOTE_MAX:
            raise ValueError(f"A note next to a reason is at most {KEEP_NOTE_MAX} characters")
        if self.action == "pick" and not (self.picked_text or "").strip():
            raise ValueError("Picking a rewrite requires picked_text")
        if self.action != "pick":
            self.picked_text = None
        return self
