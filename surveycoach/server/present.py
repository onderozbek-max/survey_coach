"""How findings read to a researcher, without changing stored reviews."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import re

from surveycoach.fix_queue import build_queue
from surveycoach.labels import screen_labels
from surveycoach.quality import build_quality
from surveycoach.recommendations import with_action
from surveycoach.server.extras import display_type
from surveycoach.server.my_changes import build_my_changes
from surveycoach.server.plan import build_plan
from surveycoach.server.rounds import field_location, locate, locations, presentation
from surveycoach.signals import build_overview
from surveycoach.snapshot import SurveySnapshot
from surveycoach.timing import TimingConstants, reading_basis

ABSORBS = {
    "B1": {"5.1", "5.2", "5.3"}, "B2": {"4.1", "4.3", "8.4"},
    "B5": {"1.4"}, "B7": {"7.1", "7.3", "7.6"},
}

_ID = r"(?:B\d+|\d{1,2}\.\d+)"
_BOOKKEEPING = re.compile(
    rf"(?:This (?:finding|issue) )?also covers? "
    rf"(?P<ids>{_ID}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+){_ID})*)[.!?]?",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)


def _place(finding: dict) -> tuple:
    """Question, page and survey scopes must never collide."""
    page = finding.get("page_id") or None
    if finding.get("question_id"):
        return "question", page, finding["question_id"]
    if page:
        return "page", page
    return ("survey",)


def humanize(text: str | None, titles: dict[str, str]) -> tuple[str, list[str]]:
    """Remove explicit ID-only bookkeeping; preserve ordinary prose verbatim.

    Numbers alone are not rubric references: 'covers 4.1 minutes' stays intact.
    Unknown IDs stay visible rather than silently losing an explanation.
    """
    text = text or ""
    kept, covered = [], []
    for sentence in _SENTENCE.findall(text):
        match = _BOOKKEEPING.fullmatch(sentence.strip())
        ids = re.findall(_ID, match["ids"], re.IGNORECASE) if match else []
        ids = [cid.upper() for cid in ids]
        if ids and all(cid in titles for cid in ids):
            covered.extend(titles[cid] for cid in ids)
        else:
            kept.append(sentence)
    prose = "".join(kept).strip() if covered else text
    return prose, list(dict.fromkeys(covered))


def present_findings(findings: list[dict], titles: dict[str, str], snapshot: dict | None = None) -> list[dict]:
    """Humanise and annotate copies, retaining every finding and its severity.

    Absorption is recomputed each time; titles survive a second projection after
    their bookkeeping sentence has already been removed. Every finding leaves with one
    action kind (explicit, or the legacy fallback) and, given the snapshot, where to look.
    No scoring or decisions belong here.
    """
    out = deepcopy(findings)
    places = locations(snapshot) if snapshot else []
    screens = screen_labels(SurveySnapshot.model_validate(snapshot)) if snapshot else []
    for index, finding in enumerate(out):
        text, covered = humanize(finding.get("explanation"), titles)
        finding["explanation"] = text
        finding["also_covers"] = list(dict.fromkeys([
            *finding.get("also_covers", []), *covered,
        ]))
        finding.pop("absorbed_by", None)
        finding.pop("also_affects", None)
        out[index] = finding = with_action(finding)
        if not finding.get("field_location"):
            where = field_location(finding, locate(finding, places), screens) if snapshot else None
            if where:
                finding["field_location"] = where
    for blocker in (item for item in out if item["severity"] == "must_fix"):
        family = ABSORBS.get(blocker["criterion_id"], set())
        for other in out:
            if (other["severity"] != "must_fix" and other["criterion_id"] in family
                    and "absorbed_by" not in other and _place(other) == _place(blocker)):
                other["absorbed_by"] = blocker["fingerprint"]
                blocker.setdefault("also_affects", []).append(other["fingerprint"])
    return out


def enrich(data: dict, rubric) -> dict:
    """Return a detached presentation payload; never decorate stored evidence.

    Repository rounds present findings before comparison. Re-presenting here is
    deliberately idempotent, so offline payloads use exactly the same contract.
    Curation always uses the caller's final validated/carried decisions.
    """
    data = deepcopy(data)
    snapshot = SurveySnapshot.model_validate(dict(
        data["snapshot"], survey_type=data.get("survey_type")
        or data["snapshot"].get("survey_type", "non_ihut_product")))
    # Derived output only: never add preview metadata to snapshot models, stored
    # captures or cache/hash inputs. Overwrite any stale serialized basis on read.
    for encoded, page in zip(data["snapshot"]["pages"], snapshot.pages, strict=True):
        encoded["reading_basis"] = reading_basis(page)
        encoded["stimulus_text"] = page.stimulus_text
    data["screens"] = screen_labels(snapshot)
    # Score and coverage are methodology: experts open them, the primary payload never leads with them.
    data["methodology"] = {"quality": build_quality(data.get("review") or {}, rubric),
                           "not_checked_automatically": []}
    data.pop("quality", None)
    data["effort_method"] = asdict(TimingConstants())
    if data.get("review"):
        titles = {c.id: c.title for c in rubric.criteria} | {b.id: b.title for b in rubric.blockers}
        points = {c.id: c.points for c in rubric.criteria}
        findings = present_findings(data["review"].get("findings", []), titles, data["snapshot"])
        data["review"]["findings"] = findings
        decisions = data.get("decisions", {})
        data["plan"] = build_plan(findings, decisions, points, data["screens"])
        survey_type, source = display_type(data)
        data["overview"] = build_overview(
            snapshot, data["review"], decisions, data["screens"], data["plan"], rubric,
            survey_type=survey_type, type_source=source, coverage=data.get("coverage"))
        data["methodology"]["not_checked_automatically"] = data["overview"].pop("not_checked_automatically")
    data["queue"] = build_queue(data.get("overview", {}).get("items", []))
    data["my_changes"] = build_my_changes(data)
    data["presentation"] = presentation(data)
    return data
