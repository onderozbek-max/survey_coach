"""The verdict (brief 4.3): kind, headline, survey story, tiles and time, all computed from data.

Rule, exactly as implemented (an item is open until an explicit decision closes it; a kept item
needs a stated reason):

  * any open fix_before_launch item               -> kind `fix_before_launch`
  * else any open worth_improving or you_check    -> kind `almost_ready`
  * else                                          -> kind `ready_for_signoff`

Ready therefore means nothing is open: no fix, every curated You check done or kept, and every
improvement applied or kept on purpose. With no evidence at all (nothing assessed, nothing raised)
there is no verdict, rather than a confident "ready". The headline's counts are always the open
items of the same list the tiles and the cards use.

Time is duration only: within the survey type's target is looks_good, over it is worth_improving
(never a fix), and with branching the duration is unknown (state None) until someone times a run.
"""
from __future__ import annotations

from math import floor

from surveycoach.snapshot import Page, SurveySnapshot
from surveycoach.status import FIX_BEFORE_LAUNCH, IMPROVE, YOU_CHECK, duration_state
from surveycoach.timing import Timing
from surveycoach.you_check import repeated_concept_pages

READY, ALMOST, FIX = "ready_for_signoff", "almost_ready", "fix_before_launch"
TYPE_PHRASES = {"community_pulse": "community surveys", "ihut": "home-use tests",
                "non_ihut_product": "product tests", "services_concept": "concept tests",
                "market_research": "market research surveys"}


def minutes_text(value: float) -> str:
    """Nearest half minute, with ties rounded up rather than to even."""
    halves = floor(value * 2 + .5)
    whole, half = divmod(halves, 2)
    number = (str(whole) if whole or not half else "") + ("½" if half else "")
    return f"{number} {'minute' if halves in (1, 2) else 'minutes'}"


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def headline_for(fix: int, improve: int, you_check: int) -> str:
    if fix:
        return f"{_plural(fix, 'thing', 'things')} to fix before launch"
    parts = []
    if improve:
        parts.append(_plural(improve, "quick improvement", "quick improvements"))
    if you_check:
        parts.append(_plural(you_check, "thing", "things") + " to check yourself")
    return "Almost ready: " + " and ".join(parts) if parts else "Ready for sign-off"


def _asked(page: Page) -> list:
    return [q for q in page.questions if q.kind != "info"]


def survey_story(snapshot: SurveySnapshot) -> str:
    """One sentence built only from detected structure. Anything undetected is left out."""
    pages = snapshot.pages
    concept = [i for i, p in enumerate(pages) if _asked(p) and p.stimulus_text.strip()]
    repeated = [pages.index(p) for p in repeated_concept_pages(snapshot)]
    count = lambda part: sum(len(_asked(p)) for p in part)
    pieces = ["get a welcome"] if any(snapshot.page_role(p) == "intro" for p in pages) else []
    if not concept:
        if count(pages):
            pieces.append(f"answer {_plural(count(pages), 'question', 'questions')}")
    else:
        if warm := count(pages[:concept[0]]):
            pieces.append(f"answer {_plural(warm, 'warm-up question', 'warm-up questions')}")
        if any(i not in repeated for i in concept):
            pieces.append("see the idea")
        if repeated:
            pieces.append(f"react to {len(repeated)} similar ideas")
            # A block is a repeated screen plus the follow-ups up to the next one.
            end = repeated[-1] + (repeated[-1] - repeated[-2]) - 1
            if wrap := count(pages[end + 1:]):
                pieces.append(f"wrap up with {_plural(wrap, 'question', 'questions')}")
        elif more := count(pages[concept[-1] + 1:]):
            pieces.append(f"answer {_plural(more, 'more question', 'more questions')}")
    if not pieces:
        return ""
    head = ", ".join(pieces[:-1]) + (", then " if len(pieces) > 1 else "")
    return f"Members {head}{pieces[-1]}."


def time_info(snapshot: SurveySnapshot, timing: Timing, targets: tuple, survey_type: str,
              type_source: str) -> dict:
    """Duration against the survey type's target. `state` is None when the total is uncertain."""
    low, high = targets
    minutes = timing.total_seconds / 60
    known = bool(snapshot.pages) and not timing.path_uncertain
    phrase = TYPE_PHRASES[survey_type]
    summary = f"About {minutes_text(minutes)}."
    summary += (" Branching makes the total uncertain." if timing.path_uncertain
                else f" {phrase.capitalize()} usually take {low:g}–{high:g} minutes.")
    return {"minutes": round(minutes, 1), "label": f"About {minutes_text(minutes)}", "summary": summary,
            "target_low": low, "target_high": high,
            "state": duration_state(minutes, high) if known else None,
            "survey_type": survey_type, "type_source": type_source, "path_uncertain": timing.path_uncertain}


def build_verdict(items: list[dict], *, evidence: bool, story: str, time: dict) -> dict | None:
    """Verdict over the shared item list; None when nothing was assessed and nothing was raised."""
    if not items and not evidence:
        return None
    open_items = [i for i in items if i["open"]]
    tiles = {"fix": sum(i["state"] == FIX_BEFORE_LAUNCH for i in open_items),
             "improve": sum(i["state"] == IMPROVE for i in open_items),
             "you_check": sum(i["state"] == YOU_CHECK for i in open_items)}
    kind = FIX if tiles["fix"] else ALMOST if tiles["improve"] or tiles["you_check"] else READY
    return {"kind": kind, "headline": headline_for(**tiles), "story": story, "tiles": tiles, "time": time,
            "progress": {"done": len(items) - len(open_items), "total": len(items)}}
