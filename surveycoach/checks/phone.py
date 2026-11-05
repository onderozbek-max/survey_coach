"""Built for the phone: one screen, tappable answers, small grids, thumb-friendly, stays put (6.1 to 6.5)."""
from __future__ import annotations

import re

from surveycoach.checks.answers import standard_scale
from surveycoach.checks.images import all_media
from surveycoach.checks.registry import (Problem, ReviewContext, check, clip, problem_finding, result,
                                         share_fraction)
from surveycoach.checks.text import plural, swap_word
from surveycoach.findings import CheckResult, Finding
from surveycoach.snapshot import Question

MAX_QUESTION_WORDS = 25
MAX_LABEL_CHARS = 60
MAX_CHOICES = 8   # configured layout-review cue, not a required maximum or research optimum
MAX_DROPDOWN_BUTTONS = 7   # lists this short should be buttons, not a dropdown
MAX_GRID_ROWS = 5
MAX_GRID_COLUMNS = 5
MAX_SCALE_POINTS = 7
DESKTOP_WORDS = re.compile(r"\b(click(?:ing)?|double-click|right-click|hover|drag(?:ging)?|on the (?:left|right)|"
                           r"(?:left|right)[- ]hand side)\b", re.I)
TAP_FOR = {"click": "tap", "clicking": "tapping", "double-click": "double-tap", "right-click": "press and hold"}
CHOICE_KINDS = {"single_choice", "multi_choice", "dropdown", "image_choice"}
GRID_KINDS = {"grid_single", "grid_multi"}
TRUNCATED = re.compile(r"(\.\.\.|\u2026)\s*$")


def _questions(ctx: ReviewContext) -> list[Question]:
    return [q for q in ctx.snapshot.all_questions() if q.kind != "info"]


def _on_question(criterion: str, q: Question, problem: Problem, impact: str) -> Finding:
    return problem_finding(criterion, problem, impact, question_id=q.id)


def _question_fit_problems(q: Question) -> list[Problem]:
    found = []
    words = len(q.text.split())
    if words > MAX_QUESTION_WORDS:
        found.append(Problem(f"Question runs {words} words; aim for {MAX_QUESTION_WORDS}", f"{words} words: {clip(q.text, 90)}",
                             f"Shorten the question to about {MAX_QUESTION_WORDS} words or fewer.", current=q.text))
    if q.options_below_fold or q.fits_one_screen is False:
        below = (f"{plural(q.options_below_fold, 'answer')} below the fold on a phone"
                 if q.options_below_fold else "Question doesn't fit one phone screen")
        found.append(Problem(below, below + ".",
                             "Trim or group the answers so the question and its first answers show without scrolling."))
    return found


@check("6.1")
def fits_one_screen(ctx: ReviewContext) -> CheckResult:
    """Judged per screen: a screen fails if it holds several questions or any question doesn't fit."""
    screens = [p for p in ctx.snapshot.pages if any(q.kind != "info" for q in p.questions)]
    findings, failing = [], 0
    for page in screens:
        problems = [_on_question("6.1", q, pr, "Long questions push the answers off the first screen.")
                    for q in page.questions if q.kind != "info" for pr in _question_fit_problems(q)]
        if len([q for q in page.questions if not q.conditional]) > 1:
            crowd = f"{plural(len(page.questions), 'question')} on one screen"
            problems.append(problem_finding("6.1", Problem(crowd, crowd + ".", "Show one question per screen."),
                                            "Crowded screens need a lot of scrolling on a phone.", page_id=page.id))
        failing += bool(problems)
        findings += problems
    return result("6.1", share_fraction(failing, len(screens)), *findings)


def _choice_layout_advice(q: Question) -> str:
    labels = [o.label for o in q.options if o.label.strip()]
    # Shared final words can suggest a heading, not a merged answer. Avoid sorting or
    # inferring a taxonomy from unrelated labels (or numeric/ordered frequency scales).
    pair = None
    for index, left in enumerate(labels):
        left_words = left.split()
        if len(left_words) < 2 or any(char.isdigit() for char in left):
            continue
        for right in labels[index + 1:]:
            right_words = right.split()
            if (len(right_words) >= 2 and left.casefold() != right.casefold()
                    and left_words[-1].casefold() == right_words[-1].casefold()
                    and not any(char.isdigit() for char in right)):
                pair = (left, right, left_words[-1])
                break
        if pair:
            break
    threshold = (
        f"The configured {MAX_CHOICES}-choice threshold is a phone-layout review cue, not a research optimum "
        "or a requirement to remove answers. Preview this question on a narrow phone. "
    )
    if pair:
        left, right, shared = pair
        guidance = (
            f'If the study owner confirms a useful grouping, try a "{shared}" heading above '
            f'"{left}" and "{right}"; keep both as distinct selectable answers. '
            "Use visual headings only if supported without changing how members answer. "
        )
    else:
        examples = " and ".join(f'"{label}"' for label in labels[:2])
        guidance = (
            f"Keep distinct choices such as {examples}. Ask the study owner whether any choices share "
            "a useful category; if so, add visual headings without merging the selectable answers. "
            "If no grouping is meaningful, keep the full list and verify that every answer is reachable. "
        )
    return threshold + guidance + (
        "Preserve any intended order, randomization, exclusive answers and routing. "
        "Do not delete distinct options merely to meet the threshold; verify the layout and selection behavior on a phone."
    )


