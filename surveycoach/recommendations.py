"""Deterministic rewrite hygiene shared by fresh findings and saved-review reads.

This catches fill-in templates, not factual hallucinations: the judge must still
justify concrete wording using the survey context. Never edit original evidence.
"""
from __future__ import annotations

import re

_BRACKETS = re.compile(r"\[([^\[\]\n]+)\]|\{([^{}\n]+)\}|<([^<>\n]+)>")
_TEMPLATE_WORDS = re.compile(
    r"\b(insert|fill|replace|specify|describe|enter|add|your|what|why|how|"
    r"purpose|goal|objective|topic|product|brand|feature|audience|research|"
    r"decision|benefit|incentive|reward|amount|duration|timeframe|time|"
    r"name|number|detail|details|specific|description|context|placeholder|tbd|xxx|x)\b",
    re.IGNORECASE,
)
_NUMERIC = re.compile(r"[\d\s.,+−–—%/():=<>-]+")
NO_REWRITE = (
    "No ready-to-use rewrite is available because the survey does not provide enough context. "
    "Confirm the missing study details with the study owner before drafting replacement wording."
)


def _has_template(text: str) -> bool:
    for match in _BRACKETS.finditer(text):
        # Numeric intervals and literal survey labels are not fill-ins. A template
        # remains unusable even if the original survey already contained it.
        body = next(group for group in match.groups() if group is not None).strip()
        if _NUMERIC.fullmatch(body):
            continue
        # Bracketed prose is not usable copy. Keep only numeric notation and
        # short literal labels such as [A], [B2], not guessed missing facts.
        if _TEMPLATE_WORDS.search(body.replace("_", " ")) or not re.fullmatch(r"[A-Z][A-Z0-9]{0,2}", body):
            return True
    return False


def guard_recommendation(finding: dict) -> dict:
    """Return a sanitized copy, retaining the finding and any usable alternatives.

    Keeping this JSON-shaped lets the same guard handle historical payloads without
    validating them against today's model or changing stored fingerprints/scores.
    """
    if finding.get("criterion_id") == "7.2" and finding.get("source", "auto") == "auto":
        finding = dict(finding,
            headline="Check image on mobile: potential layout risk",
            explanation="Open the actual survey on a mobile device. Check readability, cropping, distortion and image size. "
                        "Orientation alone does not prove a broken layout. Preserve research content; adjust only if needed.",
            member_impact="Desktop drafting can hide image layout problems on a phone.")
    suggested = finding.get("suggested_text")
    options = finding.get("options") or []
    safe_options = [option for option in options
                    if option.get("text", "").strip() and not _has_template(option["text"])]
    bad_suggestion = bool(suggested and _has_template(suggested))
    removed = bad_suggestion or len(safe_options) != len(options)
    if not removed:
        return dict(finding)
    if bad_suggestion or not (suggested or "").strip():
        suggested = safe_options[0]["text"] if safe_options else None
    cleaned = dict(finding, suggested_text=suggested, options=safe_options)
    if not suggested and not safe_options:
        explanation = finding.get("explanation") or ""
        if NO_REWRITE not in explanation:
            cleaned["explanation"] = f"{explanation}\n\n{NO_REWRITE}".strip()
    return cleaned
