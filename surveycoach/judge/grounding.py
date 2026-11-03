"""Grounding: an AI answer only counts for as much as the survey itself can back up.

Pure functions. Whatever the model says, a finding survives only if its quote is really in the survey at the place
it points to, and points are never lost without a finding a researcher can read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from surveycoach.checks.registry import clip, result
from surveycoach.findings import CheckResult, Finding, RewriteOption
from surveycoach.judge.batches import Batch
from surveycoach.judge.schemas import AiFinding, BatchOutput
from surveycoach.recommendations import guard_recommendation
from surveycoach.rubric import Rubric
from surveycoach.snapshot import Page, Question, SurveySnapshot

CREDIT_CAP_WITH_FINDING = 0.75   # one real problem can never score as full marks
MAX_OPTIONS = 3
TITLE_CRITERIA = {"1.1"}               # the survey title belongs to the survey, not to any page, so only these may quote it
MAX_FINDINGS_PER_CRITERION = 3   # a pattern is one finding on its worst example, not a wall of cards


@dataclass
class Grounded:
    results: dict[str, CheckResult] = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)      # what we refused to believe, and why


def norm(text: str) -> str:
    straightened = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", straightened).strip().lower()


_PROMPT_LABEL = re.compile(r"^\s*(option|row|help|scale label|text|intro)\s*:\s*", re.IGNORECASE)


def quote_is_real(evidence: str, located: str) -> bool:
    """Every line of the quote must be verbatim survey text. The model sometimes copies our `option:` labels along
    with the words, so those labels (and only those) are ignored; an invented line still sinks the whole quote."""
    lines = [norm(_PROMPT_LABEL.sub("", line)) for line in evidence.splitlines() if line.strip()]
    lines = [line for line in lines if line]
    haystack = norm(located)
    return bool(lines) and all(line in haystack for line in lines)


def _question_text(q: Question) -> str:
    parts = [q.text, q.help_text, *[o.label for o in q.options], *q.rows]
    if q.scale:
        parts += [q.scale.low_label or "", q.scale.high_label or "", *q.scale.labels]
    return " ".join(p for p in parts if p)


def _page_text(page: Page) -> str:
    return " ".join([page.intro_text, page.text, *[_question_text(q) for q in page.questions]])


def locate(snapshot: SurveySnapshot, page_id: str | None, question_id: str | None) -> tuple[str, str | None] | None:
    """The text a finding may quote from, and the page it lives on. None when the place does not exist."""
    if question_id:
        for page in snapshot.pages:
            for q in page.questions:
                if q.id == question_id and page_id in (None, page.id):
                    return _question_text(q), page.id
        return None
    if page_id:
        page = next((p for p in snapshot.pages if p.id == page_id), None)
        return (_page_text(page), page.id) if page else None
    return " ".join([snapshot.title, *[_page_text(p) for p in snapshot.pages]]), None


def _rewrite(raw: AiFinding, located: str) -> tuple[str | None, str | None, list[RewriteOption], str | None]:
    """Keep a before/after only when the 'before' really is in the survey; drop no-ops; cap the options."""
    current = raw.current_text if raw.current_text and norm(raw.current_text) in norm(located) else None
    if raw.current_text and current is None:
        return None, None, [], None                       # an invented 'before' poisons the 'after' too
    options = [o for o in raw.options if o.text.strip()][:MAX_OPTIONS]
    options = [o for o in options if not (current and norm(o.text) == norm(current))]
    suggested = raw.suggested_text
    if suggested and current and norm(suggested) == norm(current):
        suggested = None
    suggested = suggested or (options[0].text if options else None)
    haystack = norm(f"{current or ''} {raw.evidence}")
    highlight = raw.highlight if raw.highlight and norm(raw.highlight) in haystack else None
    return current, suggested, options, highlight


def _ground_one(raw: AiFinding, batch: Batch, raised: set[str], snapshot: SurveySnapshot) -> tuple[Finding | None, str]:
    cid = raw.criterion_id
    if cid not in (*batch.criteria, *batch.blockers):
        return None, f"{cid}: not part of this check"
    if cid in batch.blockers and cid not in raised:
        return None, f"{cid}: a finding for a blocker the judge did not raise"
    placed = locate(snapshot, raw.page_id, raw.question_id)
    if placed is None:
        return None, f"{cid}: points at a screen or question that does not exist"
    located, page_id = placed
    if cid in TITLE_CRITERIA:
        located = f"{located} {snapshot.title}"
    if not quote_is_real(raw.evidence, located):
        return None, f"{cid}: the quote was not found in the survey: {clip(raw.evidence, 60)}"
    current, suggested, options, highlight = _rewrite(raw, located)
    # Computed here, never taken from the model: a multi-line rewrite is a bundle (question plus answer choices), which
    # must not be swapped into one text element of the phone preview. Copy it, do not draw it.
    structural = any("\n" in t for t in (suggested, *[o.text for o in options]) if t)
    finding = Finding(
        criterion_id=cid, severity="must_fix" if cid in batch.blockers else "worth_improving", headline=raw.headline,
        evidence=raw.evidence, explanation=raw.explanation, member_impact=raw.member_impact, page_id=page_id,
        question_id=raw.question_id, current_text=current, suggested_text=suggested, highlight=highlight,
        options=options, structural=structural, source="ai")
    return Finding.model_validate(guard_recommendation(finding.model_dump())), ""


def ground(output: BatchOutput, batch: Batch, snapshot: SurveySnapshot, rubric: Rubric) -> Grounded:
    grounded = Grounded()
    raised = {b.blocker_id for b in output.blockers if b.triggered and b.blocker_id in batch.blockers}
    kept: dict[str, list[Finding]] = {cid: [] for cid in (*batch.criteria, *batch.blockers)}
    for raw in output.findings:
        finding, why = _ground_one(raw, batch, raised, snapshot)
        if finding is None:
            grounded.dropped.append(why)
        elif len(kept[raw.criterion_id]) >= MAX_FINDINGS_PER_CRITERION:
            grounded.dropped.append(f"{raw.criterion_id}: too many findings, kept the first {MAX_FINDINGS_PER_CRITERION}")
        else:
            kept[raw.criterion_id].append(finding)
    for verdict in output.verdicts:
        cid = verdict.criterion_id
        if cid not in batch.criteria:
            continue
        if kept[cid]:
            fraction = min(verdict.fraction, CREDIT_CAP_WITH_FINDING)
        else:
            fraction = 1.0
            if verdict.fraction < 1.0:
                grounded.dropped.append(f"{cid}: the judge took points off but gave no quotable reason, so full credit stands")
        grounded.results[cid] = result(cid, fraction, *kept[cid])
    for call in output.blockers:
        bid = call.blocker_id
        if bid not in batch.blockers:
            continue
        if call.triggered and not kept[bid]:
            grounded.dropped.append(f"{bid}: the judge raised it but gave no quotable reason, so it is not raised")
        grounded.results[bid] = CheckResult(criterion_id=bid, findings=kept[bid] if call.triggered else [])
    return grounded