@check("6.2")
def tappable_answers(ctx: ReviewContext) -> CheckResult:
    findings, failing, total = [], 0, 0
    for q in _questions(ctx):
        if q.kind not in CHOICE_KINDS or not q.options:
            continue
        total += 1
        problems = []
        long_labels = [o.label for o in q.options if len(o.label) > MAX_LABEL_CHARS]
        if long_labels:
            problems.append(Problem("Answer text is too long to tap comfortably", clip(long_labels[0], 90),
                                    f"Keep each answer to about {MAX_LABEL_CHARS} characters (2 lines).",
                                    current=long_labels[0], highlight=long_labels[0]))
        if len(q.options) > MAX_CHOICES and not standard_scale(q):
            problems.append(Problem(f"{len(q.options)} answer choices; review the phone layout",
                                    f"{len(q.options)} answer choices.", _choice_layout_advice(q)))
        if q.kind == "dropdown" and len(q.options) <= MAX_DROPDOWN_BUTTONS:
            problems.append(Problem(f"Dropdown with only {len(q.options)} choices", f"A dropdown with only {len(q.options)} choices.",
                                    "Use buttons instead; they take one tap, not two."))
        failing += bool(problems)
        findings += [_on_question("6.2", q, pr, "Long or crowded answers are hard to read and tap on a phone.") for pr in problems]
    return result("6.2", share_fraction(failing, total), *findings)


@check("6.3")
def small_grids(ctx: ReviewContext) -> CheckResult:
    findings, failing, total = [], 0, 0
    for q in _questions(ctx):
        columns = q.scale.points if q.scale else len(q.options)
        problems = []
        if q.kind in GRID_KINDS:
            total += 1
            if len(q.rows) > MAX_GRID_ROWS:
                problems.append(Problem(f"Grid has {len(q.rows)} rows; split it", f"A grid with {len(q.rows)} rows.",
                                        f"Split it into separate questions of {MAX_GRID_ROWS} rows or fewer."))
            if columns > MAX_GRID_COLUMNS:
                problems.append(Problem(f"Grid has {columns} columns; use {MAX_GRID_COLUMNS}", f"A grid with {columns} columns.",
                                        f"Use {MAX_GRID_COLUMNS} columns or fewer."))
        elif q.scale and q.kind in {"rating", "slider"}:
            total += 1
            if q.scale.points > MAX_SCALE_POINTS and not standard_scale(q):
                problems.append(Problem(f"{q.scale.points}-point scale is hard to tap", f"A {q.scale.points}-point scale.",
                                        f"Use {MAX_SCALE_POINTS} points or fewer; a 0 to 10 scale is hard to tap."))
        failing += bool(problems)
        findings += [_on_question("6.3", q, pr, "Wide grids and long scales force sideways scrolling and mis-taps.") for pr in problems]
    return result("6.3", share_fraction(failing, total), *findings)


def _desktop_word(q: Question) -> tuple[str, str] | None:
    for text in (q.text, q.help_text, *[o.label for o in q.options]):
        if match := DESKTOP_WORDS.search(text):
            return text, match.group(0)
    return None


@check("6.4")
def thumb_friendly(ctx: ReviewContext) -> CheckResult:
    findings, failing = [], 0
    for q in _questions(ctx):
        problems = []
        if hit := _desktop_word(q):
            text, word = hit
            replacement = TAP_FOR.get(word.lower())
            problems.append(Problem(f'"{word}" is a desktop word', f'"{word}" is a desktop word.',
                                    'Say "tap" and avoid "left" or "right".', current=text, highlight=word,
                                    suggested=swap_word(text, word, replacement) if replacement else None))
        failing += bool(problems)
        findings += [_on_question("6.4", q, pr, "Members on a phone can't click, hover, or drag.") for pr in problems]
    return result("6.4", share_fraction(failing, len(_questions(ctx))), *findings)


@check("6.5")
def stays_put(ctx: ReviewContext) -> CheckResult:
    findings, failing = [], 0
    for page in ctx.snapshot.pages:
        if page.links_out:
            failing += 1
            link = Problem("Link leads away from the survey", f"Links away from the survey: {', '.join(page.links_out[:2])}",
                           "Remove the link, or open it in a way that keeps the member's progress.")
            findings.append(problem_finding("6.5", link, "Leaving the survey can lose all progress.", page_id=page.id))
    for q in _questions(ctx):
        if TRUNCATED.search(q.text):
            failing += 1
            cut = Problem("Question text is cut off", q.text[-60:], "Show the full question text.", current=q.text)
            findings.append(_on_question("6.5", q, cut, "Cut-off text leaves members guessing what is being asked."))
    # A picture that did not load is missing content. The must-fix (B7) already reports it, so it only costs credit here.
    media = all_media(ctx)
    failing += sum(not ref.media.loaded for ref in media)
    total = len(ctx.snapshot.pages) + len(_questions(ctx)) + len(media)
    return result("6.5", share_fraction(failing, total), *findings)
