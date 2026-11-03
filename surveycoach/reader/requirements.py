"""Bounded requirement interpretation and explicitly synthetic upload assets."""
import re
import struct
import zlib
from pathlib import Path


class UnmetRequirement(ValueError):
    """A known requirement cannot be satisfied safely within reader limits."""


def placeholder_png(directory: Path) -> Path:
    """Use only our dedicated generated asset, never arbitrary root screenshots."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'surveycoach-test-placeholder.png'
    raw = b''.join(b'\x00' + b'\xff\xff\xff' * 64 for _ in range(64))

    def chunk(kind, body):
        return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body))

    payload = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 64, 64, 8, 2, 0, 0, 0))
    payload += chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    # Always generate it: a pre-existing filename alone does not prove an image is synthetic.
    path.write_bytes(payload)
    path.chmod(0o600)
    return path


def length_bounds(item: dict, feedback: str = '') -> tuple[int, int]:
    low = max(1, int(item.get('minlength', -1)))
    high = int(item.get('maxlength', -1))
    high = high if high >= 0 else 1000
    # Field-scoped HTML validity and visible errors take precedence over prose guesses.
    for pattern in (r'(?:at least|minimum(?: of)?|min(?:imum)? length(?: of)?)\s+(\d+)\s*characters?',):
        found = re.search(pattern, feedback, re.I)
        if found:
            low = max(low, int(found[1]))
    found = re.search(r'(?:at most|maximum(?: of)?|no more than|up to)\s+(\d+)\s*characters?', feedback, re.I)
    if found:
        high = min(high, int(found[1]))
    if low > high or low > 1000 or high < 1:
        raise UnmetRequirement('Text length requirements conflict or exceed the synthetic-answer limit.')
    return low, high


def synthetic_text(item: dict, feedback: str = '') -> str:
    low, high = length_bounds(item, feedback)
    target = min(high, max(low, len('SurveyCoach test')))
    return ('SurveyCoach test ' * (target // 17 + 2))[:target]


def selection_minimum(group: dict, feedback: str = '') -> int:
    text = group['prompt'] + ' ' + feedback
    found = re.search(r'(?:select|choose|pick)\s+(?:at least\s+|exactly\s+)?(\d+)', text, re.I)
    return min(30, max(1, int(found[1]))) if found else 1
