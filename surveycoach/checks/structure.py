"""Structure and length checks: intro, time promise, screeners, typing load, variety (B3 B4 B5 1.4 2.1 2.2 2.4 8.2 8.6)."""
from __future__ import annotations

import re

from surveycoach.checks.registry import (ReviewContext, blocker_ok, check, clip, finding, not_applicable, passed,
                                         result)
from surveycoach.checks.text import plural
from surveycoach.findings import CheckResult, Finding
from surveycoach.snapshot import Page, Question

SCREEN_OUT_EFFORT_SECONDS = 120
OPEN_TEXT = {"text_short", "text_long"}
REWARD_WORDS = re.compile(r"\b(points?|rewards?|earn(?:ed|ing)?|gift ?cards?|\$\d+)\b", re.I)
THANKS = re.compile(r"\bthank", re.I)
MINUTES_PHRASE = re.compile(
    r"(?:about\s+)?\d+(?:\.\d+)?\s*(?:(?:-|\u2013|to)\s*\d+(?:\.\d+)?\s*)?(?:minutes?|mins?)\b", re.I)
FORMAT_FAMILY = {
    "single_choice": "single choice", "dropdown": "single choice", "multi_choice": "multiple choice",
    "rating": "rating", "text_short": "open text", "text_long": "open text", "image_choice": "image choice",
    "ranking": "ranking", "best_worst": "ranking", "grid_single": "grid", "grid_multi": "grid", "slider": "slider",
}


def _minutes_said(minutes: float) -> str:
    return f"about {max(1, round(minutes))} minutes"


def fixed_intro(intro: str, minutes: float, *, fix_time: bool, add_reward: bool) -> str:
    """Correct estimated time only; add_reward stays for compatibility, never invented."""
    text = intro.strip()
    if fix_time:
        said = _minutes_said(minutes)
        text = MINUTES_PHRASE.sub(said, text, count=1) if MINUTES_PHRASE.search(text) else f"{text} This takes {said}."
    return text


def _promise_broken(promised: float, estimated: float) -> bool:
    return estimated > promised * 1.5 and estimated - promised > 3


def _promise_overrun(promised: float, estimated: float) -> bool:
    return estimated > promised * 1.25 and estimated - promised >= 1


def _intro_page_id(ctx: ReviewContext) -> str | None:
    pages = ctx.snapshot.pages
    return pages[0].id if pages and ctx.snapshot.page_role(pages[0]) == "intro" else None


def _question_pages(ctx: ReviewContext) -> list[Page]:
    return [p for p in ctx.snapshot.pages if p.questions]


def _real_questions(ctx: ReviewContext):
    return [q for q in ctx.snapshot.all_questions() if q.kind != "info"]


@check("B4")
def no_intro(ctx: ReviewContext) -> CheckResult:
    pages = ctx.snapshot.pages
    if pages and ctx.snapshot.page_role(pages[0]) == "intro":
        return blocker_ok("B4")
    title = ctx.snapshot.title.strip()
    known_topic = title and title.casefold() not in {"untitled", "untitled survey", "survey", "t"}
    draft = (f"We'd love your input on {title}. Thanks for sharing your thoughts!"
             if known_topic else "We'd love your input. Thanks for sharing your thoughts!")
    return result("B4", None, finding(
        "B4", "must_fix", "The survey starts with no welcome screen", "No opening welcome was recognized.",
        "Add a short welcome before the first question. This example uses the survey title when available; "
        "verify that it describes the intended purpose. Add a time promise only after a timed pilot, "
        "and reward details only when confirmed.",
        "A welcome tells members what to expect before they answer.",
        suggested_text=draft, field_location="RedJade > Welcome > Welcome text"))


