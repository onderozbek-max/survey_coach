"""Text a person typed, made safe to store and show: no control, zero-width or text-direction characters.

HTML and Slack escaping stay the renderer's job; this only removes what is invisible or reorders text.
"""
import re

_UNSAFE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def clean_text(value: str | None) -> str:
    """No control, zero-width or bidi-override characters; newlines and tabs stay."""
    return _UNSAFE.sub("", value or "").strip()


def one_line(value: str | None) -> str:
    """`clean_text` with every run of whitespace (newlines included) folded to one space."""
    return " ".join(clean_text(value).split())
