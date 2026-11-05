"""Survey naming. Never invents a name: every candidate is read from the survey itself.

Priority at read time: definition title, humanized URL slug, first stimulus heading, then the
page's own document title. The user's own name always wins later, at display time.
"""
import re
from urllib.parse import unquote, urlsplit

from surveycoach.snapshot import SurveySnapshot

GENERIC_TITLES = frozenset({"survey", "surveys"})
# Leading slug words that name the survey family, not the survey. Owner to confirm the list.
SLUG_PREFIXES = ("Insights", "HMS")
_GENERIC_SLUGS = GENERIC_TITLES | {"preview", "take", "start", "view", "index"}
_WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")
_SENTENCE_END = re.compile(r"[.?!…:;,]$")
MAX_HEADING_WORDS, MAX_HEADING_CHARS, MAX_SLUG_WORDS = 8, 60, 8


def is_generic_title(title: str | None) -> bool:
    """RedJade's own page title ("Surveys") says nothing about this survey."""
    return (title or "").strip().casefold() in GENERIC_TITLES | {""}


def _humanize_segment(segment: str) -> str | None:
    if any(char.isdigit() for char in segment):   # numbers, ids and tokens are never names
        return None
    words = [word for part in re.split(r"[-_+.\s]+", segment) for word in _WORDS.findall(part)]
    prefixes = {prefix.casefold() for prefix in SLUG_PREFIXES}
    while words and words[0].casefold() in prefixes:
        words.pop(0)
    if not words or len(words) > MAX_SLUG_WORDS:
        return None
    # Random letters split into one- and two-letter fragments; words and acronyms do not.
    if any(len(word) < 3 and not (word.isupper() and len(word) == 2) for word in words):
        return None
    name = " ".join(word.capitalize() if word.islower() else word for word in words)
    return None if name.casefold() in _GENERIC_SLUGS else name


def humanize_slug(url: str) -> str | None:
    """Name from the last usable path segment; query strings and fragments (tokens) are ignored."""
    try:
        path = urlsplit(url or "").path
    except ValueError:
        return None
    for segment in reversed([unquote(part) for part in path.split("/") if part]):
        if name := _humanize_segment(segment):
            return name
    return None


def first_stimulus_heading(snapshot: SurveySnapshot) -> str | None:
    """First short, unpunctuated stimulus line: a product or concept name, not a sentence."""
    for page in snapshot.pages:
        # Flattened answer labels ("YesNo") can survive subtraction; they are never a heading.
        answers = sorted({label for q in page.questions for label in (q.text.strip(), *q.rows,
                          *(o.label for o in q.options)) if label}, key=len, reverse=True)
        for line in (line.strip() for line in page.stimulus_text.splitlines()):
            residue = line
            for answer in answers:
                residue = residue.replace(answer, "")
            if (line and len(line.split()) <= MAX_HEADING_WORDS and len(line) <= MAX_HEADING_CHARS
                    and not _SENTENCE_END.search(line) and any(c.isalpha() for c in residue)
                    and not is_generic_title(line)):
                return line
    return None


def resolve_title(snapshot: SurveySnapshot, *, definition_title: str = "", document_title: str = "") -> str:
    """Best honest name; a generic document title is kept only when nothing better exists."""
    for candidate in (definition_title.strip() if not is_generic_title(definition_title) else "",
                      humanize_slug(snapshot.source_url) or "",
                      first_stimulus_heading(snapshot) or "",
                      document_title.strip() if not is_generic_title(document_title) else ""):
        if candidate:
            return candidate
    return (document_title or definition_title).strip()


def presentable_title(snapshot: SurveySnapshot) -> str:
    """Display projection of a stored snapshot: a generic stored title is replaced, never rewritten."""
    if not is_generic_title(snapshot.title):
        return snapshot.title
    return humanize_slug(snapshot.source_url) or first_stimulus_heading(snapshot) or snapshot.title
