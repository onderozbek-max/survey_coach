"""Typed strategies and private, scoped provisional rules. Never executable code."""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    op: Literal['fill', 'check', 'select', 'upload_png', 'click', 'wait']
    target: int = Field(default=0, ge=0, le=199)
    length: int = Field(default=16, ge=1, le=1000)
    option: int = Field(default=0, ge=0, le=199)
    milliseconds: int = Field(default=300, ge=100, le=5000)


class Strategy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    actions: list[Action] = Field(min_length=1, max_length=16)


def catalog(observation: dict) -> list[dict]:
    entries = []
    for group in observation['groups']:
        for item in group['items']:
            entries.append({**item, 'kind': group['kind'], 'prompt': group['prompt'], 'category': 'answer'})
    for category in ('uploads', 'auxiliary', 'nav'):
        entries.extend({**item, 'category': category} for item in observation.get(category, []))
    return entries


def descriptor(entry: dict) -> tuple:
    """No raw wording persisted; hashes bind replay to matching observed controls."""
    label_hash = hashlib.sha256(entry.get('label', '').encode()).hexdigest()[:16]
    return (entry['category'], entry.get('kind'), entry.get('type'), label_hash,
            entry.get('min'), entry.get('max'), entry.get('minlength'), entry.get('maxlength'),
            entry.get('accept'), len(entry.get('options', [])))


def signature(observation: dict) -> str:
    encoded = json.dumps([descriptor(entry) for entry in catalog(observation)], sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


class RuleStore:
    """Append evidence counters, quarantine any rule which fails its scoped replay."""
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS rules (scope TEXT, plan TEXT, successes INTEGER, failures INTEGER, PRIMARY KEY(scope,plan))')
        path.chmod(0o600)

    def connection(self):
        return sqlite3.connect(self.path)

    def candidates(self, scope: str) -> list[Strategy]:
        with self.connection() as db:
            rows = db.execute('SELECT plan FROM rules WHERE scope=? AND failures=0 ORDER BY successes DESC LIMIT 3', (scope,)).fetchall()
        plans = []
        for row in rows:
            try:
                plans.append(Strategy.model_validate_json(row[0]))
            except ValueError:
                continue
        return plans

    def success(self, scope: str, plan: Strategy):
        with self.connection() as db:
            db.execute('INSERT INTO rules VALUES (?,?,1,0) ON CONFLICT(scope,plan) DO UPDATE SET successes=successes+1', (scope, plan.model_dump_json()))

    def failure(self, scope: str, plan: Strategy):
        with self.connection() as db:
            db.execute('UPDATE rules SET failures=failures+1 WHERE scope=? AND plan=?', (scope, plan.model_dump_json()))
