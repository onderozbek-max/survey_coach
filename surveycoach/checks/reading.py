"""Conservative, local wording edits; never guess a question's intent from its topic.

A rewrite may only change wording. It must keep the behavior being measured, the timeframe, the
category, the examples and every qualifier, so each offered edit is checked against the original
(`lost_terms`) before it is shown. When no safe edit exists the card names the hardest words instead.
"""
from __future__ import annotations

import re

from surveycoach.checks.text import WORD, count_syllables

# Only a direct verb phrase, not 'the purchase of', quoted stimuli, or arbitrary deletion.
BUY = re.compile(r"\b(do you|did you|would you|will you|could you|can you) purchase\b", re.I)
# A bounded example-list restructure. Retain the named categories and both preparation modes, and keep
# the "such as" examples as examples ("like ..."), never the whole category. Deliberately decline unknown
# categories, qualifiers, extra examples, and different endings.
MEAL_EXAMPLES = re.compile(
    r"\bready-to-heat or ready-to-cook meal solutions, such as "
    r"(?P<examples>(?:prepared meals|meal kits)(?: or (?:prepared meals|meal kits))?), "
    r"to enjoy at home(?=\?)", re.I,
)
_MEAL_REPLACEMENT = r"ready-to-heat or ready-to-cook meals, like \g<examples>, to enjoy at home"
QUOTED = re.compile(r'["“”]|(?<!\w)[\'‘]|[\'’](?!\w)')

# Words a vetted edit may replace. Everything else in the original has to survive a rewrite.
SAFE_DROPS = {"purchase", "solution", "such", "as"}
_IGNORED = {"a", "an", "the", "do", "does", "did", "you", "your"}
_TOKEN = re.compile(r"[a-z0-9][a-z0-9'-]*")


def _stem(token: str) -> str:
    return token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token


def _tokens(text: str) -> list[str]:
    return [_stem(t.strip("'-")) for t in _TOKEN.findall(text.lower())]


def lost_terms(original: str, rewrite: str) -> list[str]:
    """Key terms of the original (behavior verb, category and example words, qualifiers, timeframe numbers)
    that the rewrite lost. Plural forms count as the same term; only the vetted `SAFE_DROPS` may go."""
    kept = set(_tokens(rewrite))
    return [t for t in dict.fromkeys(_tokens(original)) if t not in kept and t not in SAFE_DROPS | _IGNORED]


def simpler_question(text: str) -> str | None:
    """Return a local edit only; unsupported text stays manual, never a generic new question."""
    if QUOTED.search(text):
        return None
    revised = BUY.sub(lambda match: match[1] + " buy", text)
    revised = MEAL_EXAMPLES.sub(_MEAL_REPLACEMENT, revised)
    return revised if revised != text and not lost_terms(text, revised) else None


# --- Hard words, for questions with no safe rewrite -----------------------------------------------

MAX_HARD_TERMS = 4
# Small and vetted: each plain word means the same thing in a survey question.
SYNONYMS = {
    "purchase": "buy", "utilize": "use", "approximately": "about", "additional": "more", "regarding": "about",
    "sufficient": "enough", "assistance": "help", "numerous": "many", "commence": "start", "obtain": "get",
    "require": "need", "subsequently": "later", "frequently": "often", "currently": "now", "typically": "usually",
    "primarily": "mainly", "individuals": "people", "majority": "most",
}
WORDY = {
    "in order to": "to", "prior to": "before", "a number of": "several", "with regard to": "about",
    "due to the fact that": "because", "at this point in time": "now", "in the event that": "if",
    "on a regular basis": "often", "a large number of": "many", "in the near future": "soon",
}
_WORDY = re.compile(r"\b(?:" + "|".join(sorted(map(re.escape, WORDY), key=len, reverse=True)) + r")\b", re.I)


def _hard_words(text: str) -> list[tuple[str, int]]:
    """(word, rank) for long words and vetted-synonym words, in reading order. Names are skipped."""
    found, seen = [], set()
    for match in WORD.finditer(text):
        word = match.group(0)
        low = word.lower()
        if low in seen or (match.start() > 0 and word[0].isupper() and text[:match.start()].strip()[-1:] not in ".?!:"):
            continue
        syllables = count_syllables(low)
        if low in SYNONYMS or syllables >= 4 or (syllables >= 3 and len(low) >= 10):
            seen.add(low)
            found.append((low, 99 if low in SYNONYMS else syllables * 100 + len(low)))
    return found


def hard_terms(text: str) -> list[tuple[str, str | None]]:
    """The 2-4 hardest words or phrases, with a plain alternative only when the vetted map has one.

    Wordy phrases first, then words that have a plain alternative, then the longest words; each group in
    reading order. Fully deterministic: no model, no guessing at meaning.
    """
    phrases = [(m.group(0).lower(), WORDY[m.group(0).lower()]) for m in _WORDY.finditer(text)]
    words = _hard_words(text)
    ranked = sorted(words, key=lambda w: (w[0] not in SYNONYMS, -w[1], [x[0] for x in words].index(w[0])))
    chosen = {w for w, _ in ranked[:max(0, MAX_HARD_TERMS - len(phrases))]}
    return (phrases + [(w, SYNONYMS.get(w)) for w, _ in words if w in chosen])[:MAX_HARD_TERMS]


def as_written(text: str, term: str) -> str:
    """The term as it appears in the question (capitalization intact), so a highlight matches exactly."""
    found = re.search(rf"\b{re.escape(term)}\b", text, re.I)
    return found.group(0) if found else term


def _named(terms: list[tuple[str, str | None]]) -> str:
    return ", ".join(f'"{word}"' + (f' (try "{plain}")' if plain else "") for word, plain in terms)


def reading_steps(text: str) -> list[str]:
    """What to do when there is no safe rewrite: name the words to rework, never invent new wording.
    Grade numbers stay in the card's details."""
    terms = hard_terms(text)
    if not terms:
        return ["Cut every word that doesn't change what you are asking.",
                "Keep the topic, time frame and answer choices the same."]
    return [f"Hard words and phrases: {_named(terms)}.",
            "Rework only those. Keep the topic, time frame and answer choices the same."]


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
