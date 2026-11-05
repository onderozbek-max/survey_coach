"""Since last version (brief 4.6): the four round buckets, compact, for the delta card on Verdict.

The buckets come from `rounds.compare_rounds` untouched. Nothing is dropped: "couldn't compare" stays a
bucket of its own, and a finding that disappears is only ever "no longer flagged by our checks", never proof.
Version 1 has nothing to compare, so there is no delta (D16: the UI hides the comparison there).
"""
from __future__ import annotations

BUCKETS = ("fixed", "still", "new", "uncertain")
SNIPPET_MAX = 160
CAVEAT = "Fixed = no longer flagged by our checks."
_REWRITE = "Fixed with your rewrite"


def _snippet(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    if not text:
        return None
    return text if len(text) <= SNIPPET_MAX else text[:SNIPPET_MAX - 1].rstrip() + "…"


def _entry(entry: dict, *, fixed: bool = False) -> dict:
    finding = entry.get("prior_finding") or entry.get("current_finding") or {}
    out = {"fingerprint": finding.get("fingerprint"), "criterion_id": finding.get("criterion_id"),
           "headline": finding.get("headline"), "location": entry.get("screen_label"),
           "resolution": entry.get("resolution")}
    if fixed:
        out.update(before=_snippet(entry.get("old_wording")), after=_snippet(entry.get("new_wording")),
                   by_rewrite=entry.get("resolution") == _REWRITE)
    return out


def summary_text(counts: dict) -> str:
    return (f"{counts['fixed']} fixed · {counts['still']} still open · {counts['new']} new · "
            f"{counts['uncertain']} couldn't compare")


def build_version_delta(round_changes: dict, version: int) -> dict | None:
    """None for the first version, else counts that equal the bucket lengths by construction."""
    previous = round_changes.get("compared_to_round")
    if version <= 1 or not previous:
        return None
    buckets = {key: [_entry(e, fixed=key == "fixed") for e in round_changes.get(key, [])] for key in BUCKETS}
    counts = {key: len(entries) for key, entries in buckets.items()}
    return {"from_version": previous, "to_version": version, "counts": counts, "summary": summary_text(counts),
            "caveat": CAVEAT, **buckets}