@check("B5")
def broken_time_promise(ctx: ReviewContext) -> CheckResult:
    promised, estimated = ctx.promised_minutes, ctx.timing.minutes
    if not ctx.timing.calibrated or ctx.timing.path_uncertain:
        return CheckResult(criterion_id="B5", assessed=False)
    if promised is None or not _promise_broken(promised, estimated):
        return blocker_ok("B5")
    intro = ctx.snapshot.intro_text
    return result("B5", None, finding(
        "B5", "must_fix", f"Welcome promises {promised:g} min; members need about {estimated:.0f}",
        f"The intro promises {promised:g} minutes; we estimate about {estimated:g}.",
        f"Either shorten the survey to about {promised:g} minutes or update the intro to say about {estimated:.0f} minutes.",
        "A short promise and a long survey costs trust.",
        page_id=_intro_page_id(ctx), current_text=intro,
        suggested_text=fixed_intro(intro, estimated, fix_time=True, add_reward=False),
        highlight=(MINUTES_PHRASE.search(intro) or [None])[0]))


def _screen_out_pages(ctx: ReviewContext) -> list[tuple[int, Page]]:
    return [(i, p) for i, p in enumerate(ctx.snapshot.pages) if p.kind == "screen_out"]


@check("B3")
def late_screen_out(ctx: ReviewContext) -> CheckResult:
    """Thank-you wording is judged on canonical page copy; late-effort timing only when it is verified.

    A screen-out after other pages needs calibrated, certain timing to judge effort. Without it the
    check keeps its independent copy findings but cannot clear the blocker (assessed=False).
    A survey with no observed screen-out has nothing to place and keeps the existing clear.
    """
    findings, timing_unverified = [], False
    timing_verified = ctx.timing.calibrated and not ctx.timing.path_uncertain
    for index, page in _screen_out_pages(ctx):
        copy = ctx.snapshot.page_copy(page)
        timing_unverified |= index > 0 and not timing_verified
        effort = ctx.timing.pages[index - 1].cumulative_seconds if index > 0 else 0
        if timing_verified and effort > SCREEN_OUT_EFFORT_SECONDS:
            findings.append(finding(
                "B3", "must_fix", f"Members are screened out after about {effort / 60:.0f} min of effort",
                f"Members can be screened out after about {effort / 60:.0f} minutes of effort.",
                "Move the qualifying questions to the start so unqualified members find out in under 2 minutes.",
                "Members who spend minutes and then don't qualify rarely come back.",
                page_id=page.id,
                steps=["Move the questions that decide who qualifies to the start of the survey.",
                       "Aim for under 2 minutes before anyone is screened out."]))
        if not THANKS.search(copy):
            findings.append(finding(
                "B3", "must_fix", "Screen-out page has no thank-you",
                clip(copy) or "The screen-out page has no thank-you.",
                "Thank members warmly on the screen-out page, for example: Thanks for your time! "
                "This one isn't a match, but we'd love your help on the next one.",
                "Members who don't qualify still decide whether to come back.", page_id=page.id,
                current_text=page.text or None,
                suggested_text="Thanks for your time! This one isn't a match, but we'd love your help on the next one."))
    if findings or timing_unverified:
        return CheckResult(criterion_id="B3", findings=findings, assessed=not timing_unverified)
    return blocker_ok("B3")


def _intro_headline(promised: float | None, no_time: bool, wrong_time: bool) -> str:
    if no_time:
        return "Welcome doesn't say how long it takes"
    if wrong_time:
        return f"Welcome promises {promised:g} min; check the time"
    return "Welcome doesn't mention a reward"


def _intro_action(ctx: ReviewContext, intro: str, estimated: float, promised: float | None, *, time_issue: bool) -> dict:
    """Time problems paste a timed line when the route is timed, else ask for one timed run. A missing
    reward is a question, never a made-up sentence: only the study owner knows whether a reward applies."""
    if not time_issue:
        return {"you_check": "If members get a reward, is the exact reward in the welcome text?"}
    if ctx.timing.calibrated:
        return {"suggested_text": fixed_intro(intro, estimated, fix_time=True, add_reward=False)}
    check = (f"If it is not about {promised:g} minutes, fix the time in the welcome text." if promised is not None
             else "Add the real time to the welcome text.")
    return {"steps": ["Time one run-through on your phone.", check]}


