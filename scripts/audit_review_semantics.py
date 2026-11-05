"""Offline synthetic audit probes; no reader, model calls, database or network.

Print confirmed observations, not remediation status. Run from repository root:
    .venv/bin/python scripts/audit_review_semantics.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from surveycoach.checks.answers import no_overlap
from surveycoach.checks.images import fair_image_choices, light_and_accessible, sharp_and_high_res
from surveycoach.checks.registry import ReviewContext
from surveycoach.rubric import load_rubric
from surveycoach.snapshot import Media, Option, Page, Question, SurveySnapshot


def context(question: Question) -> ReviewContext:
    snapshot = SurveySnapshot(title="Synthetic audit", pages=[
        Page(id="p", position=0, kind="question", questions=[question])])
    return ReviewContext.build(snapshot, load_rubric())


def options(*labels: str) -> list[Option]:
    return [Option(id=f"o{index}", label=label) for index, label in enumerate(labels)]


def main() -> None:
    findings = []
    unknown = Question(id="unknown", text="Inspect image", kind="single_choice", media=[
        Media(loaded=True, alt="Synthetic product", natural_w=None, natural_h=None,
              rendered_w=None, rendered_h=None, bytes=None)])
    sharp = sharp_and_high_res(context(unknown))
    light = light_and_accessible(context(unknown))
    findings.append({"case": "missing_media_measurements", "resolution": sharp.model_dump(),
                     "weight": light.model_dump(),
                     "bug_reproduced": sharp.assessed and sharp.fraction == 1 and light.assessed and light.fraction == 1})

    choice = Question(id="equal-layout", text="Pick an image", kind="image_choice", options=options("A", "B"))
    for option, pixels in zip(choice.options, [1000, 2000]):
        option.media = Media(loaded=True, alt=option.label, natural_w=pixels, natural_h=pixels,
                             rendered_w=150, rendered_h=150, bytes=100000)
    result = fair_image_choices(context(choice))
    findings.append({"case": "equal_display_different_file_resolution", "result": result.model_dump(),
                     "bug_reproduced": any("differ a lot in size" in f.headline for f in result.findings)})

    units = Question(id="different-units", text="Which features do you want?", kind="multi_choice",
                     options=options("A 1 to 2 day delivery", "A 1 to 2 year warranty"))
    result = no_overlap(context(units))
    findings.append({"case": "unrelated_feature_ranges", "result": result.model_dump(),
                     "bug_reproduced": bool(result.findings)})

    money = Question(id="continuous", text="How much do you spend?", kind="single_choice",
                     options=options("0 to 10 dollars", "10 to 20 dollars"))
    result = no_overlap(context(money))
    findings.append({"case": "continuous_range_rewrite_leaves_gap", "result": result.model_dump(),
                     "bug_reproduced": any(f.suggested_text == "0 to 9 dollars" for f in result.findings)})
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
