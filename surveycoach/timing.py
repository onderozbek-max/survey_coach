"""Deterministic time and fatigue model. An estimate, labeled as one; constants are calibrated later."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from surveycoach.snapshot import Page, Question, SurveySnapshot

Fatigue = Literal["fresh", "fatigue_builds", "high"]
_ZONE_ORDER: list[Fatigue] = ["fresh", "fatigue_builds", "high"]


@dataclass(frozen=True)
class TimingConstants:
    seconds_per_word: float = 0.3          # mobile reading, about 200 words per minute
    page_overhead: float = 1.5             # tap Next, wait for the next page
    image_seconds: float = 3.0
    grid_row_seconds: float = 4.0
    fatigue_builds_after_seconds: float = 180.0
    high_fatigue_after_seconds: float = 420.0
    fatigue_builds_after_questions: int = 10
    high_fatigue_after_questions: int = 20
    # base seconds, then extra seconds per answer option
    kind_base: tuple[tuple[str, float, float], ...] = (
        ("single_choice", 3.0, 0.4), ("multi_choice", 5.0, 0.6), ("image_choice", 5.0, 0.0),
        ("dropdown", 5.0, 0.0), ("text_short", 15.0, 0.0), ("text_long", 40.0, 0.0),
        ("numeric", 6.0, 0.0), ("date", 8.0, 0.0), ("rating", 4.0, 0.0), ("slider", 6.0, 0.0),
        ("grid_single", 3.0, 0.0), ("grid_multi", 3.0, 0.0), ("ranking", 5.0, 3.0),
        ("best_worst", 8.0, 0.0), ("constant_sum", 20.0, 0.0), ("info", 0.0, 0.0), ("unknown", 5.0, 0.0),
    )

    def interaction(self, question: Question) -> float:
        base, per_option = next(((b, p) for k, b, p in self.kind_base if k == question.kind), (5.0, 0.0))
        return base + per_option * len(question.options) + self.grid_row_seconds * len(question.rows)


class PageTiming(BaseModel):
    page_id: str
    kind: str
    seconds: float
    cumulative_seconds: float
    fatigue: Fatigue


class Timing(BaseModel):
    total_seconds: float
    pages: list[PageTiming]
    path_uncertain: bool = False
    calibrated: bool = False
    basis: str = "Uncalibrated estimate of captured screens, not measured completion time."

    @property
    def minutes(self) -> float:
        return round(self.total_seconds / 60, 1)


def _words(text: str) -> int:
    return len(text.split())


def _question_seconds(question: Question, c: TimingConstants) -> float:
    media = len(question.media) + sum(1 for o in question.options if o.media)
    reading = _words(question.text) + _words(question.help_text) + sum(_words(o.label) for o in question.options)
    return reading * c.seconds_per_word + c.interaction(question) + media * c.image_seconds


def _unrepresented_text(text: str, represented: list[str], *, whole_lines: bool = False) -> str:
    """Subtract one exact captured copy per field, never semantic similarity.

    Whitespace is layout, but case and punctuation remain evidence. Longest
    fields go first so a short option cannot eat part of a question. Matching
    stays page-local and bounded to avoid removing labels inside other words.
    """
    remaining = text
    for field in sorted((t for t in represented if t.strip()), key=len, reverse=True):
        exact = r"\s+".join(re.escape(word) for word in field.split())
        # Option labels embedded in prose aren't evidence of a rendered option.
        pattern = (r"^[^\S\n]*" + exact + r"[^\S\n]*$" if whole_lines
                   else r"(?<!\w)" + exact + r"(?!\w)")
        remaining = re.sub(pattern, " ", remaining, count=1, flags=re.M)
    return remaining


def _page_seconds(page: Page, c: TimingConstants) -> float:
    represented = [field for q in page.questions for field in (q.text, q.help_text)]
    options = [o.label for q in page.questions for o in q.options]
    intro = _unrepresented_text(page.intro_text, represented)
    intro = _unrepresented_text(intro, options, whole_lines=True)
    raw = _unrepresented_text(page.text, [page.intro_text, *represented])
    raw = _unrepresented_text(raw, options, whole_lines=True)
    text_words = _words(intro) + _words(raw)
    questions = sum(_question_seconds(q, c) for q in page.questions)
    return text_words * c.seconds_per_word + questions + c.page_overhead


def _zone(seconds: float, questions: int, c: TimingConstants) -> Fatigue:
    by_time = 2 if seconds >= c.high_fatigue_after_seconds else 1 if seconds >= c.fatigue_builds_after_seconds else 0
    by_count = (2 if questions >= c.high_fatigue_after_questions
                else 1 if questions >= c.fatigue_builds_after_questions else 0)
    return _ZONE_ORDER[max(by_time, by_count)]


def estimate(snapshot: SurveySnapshot, constants: TimingConstants = TimingConstants()) -> Timing:
    pages: list[PageTiming] = []
    elapsed = 0.0
    answered = 0
    for page in snapshot.pages:
        seconds = _page_seconds(page, constants)
        elapsed += seconds
        answered += len(page.questions)
        pages.append(PageTiming(page_id=page.id, kind=page.kind, seconds=round(seconds, 1),
                                cumulative_seconds=round(elapsed, 1), fatigue=_zone(elapsed, answered, constants)))
    uncertain = any(q.conditional for q in snapshot.all_questions()) or any(
        p.kind == "screen_out" for p in snapshot.pages)
    return Timing(total_seconds=round(elapsed, 1), pages=pages, path_uncertain=uncertain,
                  basis=("Captured-screen total includes conditional or alternative pages; not a member route."
                         if uncertain else "Uncalibrated estimate of captured screens, not measured completion time."))


_PROMISE = re.compile(
    r"(?P<lo>\d+(?:\.\d+)?)\s*(?:(?:-|\u2013|to)\s*(?P<hi>\d+(?:\.\d+)?)\s*)?(?:minutes?|mins?)\b", re.I)


def parse_promised_minutes(text: str) -> float | None:
    """The time an intro promises. For a range, the upper end (the generous reading)."""
    match = _PROMISE.search(text or "")
    if not match:
        return None
    value = float(match.group("hi") or match.group("lo"))
    return int(value) if value == int(value) else value
