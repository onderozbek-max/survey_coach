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


def guard_recommendation(finding: dict, snapshot: dict | None = None) -> dict:
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
    from surveycoach.answer_edits import answer_addition
    finding = answer_addition(finding, snapshot)
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


# --- Action contract (brief 6.3) -------------------------------------------------------------
# Every rendered finding carries exactly one action: paste wording, 1-3 steps, or one question
# the researcher answers. Checks may set the fields; legacy findings get a fallback here, so the
# site only renders and never invents.

CRITERION_IDS = "criterion IDs"   # matched by pattern (B7, criterion 3.4), not as a literal word
BANNED_WORDS = (
    "assessed", "unassessed", "heuristic", "configured", "threshold", "provisional", "coverage",
    "saved assessment", "captured path", "reader", "snapshot", "calibrated", "verified route",
    "partial test participant", "risk checks", "rubric", CRITERION_IDS,
)
_BANNED = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(BANNED_WORDS, key=len, reverse=True)
                     if w != CRITERION_IDS) + r")\b", re.IGNORECASE)
_CRITERION_ID = re.compile(r"\bB[1-7]\b|\b(?:criterion|criteria)\s+\d{1,2}\.\d\b", re.IGNORECASE)
MAX_STEPS = 3
MAX_STEP_WORDS = 30
MAX_IMPACT_WORDS = 20

# Findings whose only honest action is a human judgement on a real phone. One table, so the
# state mapping (status.py) and the action fallback can never disagree.
# (criterion, severities it applies to or None, headline pattern or None, question)
HUMAN_JUDGEMENT = (
    ("B7", {"worth_improving"}, None,
     "Open this screen on your phone: do all the images appear?"),
    ("7.2", None, None,
     "Open this screen on your phone: do the images look right, not cropped or stretched?"),
    ("6.2", None, re.compile(r"\banswer choices; review the phone layout", re.IGNORECASE),
     "Scroll this question on your phone: are all the answers easy to reach?"),
)


def banned_words(text: str | None) -> list[str]:
    """Sorted, lowercase banned terms found as whole words; criterion IDs report as one term."""
    found = {match.lower() for match in _BANNED.findall(text or "")}
    if _CRITERION_ID.search(text or ""):
        found.add(CRITERION_IDS)
    return sorted(found)


def _has_paste(finding: dict) -> bool:
    return bool((finding.get("suggested_text") or "").strip()
                or any((o.get("text") or "").strip() for o in finding.get("options") or []))


def _judgement_question(finding: dict) -> str | None:
    for criterion, severities, headline, question in HUMAN_JUDGEMENT:
        if (finding.get("criterion_id") == criterion
                and (severities is None or finding.get("severity") in severities)
                and (headline is None or headline.search(finding.get("headline") or ""))
                and not (criterion == "7.2" and finding.get("source", "auto") != "auto")):
            return question
    return None


def action_kind_of(finding: dict) -> str:
    """Explicit kind first, then human judgement, then paste text, else steps."""
    if finding.get("action_kind"):
        return finding["action_kind"]
    if _judgement_question(finding):
        return "you_check"
    return "paste" if _has_paste(finding) else "steps"


def _plain_step(finding: dict) -> str:
    """Legacy explanation as one step: keep the sentences a researcher can act on.

    Sentences about other checks ("also covers criterion 5.1") or in our own jargon are dropped;
    if nothing plain is left the headline stands in. Explicit steps never pass through here.
    """
    sentences = re.split(r"(?<=[.!?])\s+", (finding.get("explanation") or "").strip())
    kept = [s for s in sentences if s and not banned_words(s)]
    return " ".join(kept) or finding.get("headline", "")


def with_action(finding: dict) -> dict:
    """Copy with the action fields filled in. Explicit actions are kept; projection is idempotent."""
    out = dict(finding)
    if out.get("action_kind"):
        return out
    kind = action_kind_of(out)
    out.update(action_kind=kind, action_fallback=True)
    if kind == "you_check":
        out["you_check"] = _judgement_question(out)
    elif kind == "steps":
        out["steps"] = [_plain_step(out)]
    return out


def _words(text: str) -> int:
    return len(text.split())


def validate_finding(finding: dict) -> list[str]:
    """Problem codes for one finding after `with_action`; empty means it honours the contract."""
    problems = []
    kind = finding.get("action_kind")
    steps = [s for s in finding.get("steps") or []]
    you_check = (finding.get("you_check") or "").strip()
    present = {"paste": _has_paste(finding), "steps": bool(steps), "you_check": bool(you_check)}
    if kind is None:
        problems.append("no_action")
    else:
        if kind == "paste" and not present["paste"]:
            problems.append("empty_paste")
        if kind == "steps" and not 1 <= len(steps) <= MAX_STEPS:
            problems.append("steps_count")
        if kind == "you_check" and not you_check:
            problems.append("empty_you_check")
        if sum(present.values()) > 1:
            problems.append("multiple_actions")
    if not finding.get("action_fallback") and any(_words(s) > MAX_STEP_WORDS for s in steps):
        problems.append("step_long")
    if _words(finding.get("member_impact") or "") > MAX_IMPACT_WORDS:
        problems.append("member_impact_long")
    visible = [finding.get("headline"), finding.get("member_impact"), *steps, you_check,
               finding.get("field_location")]
    for word in banned_words(" ".join(t for t in visible if t)):
        problems.append(f"banned:{word}")
    return problems
