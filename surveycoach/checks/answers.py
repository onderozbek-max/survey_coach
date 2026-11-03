"""Answer-quality checks: overlapping ranges, honest scales, agree/disagree walls (4.2 4.4 5.4)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from surveycoach.checks.registry import ReviewContext, check, clip, finding, passed, result
from surveycoach.findings import CheckResult
from surveycoach.snapshot import Question

EPS = 1e-9
NUM = r"(\d+(?:\.\d+)?)"
BETWEEN = re.compile(rf"{NUM}\s*(?:-|\u2013|to)\s*{NUM}", re.I)
BELOW = re.compile(rf"\b(?:under|less than|fewer than|below)\s*{NUM}", re.I)
ABOVE_EXCL = re.compile(rf"\b(?:over|more than|above|greater than)\s*{NUM}", re.I)
AT_LEAST = re.compile(rf"(?:\bat least\s*{NUM}|{NUM}\s*(?:\+|or more|or older|and over|and above))", re.I)
AT_MOST = re.compile(rf"{NUM}\s*(?:or less|or fewer|or younger|and under|and below)", re.I)
CHOICE_KINDS = {"single_choice", "multi_choice", "dropdown"}


@dataclass(frozen=True)
class Interval:
    label: str
    lo: float
    hi: float

    def overlaps(self, other: "Interval") -> bool:
        return self.lo <= other.hi and other.lo <= self.hi


def parse_interval(label: str) -> Interval | None:
    """Numeric range hidden in an answer label, with open ends. None when the label isn't numeric."""
    inf = float("inf")
    if m := BETWEEN.search(label):
        return Interval(label, float(m.group(1)), float(m.group(2)))
    if m := BELOW.search(label):
        return Interval(label, -inf, float(m.group(1)) - EPS)
    if m := ABOVE_EXCL.search(label):
        return Interval(label, float(m.group(1)) + EPS, inf)
    if m := AT_MOST.search(label):
        return Interval(label, -inf, float(m.group(1)))
    if m := AT_LEAST.search(label):
        return Interval(label, float(m.group(1) or m.group(2)), inf)
    return None


def shorten_to_clear(earlier: str, later: str) -> str | None:
    """The earlier range label with its top number lowered to stop just before the later range starts."""
    a, b = BETWEEN.search(earlier), BETWEEN.search(later)
    if not (a and b) or float(b.group(1)) != int(float(b.group(1))):
        return None
    new_top = int(float(b.group(1))) - 1
    if new_top < float(a.group(1)):
        return None
    return earlier[:a.start(2)] + str(new_top) + earlier[a.end(2):]


@check("4.2")
def no_overlap(ctx: ReviewContext) -> CheckResult:
    findings = []
    for q in ctx.snapshot.all_questions():
        if q.kind not in CHOICE_KINDS:
            continue
        intervals = [i for o in q.options if (i := parse_interval(o.label))]
        for a_index, a in enumerate(intervals):
            for b in intervals[a_index + 1:]:
                if a.overlaps(b):
                    findings.append(finding(
                        "4.2", "worth_improving", f"Answer ranges overlap: {a.label}, {b.label}",
                        f'"{a.label}" and "{b.label}" overlap.',
                        "Make the ranges share no numbers, for example 1 to 4 and 5 to 10.",
                        "A member at the shared number can't tell which answer is theirs.", question_id=q.id,
                        current_text=a.label, suggested_text=shorten_to_clear(a.label, b.label), highlight=a.label))
    return result("4.2", 0.0 if findings else 1.0, *findings[:3])


POSITIVE = re.compile(r"\b(like|satisfied|agree|good|great|excellent|likely|easy|happy|love|helpful|better)\w*", re.I)
NEGATIVE = re.compile(r"\b(dislike|dissatisfied|disagree|poor|bad|terrible|unlikely|difficult|hard|unhappy|hate|unhelpful|worse)\w*", re.I)


NEGATION = re.compile(r"\s*(not|never|no|none)\b", re.I)


def polarity(label: str | None) -> int:
    """+1 positive, -1 negative, 0 neutral or unknown. Negative words win ('dislike' contains 'like')."""
    if not label:
        return 0
    if NEGATION.match(label) or NEGATIVE.search(label):
        return -1
    return 1 if POSITIVE.search(label) else 0


OPPOSITES = (
    (re.compile(r"^not at all (\w+)$", re.I), r"Extremely \1"),
    (re.compile(r"^strongly disagree$", re.I), "Strongly agree"),
    (re.compile(r"^very (?:dis|un)satisfied$", re.I), "Very satisfied"),
    (re.compile(r"^very unlikely$", re.I), "Very likely"),
    (re.compile(r"^very poor$", re.I), "Very good"),
)


