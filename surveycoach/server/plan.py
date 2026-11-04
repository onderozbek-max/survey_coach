"""Turn findings into a short plan without rewriting findings or decisions."""
from __future__ import annotations


QUICK_WIN_LIMIT = 6
NICE_TO_HAVE = {"9.1", "9.2"}


def _decided(decision: dict | None) -> bool:
    if not decision:
        return False
    return decision.get("action") in {"pick", "original"} or (
        decision.get("action") == "keep" and bool(decision.get("reason", "").strip())
    )


def build_plan(findings: list[dict], decisions: dict,
               points: dict[str, float], screens: list[dict]) -> dict:
    """Include every blocker, up to six quick wins, then remaining patterns."""
    order = {screen["page_id"]: screen["screen"] for screen in screens}
    order.update({question["id"]: screen["screen"]
                  for screen in screens for question in screen["questions"]})

    def where(finding: dict) -> int:
        return (order.get(finding.get("question_id"))
                or order.get(finding.get("page_id")) or 0)

    groups: dict[tuple, list[dict]] = {}
    visible = (finding for finding in findings if not finding.get("absorbed_by"))
    for finding in sorted(visible, key=where):
        if finding["severity"] == "must_fix":
            key = (finding["fingerprint"],)
        else:
            key = (finding["criterion_id"], " ".join(finding["headline"].lower().split()))
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
            "decided": all(_decided(decisions.get(member["fingerprint"]))
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
