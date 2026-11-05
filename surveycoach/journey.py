"""The member journey strip (brief 4.4): one segment per screen, grouped into sections.

Everything is derived from the saved survey and its timing estimate, never invented:

* a segment's width is its estimated seconds (the difference of the timing model's running totals, so the
  segments always add up to the survey total exactly);
* a segment's pin is the worst state among the OPEN items on that screen, the same rule the screen markers use;
* sections come from structure only. A welcome, an ending and every info screen are boundaries. A question
  screen with its own concept copy starts a block. Blocks that repeat one shape (at least two in a row, or a
  repeat confirmed by a third whose first screens match) become numbered "Idea 1, Idea 2, ...", and whatever
  trails the last repeated block is the "Wrap-up". Screens before the first concept are the "Warm-up" and a
  single non-repeating concept is "The idea", but only when the concept structure was understood. Everything
  else falls back to neutral "Screens 2-5" labels. No name is ever taken from survey wording.
"""
from __future__ import annotations

from math import floor

from surveycoach.status import FIX_BEFORE_LAUNCH, IMPROVE, STATES, YOU_CHECK, worst_state

ENDING_ROLES = {"thank_you", "screen_out", "end"}
PHRASES = {FIX_BEFORE_LAUNCH: ("thing to fix", "things to fix"), IMPROVE: ("thing to improve", "things to improve"),
           YOU_CHECK: ("thing to check", "things to check")}
FIXED_LABELS = {"welcome": "Welcome", "ending": "Thanks", "warmup": "Warm-up", "idea": "The idea",
                "wrapup": "Wrap-up"}


def _kind(snapshot, page) -> str:
    """welcome | stimulus | question | info | ending."""
    role = snapshot.page_role(page)
    if role == "intro":
        return "welcome"
    if role in ENDING_ROLES:
        return "ending"
    if any(q.kind != "info" for q in page.questions):
        return "stimulus" if page.stimulus_text.strip() else "question"
    return "info"


def _shape(pages: list, kinds: list, start: int, end: int) -> tuple:
    """What a block asks and shows, screen by screen; two blocks repeat when their shapes are equal."""
    return tuple((kinds[i] == "stimulus", tuple((q.kind, len(q.options)) for q in pages[i].questions
                                                  if q.kind != "info")) for i in range(start, end))


def _blocks(pages: list, kinds: list, start: int, end: int) -> tuple[list, tuple | None]:
    """Split a run of question screens into concept blocks; return (blocks, wrap-up span or None)."""
    starts = [i for i in range(start, end) if kinds[i] == "stimulus"]
    bounds = [*starts, end]
    blocks = [(bounds[k], bounds[k + 1]) for k in range(len(starts))]
    wrap = None
    if len(blocks) >= 3:
        first, second, last = blocks[-3:]
        stride = second[1] - second[0]
        if (_shape(pages, kinds, *first) == _shape(pages, kinds, *second)
                and last[1] - last[0] > stride
                and _shape(pages, kinds, last[0], last[0] + stride) == _shape(pages, kinds, *second)):
            blocks[-1], wrap = (last[0], last[0] + stride), (last[0] + stride, last[1])
    return blocks, wrap


def _run_spans(pages: list, kinds: list, start: int, end: int) -> list[tuple]:
    """Spans (kind, start, end-exclusive) for one run of consecutive question screens."""
    if "stimulus" not in kinds[start:end]:
        return [("screens", start, end)]
    blocks, wrap = _blocks(pages, kinds, start, end)
    shapes = [_shape(pages, kinds, *b) for b in blocks]
    groups, counter, spans = [], 0, []
    for block, shape in zip(blocks, shapes):
        if groups and groups[-1][0] == shape:
            groups[-1][1].append(block)
        else:
            groups.append((shape, [block]))
    singles = [members[0] for _, members in groups if len(members) == 1]
    idea = singles[0] if len(singles) == 1 and singles[0] == blocks[0] else None   # first and the only one
    if idea is None and len(singles) == len(groups):
        return [("screens", start, end)]      # concept structure not understood: stay neutral
    if blocks[0][0] > start:
        spans.append(("warmup", start, blocks[0][0]))
    for _, members in groups:
        if len(members) > 1:
            for first, last in members:
                counter += 1
                spans.append((f"repeat:{counter}", first, last))
        else:
            spans.append(("idea" if members[0] == idea else "screens", *members[0]))
    if wrap:
        spans.append(("wrapup", *wrap))
    return spans


