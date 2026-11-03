"""Small evidence-only checks: captured effort patterns and explicit answer behavior.

These are review prompts, not predictions of respondent behavior. Partial criterion
checks stay unchecked until the semantic judge supplies the broader assessment.
"""
from __future__ import annotations

import re
from itertools import groupby

from surveycoach.checks.registry import ReviewContext, check, finding, result
from surveycoach.findings import CheckResult

NONE = re.compile(r"^(?:none(?: of (?:these|the above))?|not applicable|neither)\s*[.!]?$", re.I)
WRITE_IN = re.compile(r"\bother\b.*\b(?:specify|describe|write|enter)\b", re.I)
PLACEHOLDER = re.compile(r"\b(?:insert (?:question|answer|text) here|lorem ipsum)\b|^\s*(?:TODO|TBD)\s*[:.!]", re.I)


@check("4.1")
def exclusive_answers(ctx: ReviewContext) -> CheckResult:
    findings = []
    for q in ctx.snapshot.all_questions():
        if q.kind != "multi_choice":
            continue
        for option in q.options:
            if option.is_exclusive is False and NONE.fullmatch(option.label.strip()):
                findings.append(finding(
                    "4.1", "worth_improving", "None answer can be selected with other answers", option.label,
                    "Make this answer exclusive so selecting it clears the other selections.",
                    "Conflicting selections would be hard to interpret.", question_id=q.id, element_id=option.id))
    return result("4.1", None, *findings)


@check("4.3")
def promised_write_in(ctx: ReviewContext) -> CheckResult:
    findings = []
    for q in ctx.snapshot.all_questions():
        for option in q.options:
            if option.is_other_with_text is False and WRITE_IN.search(option.label):
                findings.append(finding(
                    "4.3", "worth_improving", "Other asks for details but has no text field", option.label,
                    "Enable a text field for this answer, or remove the request to specify.",
                    "Members cannot supply the details this answer asks for.", question_id=q.id, element_id=option.id))
    return result("4.3", None, *findings)


@check("B2")
def unfinished_content(ctx: ReviewContext) -> CheckResult:
    findings = []
    for page in ctx.snapshot.pages:
        items = [(None, ctx.snapshot.page_copy(page))]
        items += [(q.id, text) for q in page.questions for text in (q.text, *[o.label for o in q.options])]
        for qid, text in items:
            if PLACEHOLDER.search(text):
                findings.append(finding(
                    "B2", "must_fix", "Unfinished placeholder text is visible", text,
                    "Replace the placeholder with the final question or answer before launch.",
                    "Members cannot answer unfinished survey content reliably.", page_id=page.id, question_id=qid))
    # No placeholder found is not proof that every member has a valid answer (the wider B2 judgment).
    return CheckResult(criterion_id="B2", assessed=False, findings=findings)


def _pattern(q):
    if q.conditional or q.kind == "info":
        return None
    if q.kind in {"text_short", "text_long"}:
        return ("typing",)
    if q.scale:
        s = q.scale
        return ("scale", s.points, s.low_label, s.high_label, tuple(s.labels))
    return None


@check("8.5")
def effort_patterns(ctx: ReviewContext) -> CheckResult:
    findings = []
    questions = [q for q in ctx.snapshot.all_questions() if q.kind != "info"]
    for pattern, group in groupby(questions, key=_pattern):
        run = list(group)
        if pattern is None:
            continue
        minimum = 3 if pattern[0] == "typing" else 5
        if len(run) < minimum:
            continue
        label = "typing questions" if pattern[0] == "typing" else "questions with the same scale"
        findings.append(finding(
            "8.5", "worth_improving", f"{len(run)} consecutive {label}", run[0].text,
            "Review this run for redundant items. Keep necessary tracker scales consistent; "
            "make nonessential comments optional rather than adding arbitrary formats.",
            "This captured run asks for repeated effort; check whether every item supports a research decision.",
            question_id=run[0].id))
    grids = [q for q in questions if q.kind in {"grid_single", "grid_multi"} and not q.conditional]
    rows = sum(len(q.rows) for q in grids)
    if rows >= 20:
        findings.append(finding(
            "8.5", "worth_improving", f"{rows} grid rows across {len(grids)} questions", grids[0].text,
            "Review the total grid workload and remove attributes that do not support a research decision.",
            "The captured grids require repeated row-by-row judgments; actual answer quality is not measured.",
            question_id=grids[0].id))
    return result("8.5", None, *findings)
