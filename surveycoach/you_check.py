"""The curated You check list (D-Checklist): at most six human checks, each raised only on evidence.

Anything the engine cannot verify and a human settles in seconds becomes one of these items, instead
of "40% coverage". Each is finding-like, with a stable fingerprint (`you-check:<id>:<hash>`) so the
existing decisions API records "done" or "kept" with no new endpoint. The fingerprint follows the
evidence: when the survey changes under an item, its old tick no longer applies.

Everything else the engine could not assess is NOT a You check item; it is listed under
`not_checked_automatically` and never blocks sign-off.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass

from surveycoach.snapshot import Page, SurveySnapshot
from surveycoach.timing import Timing, parse_promised_minutes

MAX_ITEMS = 6
MAX_NAMES = 4
# id -> (theme, title in member language, signal the item belongs to, criteria it stands in for)
THEMES = {
    "images": ("Images and media", "Images load on a phone", "phone", ("7.1", "7.2", "7.3", "7.5", "7.6", "B7")),
    "display_logic": ("Display logic", "Questions that follow an earlier answer", "energy", ("8.4",)),
    "randomization": ("Order of ideas", "Ideas shown in a random order", "honest", ("5.3",)),
    "required": ("Required questions", "Key questions are required", "honest", ("2.4", "8.6")),
    "other_text": ("Other answers", "Other answers show a text box", "honest", ("4.1",)),
    "timed_run": ("Timing", "One timed run-through", "time", ("2.1", "B5")),
    "branch_paths": ("Other paths", "Check the other paths", "energy", ()),
}
_ASSUMES = re.compile(
    r"\b(?:you (?:said|answered|selected|chose|picked|mentioned|indicated|rated|told us)"
    r"|your (?:previous|last|earlier|prior) (?:answer|response|choice|rating)"
    r"|(?:why|what) (?:did|made) you (?:choose|select|pick|say|answer|rate)"
    r"|has you saying|saying ['\"“‘]?(?:yes|no)\b)", re.IGNORECASE)
_OTHER = re.compile(r"^\s*(?:other|something else)\b", re.IGNORECASE)
_NOT_KEY = {"info", "text_short", "text_long", "unknown"}


@dataclass
class _Context:
    snapshot: SurveySnapshot
    timing: Timing
    target_high: float
    label: dict          # question id -> Q label
    screen: dict         # page id -> screen number
    coverage: dict | None = None   # what the reader walked (detail["coverage"]); None when nothing was walked

    def names(self, labels: list[str]) -> str:
        shown = labels[:MAX_NAMES]
        if len(labels) > MAX_NAMES:
            return f"{', '.join(shown)} and {len(labels) - MAX_NAMES} more"
        return shown[0] if len(shown) == 1 else f"{', '.join(shown[:-1])} and {shown[-1]}"

    def screens_text(self, page_ids: list[str]) -> str:
        numbers = [str(self.screen[p]) for p in page_ids]
        return (f"screen {numbers[0]}" if len(numbers) == 1
                else f"screens {', '.join(numbers[:-1])} and {numbers[-1]}")

    def asked(self):
        """(page, question) for every real question, in survey order."""
        return [(p, q) for p in self.snapshot.pages for q in p.questions if q.kind != "info"]


def _has_media(page: Page) -> int:
    return (len(page.media) + page.declared_media
            + sum(len(q.media) + sum(1 for o in q.options if o.media) for q in page.questions))


def _found(item_id: str, pages: list[str], questions: list[str], instruction: str, reason: str = "") -> dict:
    return {"id": item_id, "pages": pages, "question_ids": questions, "instruction": instruction,
            "reason": reason}


def _images(ctx: _Context):
    pages = [p for p in ctx.snapshot.pages if _has_media(p)]
    if not pages:
        return None
    many = sum(_has_media(p) for p in pages) > 1
    where = ctx.screens_text([p.id for p in pages])
    return _found("images", [p.id for p in pages], [],
                  f"Open {where} on your phone: {'do all the images' if many else 'does the image'} show up?")


def _display_logic(ctx: _Context):
    hits = [(p, q) for p, q in ctx.asked() if _ASSUMES.search(q.text)]
    if not hits:
        return None
    labels = [ctx.label[q.id] for _, q in hits]
    verb, rest = ("refers", "Does it only show") if len(hits) == 1 else ("refer", "Do they only show")
    return _found("display_logic", [p.id for p, _ in hits], [q.id for _, q in hits],
                  f"{ctx.names(labels)} {verb} to an earlier answer. {rest} to members who gave that answer?")


def _signature(page: Page) -> tuple:
    return tuple((q.kind, " ".join(q.text.lower().split()), tuple(sorted(o.label for o in q.options)))
                 for q in page.questions if q.kind != "info")


def repeated_concept_pages(snapshot: SurveySnapshot) -> list[Page]:
    """The largest set of screens that repeat one question set, each with its own concept copy or media."""
    groups = defaultdict(list)
    for page in snapshot.pages:
        if _signature(page) and (page.stimulus_text.strip() or _has_media(page)):
            groups[_signature(page)].append(page)
    return max((g for g in groups.values() if len(g) > 1), key=len, default=[])


def _randomization(ctx: _Context):
    repeated = repeated_concept_pages(ctx.snapshot)
    if not repeated:
        return None
    firsts = [next(q for q in p.questions if q.kind != "info") for p in repeated]
    labels = [ctx.label[q.id] for q in firsts]
    return _found("randomization", [p.id for p in repeated], [q.id for q in firsts],
                  f"Are the {len(repeated)} idea screens ({', '.join(labels)}) shown in a random order? "
                  "A fixed order can favor the first one.")


def _required(ctx: _Context):
    hits = [(p, q) for p, q in ctx.asked()
            if q.kind not in _NOT_KEY and not q.conditional and not _ASSUMES.search(q.text)
            and q.required is not True]
    if not hits:
        return None
    labels = [ctx.label[q.id] for _, q in hits]
    return _found("required", [p.id for p, _ in hits], [q.id for _, q in hits],
                  f"Do you want {ctx.names(labels)} to be required? Check each one's setting in RedJade.")


def _other_text(ctx: _Context):
    hits = [(p, q, next(o for o in q.options if _OTHER.match(o.label) and o.is_other_with_text is not True))
            for p, q in ctx.asked()
            if any(_OTHER.match(o.label) and o.is_other_with_text is not True for o in q.options)]
    if not hits:
        return None
    labels = [ctx.label[q.id] for _, q, _ in hits]
    also = f" (same on {ctx.names(labels[1:])})" if len(labels) > 1 else ""
    return _found("other_text", [p.id for p, _, _ in hits], [q.id for _, q, _ in hits],
                  f'On {labels[0]}, pick "{hits[0][2].label}"{also}. Does a text box appear?')


def _timed_run(ctx: _Context):
    if not ctx.asked():
        return None
    minutes = max(1, round(ctx.timing.total_seconds / 60))
    promised = parse_promised_minutes(ctx.snapshot.intro_text)
    if promised is not None:
        unit = "minute" if promised == 1 else "minutes"
        ask, reason = f"the {promised} {unit} your welcome screen promises", f"promise:{promised}"
    elif ctx.timing.path_uncertain:
        ask, reason = f"about {minutes} {'minute' if minutes == 1 else 'minutes'}", "branching"
    else:   # a length over target is the duration item's business (items.py), not a second ask
        return None
    return _found("timed_run", [], [], f"Time one run-through on your phone. Does it take {ask}?", reason)


def _branch_paths(ctx: _Context):
    """The reader walks one route. Unless every path was walked, a survey with a walked route or with branching
    the snapshot can see needs a human look at the other routes. A linear survey nobody walked has no
    "other" route to claim, and a fully walked one has none left."""
    if ctx.coverage and ctx.coverage.get("full_branching_coverage"):
        return None
    pages = [p for p in ctx.snapshot.pages if p.kind == "screen_out"]
    hits = [(p, q) for p, q in ctx.asked() if q.conditional]
    if not (ctx.coverage or pages or hits):
        return None
    named = []
    if hits:
        labels = [ctx.label[q.id] for _, q in hits]
        named.append(f"{ctx.names(labels)} ({ctx.screens_text([p.id for p, _ in hits])})")
    if pages:
        named.append(f"the screen-out screen (screen {ctx.screen[pages[0].id]})" if len(pages) == 1 else
                     f"the screen-out screens ({ctx.screens_text([p.id for p in pages])})")
    reach = f" to reach {' and '.join(named)}" if named else ""
    ask = "do those screens look right?" if named else "do you reach any screen we didn't show?"
    return _found("branch_paths", [p.id for p, _ in hits] + [p.id for p in pages], [q.id for _, q in hits],
                  f"We checked one route. Run it again on your phone and pick different answers{reach}: {ask}",
                  "walked" if ctx.coverage else "branching")


# Detection order is priority order: when more than MAX_ITEMS apply, the later ones are dropped, so the branch
# check (which holds back sign-off) is raised first. Items are shown in THEMES order.
_DETECTORS = (_branch_paths, _images, _display_logic, _randomization, _required, _other_text, _timed_run)


def _finish(found: dict, ctx: _Context) -> dict:
    theme, title, signal, covers = THEMES[found["id"]]
    pages = sorted(set(found["pages"]), key=lambda p: ctx.screen[p])
    evidence = [found["id"], pages, sorted(found["question_ids"]), found["reason"]]
    digest = hashlib.sha1(json.dumps(evidence).encode()).hexdigest()[:8]
    return {"id": found["id"], "fingerprint": f"you-check:{found['id']}:{digest}", "theme": theme,
            "title": title, "instruction": found["instruction"],
            "where": ctx.screens_text(pages).capitalize() if pages else "Whole survey",
            "pages": pages, "screens": [ctx.screen[p] for p in pages],
            "questions": [ctx.label[q] for q in found["question_ids"]],
            "signal": signal, "covers": list(covers)}


def build_you_checks(snapshot: SurveySnapshot, screens: list[dict], timing: Timing,
                     target_high: float, coverage: dict | None = None) -> list[dict]:
    """Curated items for this survey, in fixed theme order. Pure: no I/O, snapshot untouched."""
    ctx = _Context(snapshot, timing, target_high,
                   label={q["id"]: q["label"] for s in screens for q in s["questions"]},
                   screen={s["page_id"]: s["screen"] for s in screens}, coverage=coverage)
    found = [item for item in (detect(ctx) for detect in _DETECTORS) if item][:MAX_ITEMS]
    return [_finish(item, ctx) for item in sorted(found, key=lambda item: list(THEMES).index(item["id"]))]
