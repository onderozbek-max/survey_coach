"""Finding-like extras (curated You check items, duration) for a saved version's detail.

One function feeds both the overview and the decisions API, so a fingerprint the user sees is a
fingerprint the API accepts, and neither can drift from the other.
"""
from __future__ import annotations

from surveycoach.items import extra_items
from surveycoach.labels import screen_labels
from surveycoach.rubric import Rubric, load_rubric
from surveycoach.snapshot import SurveySnapshot
from surveycoach.timing import estimate
from surveycoach.verdict import TYPE_PHRASES

DETECTED_LABELS = {"medium", "high"}


def display_type(data: dict) -> tuple[str, str]:
    """(survey type, source) whose length target applies: confirmed, else a trusted detection, else stored."""
    stored = data.get("survey_type") or (data.get("snapshot") or {}).get("survey_type", "non_ihut_product")
    if data.get("survey_type_chosen"):
        return stored, "confirmed"
    detection = data.get("survey_type_detection") or {}
    if detection.get("type") and detection.get("label") in DETECTED_LABELS:
        return detection["type"], "detected"
    return stored, "default"


def extras_for(data: dict, rubric: Rubric | None = None) -> list[dict]:
    """Extras for a detail dict that has a review; empty otherwise."""
    review = data.get("review")
    if not review or "snapshot" not in data:
        return []
    rubric = rubric or load_rubric()
    survey_type, _ = display_type(data)
    snapshot = SurveySnapshot.model_validate(dict(data["snapshot"], survey_type=survey_type))
    return extra_items(snapshot, screen_labels(snapshot), estimate(snapshot),
                       rubric.length_targets_minutes[survey_type][1], TYPE_PHRASES[survey_type],
                       survey_type, review.get("findings", []))