@check("1.4")
def time_and_reward(ctx: ReviewContext) -> CheckResult:
    intro, promised, estimated = ctx.snapshot.intro_text, ctx.promised_minutes, ctx.timing.minutes
    no_time = promised is None
    if ctx.timing.path_uncertain:
        return result("1.4", None)
    overrun = promised is not None and _promise_overrun(promised, estimated)
    no_reward = not REWARD_WORDS.search(intro)
    fraction = ((not no_time and not overrun) + (not no_reward)) / 2
    # B5 reports a badly broken promise; here only the smaller overruns, so nothing is said twice.
    wrong_time = overrun and (not ctx.timing.calibrated or not _promise_broken(promised, estimated))
    details = []
    if no_time:
        details.append("The intro doesn't say how long the survey takes.")
    if wrong_time:
        details.append(f"The intro promises {promised:g} minutes; estimated member completion is about {estimated:g}. "
                       "Verify this estimate before changing the promise.")
    if no_reward:
        details.append("No reward terms are stated; whether a reward applies is unknown.")
    if not details:
        return result("1.4", fraction)
    return result("1.4", fraction, finding(
        "1.4", "worth_improving", _intro_headline(promised, no_time, wrong_time), " ".join(details),
        "Verify the estimated time with a timed run. If a reward applies, state its confirmed terms separately; "
        "no reward details were supplied. A time rewrite is offered only for a calibrated, verified route.",
        "Knowing how long it takes helps members decide to start." if no_time or wrong_time
        else "Members like to know up front whether a reward applies.",
        page_id=_intro_page_id(ctx), current_text=intro or None,
        highlight=(MINUTES_PHRASE.search(intro) or [None])[0] if wrong_time else None,
        **_intro_action(ctx, intro, estimated, promised, time_issue=no_time or wrong_time)))


@check("2.1")
def length_fits_type(ctx: ReviewContext) -> CheckResult:
    if ctx.timing.path_uncertain:
        return result("2.1", None)
    full, partial = ctx.rubric.length_targets_minutes[ctx.snapshot.survey_type]
    minutes, count = ctx.timing.minutes, len(_real_questions(ctx))
    if minutes <= full:
        return passed("2.1")
    fraction = 0.6 if minutes <= partial else 0.0
    return result("2.1", fraction, finding(
        "2.1", "worth_improving", f"About {minutes:g} min; surveys like this aim for {full:g} or less",
        f"Estimated member completion is {minutes:g} minutes across {count} questions, not crawl or load time. "
        f"The configured survey-type guideline is up to {full:g} minutes; it is not a measured member limit.",
        ("This is an uncalibrated estimate. " if not ctx.timing.calibrated else "This is a calibrated estimate. ") +
        "Verify it with a timed pilot before shortening the survey. If confirmed, consider removing or merging "
        "questions that don't drive a decision.",
        "Long surveys lose members before the last question.",
        steps=["Time one run-through on your phone to check the estimate.",
               "If it is right, cut or merge questions that don't drive a decision."]))


@check("2.2")
def screeners_first(ctx: ReviewContext) -> CheckResult:
    if not _screen_out_pages(ctx):
        return not_applicable("2.2")   # no screen-out was observed, so there is nothing to place
    late = []
    for index, page in _screen_out_pages(ctx):
        answered = sum(len(p.questions) for p in ctx.snapshot.pages[:index])
        if answered > 3:
            late.append(finding(
                "2.2", "worth_improving", f"Screen-out comes after {plural(answered, 'question')}",
                f"A screen-out comes after {answered} questions.",
                "Put every qualifying question in the first 3 screens.",
                "Late screening wastes the time of members who never qualified.", page_id=page.id,
                steps=["Move the screening questions to the first 3 screens."]))
    return result("2.2", 0.0 if late else 1.0, *late)


