"""The owner's answer to "Does this survey offer a reward?" (brief 4.8), kept per survey, outside the snapshot.

  * `has_reward is None`  the question is still open: the welcome check keeps asking it;
  * `has_reward is False` no reward: nothing to nag about, nothing to check;
  * `has_reward is True`  a reward exists: the only thing left to check is that the welcome text mentions it.

Only the study owner knows which applies, so no reward is ever invented or assumed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from surveycoach.safe_text import one_line

REWARD_TEXT_MAX = 120
REWARD_WORDS = re.compile(r"\b(points?|rewards?|earn(?:ed|ing)?|gift ?cards?|\$\d+)\b", re.I)


@dataclass(frozen=True)
class Reward:
    has_reward: bool | None = None
    text: str = ""

    def mentioned_in(self, welcome: str) -> bool:
        """Reward wording in the welcome, or the owner's own words for it."""
        said = " ".join((welcome or "").lower().split())
        mine = " ".join(self.text.lower().split())
        return bool(REWARD_WORDS.search(welcome or "") or (mine and mine in said))

    def as_dict(self) -> dict:
        return {"has_reward": self.has_reward, "text": self.text}


def read_reward(raw: dict | None) -> Reward:
    """A stored answer as served: tolerant of missing or hand-edited rows, never raises."""
    raw = raw if isinstance(raw, dict) else {}
    has = raw.get("has_reward")
    has = has if isinstance(has, bool) else None
    text = one_line(raw.get("text") if isinstance(raw.get("text"), str) else "")[:REWARD_TEXT_MAX]
    return Reward(has, text if has else "")


def validate_reward(has_reward, text="") -> Reward:
    """The one rule for a new answer, shared by the API and the store; raises ValueError (422 over HTTP)."""
    if has_reward is not None and not isinstance(has_reward, bool):
        raise ValueError("has_reward must be true, false or null")
    if not isinstance(text, str):
        raise ValueError("text must be text")
    cleaned = one_line(text)
    if len(cleaned) > REWARD_TEXT_MAX:
        raise ValueError(f"Describe the reward in at most {REWARD_TEXT_MAX} characters")
    if cleaned and has_reward is not True:
        raise ValueError("text only applies when has_reward is true")
    return Reward(has_reward, cleaned)
