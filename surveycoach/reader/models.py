"""Coverage lives beside, not inside, the existing reader-independent snapshot."""
from pathlib import Path

from pydantic import BaseModel, Field

from surveycoach.snapshot import SurveySnapshot


class Coverage(BaseModel):
    pages_captured: int = 0
    definition_available: bool = False
    definition_wording_complete: bool = False
    pages_defined: int = 0
    questions_defined: int = 0
    definition_conditions: dict = Field(default_factory=dict)
    rendered_definition_pages: list[str] = Field(default_factory=list)
    visual_media_verified: bool = False
    paths_verified: bool = False
    stop_reason: str = "not_started"
    full_branching_coverage: bool = False
    blocked_requests: int = 0
    test_session_started: bool = False
    warnings: list[str] = Field(default_factory=lambda: [
        "Partial read: only one deterministic path; branching coverage is never complete.",
        "No definition/API extraction; hidden questions, loops and unvisited branches are not inferred.",
        "Screenshots capture the phone viewport only; no stitched inner-scroll or interactive replica.",
        "Only visible img elements are measured; original image bytes and CSS/background media are not analyzed.",
    ])


class Capture(BaseModel):
    page_id: str
    viewport_png: Path
    observation_json: Path


class ReadResult(BaseModel):
    snapshot: SurveySnapshot
    coverage: Coverage
    capture_dir: Path
    captures: list[Capture] = Field(default_factory=list)
    # Full passive source retained so unsupported fields/conditions are not discarded.
    definition: dict | None = None
