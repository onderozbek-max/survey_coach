"""Interpret only observed DOM wording; never invent missing questions or labels."""
import hashlib
import json
import re
from collections import Counter
from collections.abc import Sequence

from surveycoach.snapshot import Media, Option, Page, Question


def stable_id(prefix: str, *parts) -> str:
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def fingerprint(observation: dict) -> str:
    if observation.get("state_key"):
        return stable_id("page", observation["state_key"])
    return stable_id("page", observation.get("source_page_id"), observation["text"], [
        [group["prompt"], group["kind"], [item["label"] for item in group["items"]]]
        for group in observation["groups"]
    ])


# RedJade shows its own "Optional" label after the prompt, on its own line or after sentence punctuation.
_OPTIONAL_LABEL = re.compile(r"(?:\n[ \t]*|(?<=[?.!:])[ \t]+)\(?optional\)?[ \t]*$", re.I)


def _requiredness(group: dict) -> tuple[str, bool | None]:
    """Prompt wording without the vendor label, and what the page proves about requiredness.

    The HTML required flag proves required. A visible Optional label proves optional.
    No flag is NOT proof of optional, and conflicting evidence stays unknown.
    """
    prompt = group["prompt"]
    label = _OPTIONAL_LABEL.search(prompt)
    if label:
        prompt = prompt[:label.start()].rstrip()
    optional = bool(label) or group.get("optional_label") is True
    if optional:
        return prompt, None if group["required"] else False
    return prompt, True if group["required"] else None


def _row_key(item: dict):
    """Grid row identity: the DOM row when observed, else the visible row text."""
    index = item.get("row_index", -1)
    return index if index >= 0 else item["row"]


def _row_labels(items: list[dict]) -> list[str]:
    """One label per distinct row; equal row text in different DOM rows stays distinct."""
    rows = {}
    for item in items:
        if item["row"]:
            rows.setdefault(_row_key(item), item["row"])
    return list(rows.values())


def _answer_labels(kind: str, items: list[dict]) -> list[str]:
    """Every native choice is its own control, even when labels repeat."""
    if kind == "dropdown":
        return [o["label"] for o in items[0]["options"]]
    if kind in {"grid_single", "grid_multi"}:
        # Each row repeats the same columns: merge by column identity, never by label text.
        seen, columns = Counter(), {}
        for item in items:
            row = _row_key(item)
            column = item.get("column", -1)
            columns.setdefault(column if column >= 0 else seen[row], item["label"])
            seen[row] += 1
        return [columns[key] for key in sorted(columns)]
    if kind in {"single_choice", "multi_choice"}:
        return [item["label"] for item in items]
    return []


def extract_page(observation: dict, position: int, *, existing_pages: Sequence[Page] = ()) -> Page:
    """Preserve source IDs on first use; allocate deterministic IDs for revisits.

    Rendered identity (fingerprint) is separate from capture-instance identity.
    Raw observations retain source IDs even when an instance needs a new ID.
    """
    page_ids = {page.id for page in existing_pages}
    question_ids = {question.id for page in existing_pages for question in page.questions}

    def allocate(prefix, original, occupied):
        candidate, occurrence = original, 1
        while candidate in occupied:
            occurrence += 1
            candidate = stable_id(prefix, original, "occurrence", occurrence)
        occupied.add(candidate)
        return candidate

    questions = []
    page_id = allocate("page", observation.get("source_page_id") or fingerprint(observation), page_ids)
    for index, group in enumerate(observation["groups"]):
        kind = group["kind"]
        items = group["items"]
        qid = allocate("q", group.get("source_id") or stable_id("q", page_id, index, group["prompt"]),
                       question_ids)
        options = [Option(id=stable_id("o", qid, number, label), label=label)
                   for number, label in enumerate(_answer_labels(kind, items))]
        prompt, required = _requiredness(group)
        questions.append(Question(
            id=qid, text=prompt, kind=kind, required=required, options=options,
            rows=_row_labels(items),
        ))
    kind = "screen_out" if observation["screenout"] else "question" if questions else "info"
    return Page(id=page_id, position=position, kind=kind, questions=questions,
                text=observation["text"], media=[Media(**item) for item in observation["media"]])


def answer_groups(page, observation: dict) -> None:
    """First usable option per native group/row, and clearly tagged synthetic text."""
    for group in observation["groups"]:
        selected = set()
        for item in group["items"]:
            if item["disabled"]:
                continue
            locator = page.locator(f'[data-surveycoach-id="{item["id"]}"]')
            kind = group["kind"]
            if kind in {"single_choice", "multi_choice", "grid_single", "grid_multi"}:
                key = item["row"] or item["name"] or "group"
                if key in selected:
                    continue
                if not item["checked"]:
                    if item["type"] in {"radio", "checkbox"} and locator.evaluate("e => e.tagName === 'INPUT'"):
                        locator.check()
                    else:
                        locator.click()
                selected.add(key)
            elif kind in {"text_short", "text_long"}:
                locator.fill("SurveyCoach test")
            elif kind == "numeric":
                low, high = float(item["min"] or 1), float(item["max"] or item["min"] or 10)
                locator.fill(str(int((low + high) // 2)))
            elif kind == "dropdown":
                usable = [o for o in item["options"] if o["value"] and not o["disabled"]]
                if not usable:
                    raise ValueError("No usable dropdown option")
                locator.select_option(value=usable[0]["value"])