def _spans(pages: list, kinds: list) -> list[tuple]:
    spans, i, n = [], 0, len(pages)
    while i < n:
        kind = kinds[i]
        if kind in ("welcome", "ending"):
            j = i
            while j < n and kinds[j] == kind:
                j += 1
            spans.append((kind, i, j))
        elif kind == "info":
            j = i + 1
            spans.append(("screens", i, j))
        else:
            j = i
            while j < n and kinds[j] in ("question", "stimulus"):
                j += 1
            spans.extend(_run_spans(pages, kinds, i, j))
        i = j
    merged = []
    for span in spans:      # neutral neighbours read as one range
        if merged and merged[-1][0] == span[0] == "screens":
            span = ("screens", merged.pop()[1], span[2])
        merged.append(span)
    return merged


def _range_label(start: int, end: int) -> str:
    return f"Screen {start + 1}" if end - start == 1 else f"Screens {start + 1}-{end}"


def _label(kind: str, start: int, end: int) -> str:
    if kind.startswith("repeat:"):
        return f"Idea {kind.split(':')[1]}"
    return FIXED_LABELS.get(kind) or _range_label(start, end)


def _seconds_text(seconds: float) -> str:
    return f"~{max(1, floor(seconds + .5))} sec" if seconds < 90 else f"~{floor(seconds / 60 + .5)} min"


def _plural(count: int, phrase: tuple) -> str:
    return f"{count} {phrase[0] if count == 1 else phrase[1]}"


def _tooltip(label: str, seconds: float, states: list, done: int) -> str:
    parts = [f"{label} · {_seconds_text(seconds)}"]
    counted = [_plural(states.count(s), PHRASES[s]) for s in STATES if s in states]
    if counted:
        parts.append(", ".join(counted))
    elif done:
        parts.append("all handled")
    return " · ".join(parts)


def build_journey(snapshot, screens: list, timing, items: list) -> dict:
    """{"segments": [...], "sections": [...]}; see the module docstring for every rule."""
    pages = snapshot.pages
    kinds = [_kind(snapshot, page) for page in pages]
    tenths = [0] + [round(p.cumulative_seconds * 10) for p in timing.pages]
    open_states, closed = {}, {}
    for item in items:
        for page_id in item.get("pages", []):
            if item["open"]:
                open_states.setdefault(page_id, []).append(item["state"])
            else:
                closed[page_id] = closed.get(page_id, 0) + 1
    sections, segments = [], []
    for number, (kind, start, end) in enumerate(_spans(pages, kinds), 1):
        label = _label(kind, start, end)
        sections.append({"id": f"s{number}", "label": label, "kind": kind.split(":")[0], "start_screen": start + 1,
                         "end_screen": end, "running": tenths[start] / 10,
                         "seconds": (tenths[end] - tenths[start]) / 10})
        for index in range(start, end):
            seconds = (tenths[index + 1] - tenths[index]) / 10
            states = open_states.get(pages[index].id, [])
            name = screens[index]["name"]
            segments.append({
                "index": index, "screen": index + 1, "page_id": pages[index].id, "label": name,
                "kind": kinds[index], "seconds": seconds, "running": tenths[index] / 10,
                "section": f"s{number}", "section_label": label, "state": worst_state(states),
                "n_items": len(states), "n_done": closed.get(pages[index].id, 0),
                "tooltip": _tooltip(name, seconds, states, closed.get(pages[index].id, 0))})
    return {"segments": segments, "sections": sections}
