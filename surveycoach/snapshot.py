"""Reader-independent survey model. Every reader (crawler, API, fixture) produces this."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, Field

SurveyType = Literal["ihut", "non_ihut_product", "services_concept", "market_research", "community_pulse"]
PageKind = Literal["intro", "question", "info", "screen_out", "thank_you", "end"]
QuestionKind = Literal[
    "single_choice", "multi_choice", "dropdown", "text_short", "text_long", "numeric",
    "date", "rating", "slider", "grid_single", "grid_multi", "ranking", "best_worst",
    "image_choice", "constant_sum", "info", "unknown",
]


_NAV_TAIL = re.compile(r"(?:^|\n)[ \t]*(?:next|continue|back|start|begin|submit|finish|done)[ \t]*$", re.I)


def clean_copy(text: str) -> str:
    """Screen copy as a member reads it: no trailing navigation label, no runs of blank lines."""
    text = (text or "").replace("\xa0", " ").rstrip()
    while (trimmed := _NAV_TAIL.sub("", text).rstrip()) != text:
        text = trimmed
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class Media(BaseModel):
    kind: Literal["image", "video", "embed"] = "image"
    element_id: str = ""
    role: Literal["intro", "question", "option", "decoration"] = "question"
    alt: str | None = None
    natural_w: int | None = None
    natural_h: int | None = None
    rendered_w: int | None = None
    rendered_h: int | None = None
    bytes: int | None = None
    format: str | None = None
    has_alpha: bool = False
    object_fit: str | None = None   # cover/contain mean a deliberate crop, not a stretch
    loaded: bool = True
    asset_path: str | None = None


class Option(BaseModel):
    id: str
    label: str
    media: Media | None = None
    is_other_with_text: bool | None = None  # None: reader did not capture the behavior
    is_exclusive: bool | None = None


class Scale(BaseModel):
    points: int
    low_label: str | None = None
    high_label: str | None = None
    labels: list[str] = Field(default_factory=list)


class Question(BaseModel):
    id: str
    text: str
    kind: QuestionKind
    label: str | None = None
    help_text: str = ""
    required: bool | None = None  # None: the source never said (absence of a flag is not proof)
    options: list[Option] = Field(default_factory=list)
    rows: list[str] = Field(default_factory=list)
    scale: Scale | None = None
    media: list[Media] = Field(default_factory=list)
    conditional: bool = False
    options_below_fold: int = 0
    fits_one_screen: bool | None = None


class Page(BaseModel):
    id: str
    position: int
    kind: PageKind
    intro_text: str = ""
    questions: list[Question] = Field(default_factory=list)
    links_out: list[str] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    text: str = ""


class SurveySnapshot(BaseModel):
    title: str
    source_url: str = ""
    survey_type: SurveyType = "non_ihut_product"
    pages: list[Page]

    def page_role(self, page: Page) -> PageKind:
        """Infer conversation roles only at boundaries, from explicit wording, never from info alone."""
        if page.kind != "info" or any(q.kind != "info" for q in page.questions):
            return page.kind
        text = self.page_copy(page)
        if self.pages and page.id == self.pages[0].id:
            greeting = re.search(
                r"\bwelcome\b|\bthanks? for (?:helping|taking|joining|participating)\b", text, re.I
            )
            # A short topical invitation is a welcome even without the word "welcome".
            # Keep system screens and generic sharing/navigation instructions out.
            system_message = re.search(
                r"\b(?:loading|sign[ -]?in|log[ -]?in|password|authentication|verification|"
                r"validation|error|required question|answer (?:all|the) required)\b", text, re.I
            )
            invitation = len(text) <= 1200 and re.search(
                r"\b(?:(?:let us know|tell us)\s+(?:how|what|about|your)|"
                r"share\s+your\s+(?:thoughts|feedback|experience|opinions?|ideas?)\s+(?:on|about|with)|"
                r"your thoughts\s+(?:on|about))\s+(?!(?:next|continue|back|submit)\b)[a-z][\w'-]*",
                text, re.I,
            )
            purpose = re.search(
                r"\bwe(?:['’]re| are)\s+(?:exploring|cooking up|testing|learning about)\s+"
                r"(?!(?:how to|the next|this survey)\b)[a-z][\w'’-]*(?:\s+[a-z][\w'’-]*)+",
                text, re.I,
            )
            input_invitation = re.search(
                r"\bwe(?:['’]d| would)\s+(?:love|like)\s+your\s+(?:input|feedback|thoughts|opinions?)\b",
                text, re.I,
            )
            grounded_invitation = invitation or (len(text) <= 1200 and purpose and input_invitation)
            if not system_message and (greeting or grounded_invitation):
                return "intro"
        if self.pages and page.id == self.pages[-1].id and re.search(
            r"\bthank(?:s| you)\b", text, re.I
        ) and not re.search(r"\b(?:now|next|taste|read|continue|sample)\b", text, re.I):
            return "thank_you"
        return page.kind

    @staticmethod
    def page_copy(page: Page) -> str:
        parts = [clean_copy(t) for t in (
            page.intro_text, page.text, *[q.text for q in page.questions if q.kind == "info"]
        )]
        return " ".join(dict.fromkeys(p for p in parts if p))

    def all_questions(self) -> list[Question]:
        return [q for page in self.pages for q in page.questions]

    @property
    def intro_text(self) -> str:
        return next((self.page_copy(p) for p in self.pages if self.page_role(p) == "intro"), "")

    @property
    def review_hash(self) -> str:
        """Version identity includes all review inputs, not capture paths or source-link tokens."""
        canonical = self.model_dump(exclude={"source_url"})
        for page in canonical["pages"]:
            for media in page["media"]:
                media.pop("asset_path", None)
            for question in page["questions"]:
                question["options"].sort(key=lambda option: (option["id"], option["label"]))
                for media in question["media"]:
                    media.pop("asset_path", None)
                for option in question["options"]:
                    if option["media"]:
                        option["media"].pop("asset_path", None)
        return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()

    @property
    def content_hash(self) -> str:
        """Stable across option reordering, so randomized surveys do not create new versions."""
        canonical = [
            [page.kind, page.intro_text, page.text,
             [[q.text, q.kind, sorted(o.label for o in q.options), sorted(q.rows)] for q in page.questions]]
            for page in self.pages
        ]
        payload = json.dumps([self.title, canonical], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()
