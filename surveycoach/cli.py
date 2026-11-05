"""Command line: python -m surveycoach review <snapshot.json>"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from surveycoach.judge.batches import BATCHES
from surveycoach.llm import WibeyProvider
from surveycoach.review import Review, run_review
from surveycoach.snapshot import SurveySnapshot

READINESS_LABEL = {"ready": "Ready to launch", "almost_ready": "Almost ready", "needs_work": "Needs work"}


def _ai_lines(review: Review) -> list[str]:
    """Say plainly what the AI step did, so nothing unchecked reads as checked."""
    card = review.scorecard
    if review.ai is None:
        return [f"  AI check: not run. {card.unchecked_points} points wait on it (add --ai to run it)."] if card.provisional else []
    info = review.ai
    lines = [f"  AI judge ({info.model}): checked {len(info.checked)} of {len(BATCHES)} parts."]
    titles = {b.id: b.title for b in BATCHES}
    if info.failed:
        lines.append(f"  could not check: {', '.join(titles[b] for b in info.failed)}")
        lines += [f"    {titles[b]}: {why}" for b, why in info.failed.items()]
    if info.merged:
        lines.append(f"  merged {len(info.merged)} overlaps so each text has one rewrite:")
        lines += [f"    - {note}" for note in info.merged]
    if info.dropped:
        lines.append(f"  ignored {len(info.dropped)} claims the survey did not back up:")
        lines += [f"    - {note}" for note in info.dropped]
    if card.unchecked_points:
        lines.append(f"  {card.unchecked_points} points are still unchecked: {', '.join(review.unchecked)}.")
    return lines


def render(review: Review) -> str:
    card = review.scorecard
    checked = card.checked_points
    earned = card.score
    lines = [f"SurveyCoach review: {review.survey_title}", "", f"Readiness: {READINESS_LABEL[card.readiness]}"]
    lines.append(f"  Score on the {checked} points checked so far: {earned:.1f} of {checked} ({earned / checked:.0%})."
                 if checked else "  Nothing has been checked yet.")
    lines += _ai_lines(review)
    if card.pending_blockers:
        lines.append(f"  {len(card.pending_blockers)} launch checks ({', '.join(card.pending_blockers)}) are still unchecked,"
                     " so this cannot be called Ready to launch yet.")
    promise = f" (the intro promises {review.promised_minutes:g})" if review.promised_minutes else ""
    calibration = "Calibrated" if review.timing.calibrated else "Uncalibrated"
    lines.append(f"{calibration} estimated member completion: {review.est_minutes:g} minutes{promise}; "
                 "not crawl or load time. Verify with a timed pilot.")
    if review.timing.path_uncertain:
        lines.append("  Captured screens include alternative or conditional pages, not a verified member route.")
    for title, severity in (("MUST FIX", "must_fix"), ("WORTH IMPROVING", "worth_improving")):
        items = [f for f in review.findings if f.severity == severity]
        lines += ["", f"{title} ({len(items)})"]
        for f in items:
            where = f" [{f.question_id or f.page_id}]" if f.question_id or f.page_id else ""
            tag = "[AI] " if f.source == "ai" else ""
            lines += [f"  {f.criterion_id}{where}  {tag}{f.headline}", f"      Why: {f.explanation}"]
            if f.suggested_text:
                lines += [f"      Now:  {f.current_text or '(nothing)'}", f"      Fix:  {f.suggested_text}"]
            lines += [f"      {o.label}: {o.text}" for o in f.options]
    lines += ["", "WHAT'S WORKING"] + [f"  {s}" for s in card.strengths or ["Nothing confirmed yet."]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="surveycoach")
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("review", help="Score a survey snapshot against the MMC rubric")
    review.add_argument("snapshot", type=Path)
    review.add_argument("--ai", action="store_true", help="Also run the AI judge (needs Wibey)")
    args = parser.parse_args(argv)
    snapshot = SurveySnapshot.model_validate_json(args.snapshot.read_text())
    print(render(run_review(snapshot, provider=WibeyProvider() if args.ai else None)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
