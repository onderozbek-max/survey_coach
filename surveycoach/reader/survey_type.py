"""Deterministic survey-type suggestion. It never chooses: a type is only "chosen" when the user says so.

Only one pattern is recognised, on purpose: a concept described to the member, then asked about
buying or trying it. Everything else stays a plain product test. No AI, no fuzzy scoring.
"""
import re

from pydantic import BaseModel, Field, computed_field

from surveycoach.snapshot import Page, SurveySnapshot, SurveyType

DEFAULT_TYPE: SurveyType = "non_ihut_product"
SUBSTANTIAL_WORDS, CUED_WORDS = 40, 20

_CONCEPT_CUE = re.compile(
    r"\b(?:imagine|introducing|concept|our idea|new idea|an idea|new product|new service|coming soon|"
    r"we(?:'|\u2019)re (?:thinking|working|developing|exploring)|picture this|launching)\b", re.I)
_INTENT_QUESTION = re.compile(
    r"\bhow likely\b.*\b(?:buy|purchase|try|use|order|subscribe|sign up|add)\b|"
    r"\b(?:would|will) you (?:\w+ ){0,2}(?:buy|purchase|try|use|order|subscribe|sign up|add|consider)\b|"
    r"\b(?:purchase|buying|trial) intent\b|\binterested in (?:buy|purchas|try|using|subscrib)|"
    r"\bhow interested\b|\blikelihood (?:of|to) (?:buy|purchase|try)\b|\b(?:intend|plan) to (?:buy|purchase|try)\b",
    re.I | re.S)
_INTENT_OPTION = re.compile(r"\b(?:definitely|probably|might|would not|wouldn't|would) (?:\w+ )?(?:buy|purchase|try|use)\b", re.I)


class TypeDetection(BaseModel):
    type: SurveyType = DEFAULT_TYPE
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def label(self) -> str:
        return "high" if self.confidence >= 0.8 else "medium" if self.confidence >= 0.6 else "low"


def _description(page: Page, snapshot: SurveySnapshot) -> str:
    """Copy that describes something to the member: a question screen's stimulus or a middle info page."""
    if page.questions and any(q.kind != "info" for q in page.questions):
        return page.stimulus_text
    if snapshot.page_role(page) == "info":
        return snapshot.page_copy(page)
    return ""


def _is_concept(text: str) -> tuple[bool, bool]:
    """(is a concept description, has an explicit concept cue)."""
    words, cued = len(text.split()), bool(_CONCEPT_CUE.search(text))
    return words >= SUBSTANTIAL_WORDS or (words >= CUED_WORDS and cued), cued


def _asks_intent(page: Page) -> tuple[bool, bool]:
    """(any intent question, a purchase-intent answer scale)."""
    questions = [q for q in page.questions if q.kind != "info"]
    asks = any(_INTENT_QUESTION.search(q.text) for q in questions)
    scale = any(_INTENT_OPTION.search(o.label) for q in questions for o in q.options)
    return asks or scale, scale


def detect_survey_type(snapshot: SurveySnapshot) -> TypeDetection:
    pending, cells, cued, scaled = 0, 0, False, False
    for page in snapshot.pages:
        concept, cue = _is_concept(_description(page, snapshot))
        pending += concept
        cued |= concept and cue
        asks, scale = _asks_intent(page)
        if asks and pending:
            cells, pending, scaled = cells + 1, pending - 1, scaled or scale
    if not cells:
        return TypeDetection(confidence=0.4, reasons=[
            "No concept description followed by a purchase-interest question."])
    confidence = 0.65 + 0.1 * cued + 0.15 * (cells >= 2) + 0.05 * scaled
    reasons = [f"{cells} concept description{'s' if cells > 1 else ''} followed by a purchase-interest question."]
    if cued:
        reasons.append("The description uses concept wording (for example imagine, idea or introducing).")
    if scaled:
        reasons.append("Answers are a buy or try likelihood scale.")
    return TypeDetection(type="services_concept", confidence=round(min(confidence, 0.95), 2), reasons=reasons)


def apply_detection(snapshot: SurveySnapshot) -> TypeDetection:
    """Set the type on a freshly read snapshot, only when it still holds the default."""
    detection = detect_survey_type(snapshot)
    if snapshot.survey_type == DEFAULT_TYPE and detection.type != DEFAULT_TYPE:
        snapshot.survey_type = detection.type
    return detection
