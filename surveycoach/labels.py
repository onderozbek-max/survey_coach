"""The one naming scheme for screens and questions. Views never count on their own."""
from __future__ import annotations

import re

from surveycoach.snapshot import SurveySnapshot

_ROLE_NAMES = {"intro": "Welcome", "thank_you": "Thank you", "screen_out": "Screen-out", "end": "Last screen"}


def _topic(text: str, words: int = 5) -> str:
    parts = (text or "").split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def screen_labels(snapshot: SurveySnapshot) -> list[dict]:
    labels, number = [], 0
    for index, page in enumerate(snapshot.pages):
        questions = []
        for question in page.questions:
            if question.kind == "info":
                continue
            number += 1
            questions.append({"id": question.id, "number": number, "label": question.label or f"Q{number}"})
        if len(questions) == 1:
            name = questions[0]["label"]
        elif questions:
            name = f'{questions[0]["label"]}–{questions[-1]["label"]}'
        else:
            name = _ROLE_NAMES.get(snapshot.page_role(page), "Message")
        first = next((q.text for q in page.questions if q.kind != "info"), "")
        labels.append({"page_id": page.id, "screen": index + 1, "name": name,
                       "topic": _topic(first or snapshot.page_copy(page)), "questions": questions})
    return labels


def join_names(names) -> str:
    """'Q4', 'Q4 and Q6', 'Q4, Q6 and Q8'."""
    names = list(dict.fromkeys(names))
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


QUESTION_LABEL = re.compile(r"\bQ\d+\b")


def group_label(findings: list[dict], labels: list[dict]) -> str:
    """Where a grouped card applies, e.g. 'Q4, Q6 and Q8 · Screens 5, 7 and 9'. One finding keeps its own label."""
    spots = [finding_label(f, labels) for f in findings]
    if len(set(spots)) == 1 or "Whole survey" in spots:
        return spots[0]
    names, numbers = zip(*(spot.split(" · Screen ") for spot in spots))
    return f"{join_names(names)} · Screens {join_names(numbers)}"


def finding_label(finding: dict, labels: list[dict]) -> str:
    for screen in labels:
        for question in screen["questions"]:
            if question["id"] == finding.get("question_id"):
                return f'{question["label"]} · Screen {screen["screen"]}'
        if not finding.get("question_id") and finding.get("page_id") == screen["page_id"]:
            return f'{screen["name"]} · Screen {screen["screen"]}'
    return "Whole survey"
