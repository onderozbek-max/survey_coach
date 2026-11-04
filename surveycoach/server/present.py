"""How findings read to a researcher, without changing stored reviews."""
from __future__ import annotations

from copy import deepcopy
import re

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


def present_findings(findings: list[dict], titles: dict[str, str]) -> list[dict]:
    """Humanise and annotate copies, retaining every finding and its severity.

    Absorption is recomputed each time; titles survive a second projection after
    their bookkeeping sentence has already been removed. No scoring or decisions
    belong here, and no repository or enrichment wiring is needed yet.
    """
    out = deepcopy(findings)
    for finding in out:
        text, covered = humanize(finding.get("explanation"), titles)
        finding["explanation"] = text
        finding["also_covers"] = list(dict.fromkeys([
            *finding.get("also_covers", []), *covered,
        ]))
        finding.pop("absorbed_by", None)
        finding.pop("also_affects", None)
    for blocker in (item for item in out if item["severity"] == "must_fix"):
        family = ABSORBS.get(blocker["criterion_id"], set())
        for other in out:
            if (other["severity"] != "must_fix" and other["criterion_id"] in family
                    and "absorbed_by" not in other and _place(other) == _place(blocker)):
                other["absorbed_by"] = blocker["fingerprint"]
                blocker.setdefault("also_affects", []).append(other["fingerprint"])
    return out
