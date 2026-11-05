"""Turn findings into a short plan without rewriting findings or decisions."""
from __future__ import annotations

import re

from surveycoach.labels import QUESTION_LABEL
from surveycoach.recommendations import with_action
from surveycoach.status import is_decided

QUICK_WIN_LIMIT = 6
NICE_TO_HAVE = {"9.1", "9.2"}


def _mask_label(line: str, own_label: str | None) -> str:
    """Replace question labels with Q#: the generated Q4 style, and the finding's own custom label ("Research B")."""
    if own_label and not QUESTION_LABEL.fullmatch(own_label):
        line = re.sub(rf"(?<!\w){re.escape(own_label)}(?!\w)", "Q#", line)
    return QUESTION_LABEL.sub("Q#", line)


def action_signature(finding: dict, own_label: str | None = None) -> tuple:
    """What the researcher is asked to do, with the question label masked: 'Scroll Q4 ...' and 'Scroll Q6 ...'
    are one action, while two different rewrites, or steps naming different words, are two."""
    served = with_action(finding)
    kind = served["action_kind"]
    if kind == "paste":     # the survey's own wording: compared exactly, never masked
        return kind, (served.get("suggested_text") or "", *(o["text"] for o in served.get("options") or []))
    lines = served.get("steps") or [] if kind == "steps" else [served.get("you_check") or ""]
    return kind, tuple(" ".join(_mask_label(line, own_label).lower().split()) for line in lines)


def build_plan(findings: list[dict], decisions: dict,
               points: dict[str, float], screens: list[dict]) -> dict:
    """Include every blocker, up to six quick wins, then remaining patterns."""
    order = {screen["page_id"]: screen["screen"] for screen in screens}
    order.update({question["id"]: screen["screen"]
                  for screen in screens for question in screen["questions"]})

    def where(finding: dict) -> int:
        return (order.get(finding.get("question_id"))
                or order.get(finding.get("page_id")) or 0)

    own_labels = {question["id"]: question.get("label")
                  for screen in screens for question in screen["questions"]}
    groups: dict[tuple, list[dict]] = {}
    visible = (finding for finding in findings if not finding.get("absorbed_by"))
    for finding in sorted(visible, key=where):
        if finding["severity"] == "must_fix":
            key = (finding["fingerprint"],)
        else:
            key = (finding["criterion_id"], " ".join(finding["headline"].lower().split()),
                   action_signature(finding, own_labels.get(finding.get("question_id"))))
        groups.setdefault(key, []).append(finding)

    items = []
    for members in groups.values():
        lead = members[0]
        if lead["severity"] == "must_fix":
            tier = "must_fix"
        elif lead["criterion_id"] in NICE_TO_HAVE:
            tier = "nice_to_have"
        else:
            tier = "improve"
        items.append({
            "id": (lead["fingerprint"] if len(members) == 1
                   else f"pattern-{lead['fingerprint']}"),
            "fingerprints": [member["fingerprint"] for member in members],
            "criterion_id": lead["criterion_id"], "headline": lead["headline"],
            "count": len(members), "tier": tier, "screen": where(lead),
            "decided": all(is_decided(decisions.get(member["fingerprint"]))
                           for member in members),
        })

    must = [item for item in items if item["tier"] == "must_fix"]
    improve = sorted(
        (item for item in items if item["tier"] == "improve"),
        key=lambda item: (-points.get(item["criterion_id"], 0), item["screen"]),
    )
    quick = improve[:QUICK_WIN_LIMIT]
    more = improve[QUICK_WIN_LIMIT:] + [
        item for item in items if item["tier"] == "nice_to_have"
    ]
    return {
        "must_fix": must, "quick_wins": quick, "more": more,
        "counts": {"must_fix": len(must), "quick_wins": len(quick), "more": len(more),
                   "open_must_fix": sum(not item["decided"] for item in must)},
    }
