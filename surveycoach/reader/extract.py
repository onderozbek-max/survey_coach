"""Interpret only observed DOM wording; never invent missing questions or labels."""
import hashlib
import json
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
        options = []
        if kind == "dropdown":
            labels = [o["label"] for o in items[0]["options"]]
        elif kind in {"single_choice", "multi_choice", "grid_single", "grid_multi"}:
            labels = list(dict.fromkeys(item["label"] for item in items))
        else:
            labels = []
        for number, label in enumerate(labels):
            options.append(Option(id=stable_id("o", qid, number, label), label=label))
        questions.append(Question(
            id=qid, text=group["prompt"], kind=kind, required=group["required"], options=options,
            rows=list(dict.fromkeys(item["row"] for item in items if item["row"])),
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