def opposite_label(label: str) -> str | None:
    for pattern, replacement in OPPOSITES:
        if pattern.match(label.strip()):
            return pattern.sub(replacement, label.strip())
    return None


@dataclass(frozen=True)
class ScaleProblem:
    headline: str
    fix: str
    current: str | None = None
    suggested: str | None = None


def standard_scale(q: Question) -> bool:
    """Recognize methods from wording and anchors, never from point count alone."""
    labels = [o.label for o in q.options]
    s = q.scale
    if s:
        labels += [s.low_label or "", s.high_label or "", *s.labels]
    text = " ".join(labels).lower()
    points = s.points if s else len(q.options)
    numeric_nps = [o.label.strip() for o in q.options] == [str(i) for i in range(11)]
    nps = points == 11 and "recommend" in q.text.lower() and (
        numeric_nps or ("not at all likely" in text and ("extremely likely" in text or "very likely" in text)))
    hedonic = points == 9 and "dislike extremely" in text and "like extremely" in text
    jar = points in {3, 5} and "just about right" in text and "too" in text
    quality = points == 5 and [label.strip().lower() for label in (s.labels if s else labels)] in (
        ["excellent", "very good", "good", "fair", "poor"], ["poor", "fair", "good", "very good", "excellent"])
    return nps or hedonic or jar or quality


def _scale_problems(q: Question) -> list[ScaleProblem]:
    s = q.scale
    problems = []
    if s is None:
        return problems
    if not (s.low_label and s.high_label):
        missing = "no labels on its ends" if not (s.low_label or s.high_label) else "no label on one end"
        end_text = f"{s.low_label or '(no label)'} ... {s.high_label or '(no label)'}"
        added = opposite_label(s.low_label) if s.low_label and not s.high_label else None
        problems.append(ScaleProblem(
            f"Scale has {missing}",
            "Both ends of the scale should be labeled so every member reads it the same way.",
            end_text, f"{s.low_label} ... {added}" if added else None))
    if len(s.labels) >= 3 and not standard_scale(q):
        signs = [polarity(label) for label in s.labels]
        if abs(signs.count(1) - signs.count(-1)) > 1:
            problems.append(ScaleProblem("Scale is lopsided",
                                         "Keep the scale balanced: as many positive answers as negative ones.",
                                         " / ".join(s.labels)))
    return problems


def _orientation(q: Question) -> int:
    s = q.scale
    return polarity(s.low_label) if s and s.low_label else 0


@check("4.4")
def honest_scales(ctx: ReviewContext) -> CheckResult:
    scaled = [q for q in ctx.snapshot.all_questions() if q.scale is not None]
    findings = []
    for q in scaled:
        for problem in _scale_problems(q):
            findings.append(finding("4.4", "worth_improving", problem.headline, clip(q.text), problem.fix,
                                    "Unlabeled or lopsided scales push members toward certain answers.",
                                    question_id=q.id, current_text=problem.current, suggested_text=problem.suggested))
    directions = {o for q in scaled if (o := _orientation(q))}
    if len(directions) > 1:
        findings.append(finding(
            "4.4", "worth_improving", "Scales run in opposite directions",
            "Some scales run from positive to negative, others the other way round.",
            "Use the same direction throughout, so the highest number always means best (the direction rule).",
            "Members on autopilot tap the wrong end when the direction flips."))
    if not scaled:
        return result("4.4", 1.0)
    problem_kinds = len({f.explanation for f in findings})
    return result("4.4", max(0.0, 1 - 0.5 * min(problem_kinds, 2)), *findings[:4])


AGREE_WORD = re.compile(r"\bagree\b|\bdisagree\b", re.I)


def is_agree_scale(q: Question) -> bool:
    labels = [o.label for o in q.options]
    if q.scale:
        labels += [q.scale.low_label or "", q.scale.high_label or "", *q.scale.labels]
    return q.kind in {"single_choice", "rating", "grid_single"} and any(AGREE_WORD.search(l) for l in labels)


@check("5.4")
def agree_wall(ctx: ReviewContext) -> CheckResult:
    longest, longest_start, run_start, current = 0, None, None, 0
    for q in ctx.snapshot.all_questions():
        if is_agree_scale(q):
            current += 1
            run_start = run_start or q.id
            if current > longest:
                longest, longest_start = current, run_start
        else:
            current, run_start = 0, None
    if longest <= 3:
        return passed("5.4")
    return result("5.4", 0.0, finding(
        "5.4", "worth_improving", f"{longest} agree/disagree questions in a row", f"{longest} agree/disagree questions in a row.",
        'Ask direct questions instead, for example "How easy was the package to open?"',
        "Long runs of agree/disagree make members default to agreeing.", question_id=longest_start))
