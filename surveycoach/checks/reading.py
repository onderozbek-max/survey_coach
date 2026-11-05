"""Conservative, local wording edits; never guess a question's intent from its topic."""
from __future__ import annotations

import re

# Only a direct verb phrase, not 'the purchase of', quoted stimuli, or arbitrary deletion.
BUY = re.compile(r"\b(do you|did you|would you|will you|could you|can you) purchase\b", re.I)
# A bounded example-list restructure. Retain the named categories and both preparation modes.
# Deliberately decline unknown categories, qualifiers, extra examples, and different endings.
MEAL_EXAMPLES = re.compile(
    r"\bready-to-heat or ready-to-cook meal solutions, such as "
    r"(?P<examples>(?:prepared meals|meal kits)(?: or (?:prepared meals|meal kits))?), "
    r"to enjoy at home(?=\?)", re.I,
)
QUOTED = re.compile(r'["“”]|(?<!\w)[\'‘]|[\'’](?!\w)')


def simpler_question(text: str) -> str | None:
    """Return a local edit only; unsupported text stays manual, never a generic new question."""
    if QUOTED.search(text):
        return None
    revised = BUY.sub(lambda match: match[1] + " buy", text)
    revised = MEAL_EXAMPLES.sub(
        lambda match: match["examples"] + " to heat or cook at home", revised,
    )
    return revised if revised != text else None


def reading_advice(grade: float, threshold: float, suggested: str | None) -> str:
    limits = (
        f"An automated formula estimates this wording at about US school grade {grade:.0f}. "
        f"The configured grade-{threshold:.0f} threshold is a review cue, not a scientific pass/fail test "
        "or a measure of actual comprehension. "
    )
    if suggested:
        return limits + (
            "Try the draft below. Check with the study owner that its category scope and meaning are unchanged; "
            "keep the answer choices, timeframe and preparation distinctions. "
            "Read it aloud before using it; a lower estimate alone does not prove it is clearer."
        )
    return limits + (
        "Keep the behavior being asked about, category boundaries, timeframe, qualifiers and answer choices. "
        "Read the question aloud; mark the words that need explaining and replace only those words with "
        "everyday equivalents agreed with the study owner. If a definition is needed, put it in help text "
        "without removing it from the member's task. No safe automatic rewrite is available for this wording."
    )