def _typing_fraction(required_count: int) -> float:
    return 1.0 if required_count <= 2 else 0.5 if required_count == 3 else 0.0


@check("2.4")
def typing_load(ctx: ReviewContext) -> CheckResult:
    """Only verified-required typing counts. Unknown requiredness is not optional, so it cannot earn a pass."""
    open_text = [q for q in ctx.snapshot.all_questions() if q.kind in OPEN_TEXT]
    required = [q for q in open_text if q.required is True]
    unknown = sum(q.required is None for q in open_text)
    fraction = _typing_fraction(len(required))
    if _typing_fraction(len(required) + unknown) != fraction:
        return CheckResult(criterion_id="2.4", assessed=False, findings=_make_optional_findings(required),
                           note=f"{plural(unknown, 'typing question')} with unknown required status could change "
                                "this result; confirm which are required.")
    return result("2.4", fraction, *_make_optional_findings(required))


def _make_optional_findings(required: list[Question]) -> list[Finding]:
    return [finding("2.4", "worth_improving", "Required typing question; make it optional", clip(q.text),
                    "Make this answer optional, or replace it with answer choices.",
                    "Typing on a phone is work, and required typing makes members quit.",
                    question_id=q.id, current_text=q.text,
                    steps=["Open this question in RedJade and make it optional.",
                           "Or swap the typing box for answer choices."])
            for q in required[2:]]


@check("8.2")
def format_variety(ctx: ReviewContext) -> CheckResult:
    questions = _real_questions(ctx)
    if not questions:
        return result("8.2", None)
    formats = {FORMAT_FAMILY[q.kind] for q in questions if q.kind in FORMAT_FAMILY}
    needed = 2 if len(questions) <= 8 else 3
    if len(formats) >= needed:
        return passed("8.2")
    fraction = 0.5 if len(questions) > 8 and len(formats) == 2 else 0.0
    return result("8.2", fraction, finding(
        "8.2", "worth_improving",
        "Every question looks the same" if len(formats) == 1 else f"Only {len(formats)} question formats; mix in more",
        f"{len(questions)} questions use {len(formats)} format(s): {', '.join(sorted(formats))}.",
        f"Mix in at least {needed} formats, such as a rating, an image choice, or a short optional comment.",
        "The same question shape again and again feels like a chore.",
        steps=["Change one or two questions to a different type, like a rating or an image choice.",
               "Or add one short optional comment box."]))


@check("8.6")
def room_to_speak(ctx: ReviewContext) -> CheckResult:
    tail = [q for p in _question_pages(ctx)[-2:] for q in p.questions]
    open_text = [q for q in tail if q.kind in OPEN_TEXT]
    if any(q.required is False for q in open_text):      # verified optional
        return passed("8.6")
    if any(q.required is None for q in open_text):       # unknown is neither optional nor required
        return CheckResult(criterion_id="8.6", assessed=False,
                           note="A comment box near the end has unknown required status, so we cannot say "
                                "whether members can skip it. Check it in RedJade.")
    existing = next((q for q in reversed(tail) if q.kind in OPEN_TEXT), None)
    if existing:
        return result("8.6", 0.0, finding(
            "8.6", "worth_improving", "Make the final comment optional", existing.text,
            "Make this existing comment question optional; keep one place for members to speak freely.",
            "Members should be able to finish without writing a comment.",
            question_id=existing.id, current_text=existing.text,
            steps=["Open this comment question in RedJade.", "Turn off Required so members can skip it."]))
    return result("8.6", 0.0, finding(
        "8.6", "worth_improving", "No optional comment box near the end", "No optional comment box near the end.",
        "Add one optional question: Anything else you'd like the product team to know?",
        "Members who have something to say feel heard when they get the chance.",
        page_id=_question_pages(ctx)[-1].id if _question_pages(ctx) else None,
        suggested_text="Anything else you'd like the product team to know? (optional)"))
