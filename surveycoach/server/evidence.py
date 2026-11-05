"""What a finished read means, and which evidence bundle a version keeps. Pure rules plus one SQL unit.

A read is *reviewable* when it captured questions, *limited* when it only captured legitimate
welcome/closing/screen-out screens, and an *error* when what it captured looks like an error
screen or nothing recognisable after the reader failed. Errors never become review jobs.
"""
import json
import re
from typing import Literal

from surveycoach.reader.models import Coverage, ReadResult
from surveycoach.snapshot import SurveySnapshot

ReadOutcome = Literal["reviewable", "limited", "error"]
EvidenceAction = Literal["new", "replaced", "retained"]

ERROR_SCREEN_MESSAGE = (
    "Connected to RedJade, but the read ended on an error screen, not survey content. SurveyCoach could "
    "not read any questions. Check that the link works in your browser, then retry. No review was created.")

_ERROR_SCREEN = re.compile(
    r"\b(?:service (?:is )?unavailable|something went wrong|try again|(?:please )?retry later|"
    r"temporarily unavailable|internal server error|bad gateway|gateway time-?out|page not found|"
    r"access denied|session (?:has )?expired|an? (?:unexpected )?error (?:has )?occurred|unexpected error|"
    r"(?:http|error) [45]\d\d)\b", re.I)
_TERMINAL_ROLES = {"intro", "thank_you", "end", "screen_out"}


def read_outcome(snapshot: SurveySnapshot, coverage: Coverage) -> ReadOutcome:
    if snapshot.all_questions():
        return "reviewable"
    recognised = {page.id for page in snapshot.pages if snapshot.page_role(page) in _TERMINAL_ROLES}
    unknown = [page for page in snapshot.pages if page.id not in recognised]
    if any(_ERROR_SCREEN.search(snapshot.page_copy(page)) for page in unknown):
        return "error"
    if coverage.stop_reason == "reader_error" and not recognised:
        return "error"
    return "limited"


def validated_captures(captured: ReadResult) -> list[tuple[int, str, str]]:
    """(position, page_id, path) rows; any capture outside the reader directory rejects the whole set."""
    root = captured.capture_dir.resolve()
    rows = []
    for position, capture in enumerate(captured.captures):
        path = capture.viewport_png.resolve()
        if not path.is_relative_to(root):
            raise ValueError("Capture outside reader directory")
        rows.append((position, capture.page_id, str(path)))
    return rows


def store_evidence(db, survey_id: str, version: int, coverage: dict,
                   rows: list[tuple[int, str, str]]) -> EvidenceAction:
    """Bind coverage and captures to ONE attempt, inside the caller's transaction.

    A reread of the same version replaces the whole bundle only if it captured at least as many
    screens; otherwise the prior bundle is retained intact. A bundle is never mixed, so there is
    never an old capture tail under new coverage. Decisions and history are not touched.
    """
    key = (survey_id, version)
    kept = db.execute("SELECT COUNT(*) FROM captures WHERE survey_id=? AND version=?", key).fetchone()[0]
    has_bundle = db.execute("SELECT 1 FROM coverage WHERE survey_id=? AND version=?", key).fetchone() is not None
    if has_bundle and len(rows) < kept:
        return "retained"
    db.execute("DELETE FROM captures WHERE survey_id=? AND version=?", key)
    db.executemany("INSERT INTO captures VALUES (?,?,?,?,?)",
                   [(survey_id, version, position, page_id, path) for position, page_id, path in rows])
    # The reader's own counter is a claim; the stored captures are the evidence.
    db.execute("INSERT OR REPLACE INTO coverage(survey_id,version,data) VALUES (?,?,?)",
               (survey_id, version, json.dumps(dict(coverage, pages_captured=len(rows)))))
    return "replaced" if has_bundle else "new"
