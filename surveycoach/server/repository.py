"""Small SQLite store: immutable snapshots/review attempts, version-scoped decisions."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from pydantic import TypeAdapter

from surveycoach.labels import screen_labels
from surveycoach.recommendations import guard_recommendation

from surveycoach.snapshot import SurveySnapshot, SurveyType
from surveycoach.server.rounds import (canonical_source_url, change_sheet, compare_rounds,
                                       presentation, project_review, valid_decisions)

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS surveys (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS versions (
    survey_id TEXT NOT NULL REFERENCES surveys(id), version INTEGER NOT NULL,
    content_hash TEXT NOT NULL, title TEXT NOT NULL, snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (survey_id, version), UNIQUE (survey_id, content_hash)
);
CREATE TABLE IF NOT EXISTS coverage (
    survey_id TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (survey_id, version),
    FOREIGN KEY (survey_id, version) REFERENCES versions(survey_id, version)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, survey_id TEXT NOT NULL, version INTEGER NOT NULL,
    ai_requested INTEGER NOT NULL, status TEXT NOT NULL, error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT,
    FOREIGN KEY (survey_id, version) REFERENCES versions(survey_id, version)
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY, job_id TEXT UNIQUE NOT NULL REFERENCES jobs(id),
    survey_id TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (survey_id, version) REFERENCES versions(survey_id, version)
);
CREATE TABLE IF NOT EXISTS decisions (
    survey_id TEXT NOT NULL, version INTEGER NOT NULL, fingerprint TEXT NOT NULL,
    data TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (survey_id, version, fingerprint),
    FOREIGN KEY (survey_id, version) REFERENCES versions(survey_id, version)
);
"""


class Repository:
    def __init__(self, db_path: str | Path):
        if str(db_path) != ":memory:":
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(str(db_path), check_same_thread=False, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(surveys)")}
        if "display_title" not in columns:
            self.db.execute("ALTER TABLE surveys ADD COLUMN display_title TEXT")
        if "survey_type" not in columns:
            self.db.execute("ALTER TABLE surveys ADD COLUMN survey_type TEXT")
        # A stopped process cannot finish its in-process jobs. Never leave a spinner forever.
        with self.transaction() as db:
            db.execute("UPDATE jobs SET status='failed', error='Local server stopped before review finished', "
                       "finished_at=CURRENT_TIMESTAMP WHERE status IN ('queued', 'running')")

    @contextmanager
    def transaction(self):
        with self.lock, self.db:
            yield self.db

    def close(self):
        with self.lock:
            self.db.close()

    def submit(self, snapshot: SurveySnapshot, ai: bool, survey_id: str | None = None) -> dict:
        """Atomically find/create a snapshot and enqueue a review; never overwrite a snapshot."""
        with self.transaction() as db:
            if survey_id is None:
                survey_id = self.find_by_source_url(snapshot.source_url)
            if survey_id is None:
                survey_id = uuid4().hex
                db.execute("INSERT INTO surveys(id) VALUES (?)", (survey_id,))
            elif not db.execute("SELECT 1 FROM surveys WHERE id=?", (survey_id,)).fetchone():
                raise KeyError("Survey not found")
            row = db.execute("SELECT version FROM versions WHERE survey_id=? AND content_hash=?",
                             (survey_id, snapshot.review_hash)).fetchone()
            duplicate = row is not None
            if row:
                version = row["version"]
            else:
                version = db.execute("SELECT COALESCE(MAX(version), 0)+1 FROM versions WHERE survey_id=?",
                                     (survey_id,)).fetchone()[0]
                db.execute("INSERT INTO versions(survey_id, version, content_hash, title, snapshot) VALUES (?,?,?,?,?)",
                           (survey_id, version, snapshot.review_hash, snapshot.title, snapshot.model_dump_json()))
            active = db.execute("SELECT id FROM jobs WHERE survey_id=? AND version=? AND ai_requested=? "
                                "AND status IN ('queued','running') ORDER BY rowid DESC LIMIT 1",
                                (survey_id, version, int(ai))).fetchone()
            job_id = active["id"] if active else uuid4().hex
            if not active:
                db.execute("INSERT INTO jobs(id,survey_id,version,ai_requested,status) VALUES (?,?,?,?,'queued')",
                           (job_id, survey_id, version, int(ai)))
        return {"id": survey_id, "survey_id": survey_id, "version": version,
                "job_id": job_id, "deduplicated": duplicate, "scheduled": not bool(active)}

    def find_by_source_url(self, url: str) -> str | None:
        canonical = canonical_source_url(url)
        if not canonical:
            return None
        with self.transaction() as db:
            rows = db.execute("SELECT survey_id,snapshot FROM versions ORDER BY rowid").fetchall()
            matches = {row["survey_id"] for row in rows
                       if canonical_source_url(json.loads(row["snapshot"]).get("source_url")) == canonical}
            return next(iter(matches)) if len(matches) == 1 else None

    def rename(self, survey_id: str, title: str) -> dict:
        """Compatibility for callers using the original title-only API."""
        return self.update(survey_id, title=title)

    def update(self, survey_id: str, title: str | None = None,
               survey_type: SurveyType | None = None) -> dict:
        if title is not None:
            title = title.strip()
            if not title or len(title) > 200 or any(ord(c) < 32 for c in title):
                raise ValueError("Supply a title of 1 to 200 characters without control characters")
        if survey_type is not None:
            survey_type = TypeAdapter(SurveyType).validate_python(survey_type)
        if title is None and survey_type is None:
            raise ValueError("Supply a title or survey_type")
        with self.transaction() as db:
            if not db.execute("UPDATE surveys SET display_title=COALESCE(?, display_title), "
                              "survey_type=COALESCE(?, survey_type) WHERE id=?",
                              (title, survey_type, survey_id)).rowcount:
                raise KeyError("Survey not found")
        response = {"id": survey_id, "survey_id": survey_id}
        if title is not None:
            response["title"] = title
        if survey_type is not None:
            response.update(survey_type=survey_type, survey_type_chosen=True)
        return response

    @staticmethod
    def _latest_review(db, survey_id: str, version: int):
        row = db.execute("SELECT reviews.data FROM reviews JOIN jobs ON jobs.id=reviews.job_id "
                         "WHERE reviews.survey_id=? AND reviews.version=? ORDER BY jobs.rowid DESC LIMIT 1",
                         (survey_id, version)).fetchone()
        return json.loads(row["data"]) if row else None

    @staticmethod
    def _coverage(db, survey_id: str, version: int):
        row = db.execute("SELECT data FROM coverage WHERE survey_id=? AND version=?", (survey_id, version)).fetchone()
        return json.loads(row["data"]) if row else None

    @staticmethod
    def _qualify(review, coverage) -> None:
        """Partial reader coverage can never present an unqualified Ready."""
        if coverage and review and not coverage["full_branching_coverage"]:
            if review["scorecard"]["readiness"] == "ready":
                review["scorecard"]["readiness"] = "almost_ready"

    def list_surveys(self) -> list[dict]:
        with self.transaction() as db:
            rows = db.execute("SELECT v.survey_id AS id,v.title,v.version,v.content_hash,v.created_at,"
                              "v.snapshot,s.survey_type,s.display_title FROM versions v "
                              "JOIN surveys s ON s.id=v.survey_id WHERE v.version=(SELECT MAX(v2.version) FROM versions v2 "
                              "WHERE v2.survey_id=v.survey_id) ORDER BY v.created_at DESC, v.survey_id").fetchall()
            surveys = []
            for row in rows:
                item = dict(row) | {"readiness": None, "must_fix": None, "score_checked": None}
                snapshot = json.loads(item.pop("snapshot"))
                item["survey_type"] = row["survey_type"] or snapshot["survey_type"]
                item["survey_type_chosen"] = bool(row["survey_type"])
                if title := item.pop("display_title"):
                    item["title"] = title
                data = self._latest_review(db, row["id"], row["version"])
                if data:
                    review = project_review(dict(snapshot, survey_type=item["survey_type"]), data["review"])
                    self._qualify(review, self._coverage(db, row["id"], row["version"]))
                    card = review["scorecard"]
                    item.update(readiness=card["readiness"],
                                must_fix=sum(f["severity"] == "must_fix" for f in review["findings"]),
                                score_checked=[round(card["score"] if "checked_points" in card else card["score"] - card["unchecked_points"]),
                                               card.get("checked_points", 100 - card["unchecked_points"]) ])
                surveys.append(item)
            return surveys

    def _raw_detail(self, survey_id: str, version: int | None = None) -> dict:
        with self.transaction() as db:
            versions = db.execute("SELECT version,title,content_hash,created_at FROM versions "
                                  "WHERE survey_id=? ORDER BY version DESC", (survey_id,)).fetchall()
            if not versions:
                raise KeyError("Survey not found")
            version = version if version is not None else versions[0]["version"]
            row = db.execute("SELECT * FROM versions WHERE survey_id=? AND version=?", (survey_id, version)).fetchone()
            if row is None:
                raise KeyError("Version not found")
            review = self._latest_review(db, survey_id, version)
            decisions = db.execute("SELECT fingerprint,data FROM decisions WHERE survey_id=? AND version=?",
                                   (survey_id, version)).fetchall()
            job = db.execute("SELECT * FROM jobs WHERE survey_id=? AND version=? ORDER BY rowid DESC LIMIT 1",
                             (survey_id, version)).fetchone()
            data = {"id": survey_id, "survey_id": survey_id, "title": row["title"], "version": version,
                    "content_hash": SurveySnapshot.model_validate_json(row["snapshot"]).content_hash,
                    "review_hash": row["content_hash"], "snapshot": json.loads(row["snapshot"]),
                    "review": None, "timeline": [], "total_seconds": 0,
                    "versions": [dict(v) for v in versions],
                    "decisions": {d["fingerprint"]: json.loads(d["data"]) for d in decisions},
                    "job": self._job(job) if job else None}
            if review:
                data.update(review)
            metadata = db.execute("SELECT display_title,survey_type FROM surveys WHERE id=?", (survey_id,)).fetchone()
            data["title"] = metadata["display_title"] or row["title"]
            data["survey_type"] = metadata["survey_type"] or data["snapshot"]["survey_type"]
            data["survey_type_chosen"] = bool(metadata["survey_type"])
            data["snapshot_title"] = row["title"]
            data["coverage"] = self._coverage(db, survey_id, version)
            return data

    def _project_detail(self, data):
        """Project one round only. This never loads or walks historical rounds."""
        effective = dict(data["snapshot"], survey_type=data["survey_type"])
        data["screens"] = screen_labels(SurveySnapshot.model_validate(effective))
        if data["review"]:
            data["review"] = project_review(effective, data["review"])
            data["review"]["findings"] = [guard_recommendation(finding, effective)
                                           for finding in data["review"].get("findings", [])]
        self._qualify(data["review"], data["coverage"])
        data["decisions"] = valid_decisions(data)
        return data

    def detail(self, survey_id: str, version: int | None = None) -> dict:
        # Copy DB state under the lock; expensive checks run outside it. Compare
        # only the direct previous round, never recursively project all history.
        with self.transaction():
            data = self._raw_detail(survey_id, version)
            version = data["version"]
            prior = self._raw_detail(survey_id, version - 1) if version > 1 else None
        data = self._project_detail(data)
        data["round"] = version
        data["round_changes"] = {key: [] for key in ("fixed", "still", "new", "uncertain")}
        data["carried"] = {}
        if prior:
            data["round_changes"], carried = compare_rounds(self._project_detail(prior), data)
            data["carried"] = {key: value for key, value in carried.items() if key not in data["decisions"]}
            data["decisions"] = {**data["carried"], **data["decisions"]}
            data["round_changes"]["compared_to_round"] = version - 1
        data["round_changes"]["unchecked_paths"] = presentation(data)["scope"]["unchecked_paths"]
        data["carried_decisions"] = data["carried"]
        data["presentation"] = presentation(data)
        data["change_sheet"] = change_sheet(data)
        return data

    @staticmethod
    def _job(row) -> dict:
        data = dict(row)
        data["ai_requested"] = bool(data["ai_requested"])
        return data

    def job(self, job_id: str) -> dict:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                reader = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reader_jobs'").fetchone()
                row = db.execute("SELECT * FROM reader_jobs WHERE id=?", (job_id,)).fetchone() if reader else None
                if row is None:
                    raise KeyError("Job not found")
                return dict(row)
            return self._job(row)

    def start(self, job_id: str) -> bool:
        with self.transaction() as db:
            return db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'",
                              (job_id,)).rowcount == 1

    def finish(self, job_id: str, data: dict | None = None, error: str | None = None):
        with self.transaction() as db:
            job = self.job(job_id)
            if data is not None:
                db.execute("INSERT INTO reviews(job_id,survey_id,version,data) VALUES (?,?,?,?)",
                           (job_id, job["survey_id"], job["version"], json.dumps(data)))
            db.execute("UPDATE jobs SET status=?,error=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                       ("completed" if data is not None else "failed", error, job_id))

    def save_decision(self, survey_id: str, version: int, fingerprint: str, data: dict) -> dict:
        with self.transaction() as db:
            detail = self._project_detail(self._raw_detail(survey_id, version))
            findings = (detail["review"] or {}).get("findings", [])
            finding = next((f for f in findings if f["fingerprint"] == fingerprint), None)
            if finding is None:
                raise KeyError("Finding not found in this version's latest review")
            allowed = [option["text"] for option in finding.get("options", [])]
            if not allowed and finding.get("suggested_text"):
                allowed = [finding["suggested_text"]]
            if data["action"] == "pick" and data.get("picked_text") not in allowed:
                raise ValueError("Choose one of this finding's saved suggestions")
            existing = detail["decisions"].get(fingerprint)
            if existing and data.get("client_id") == existing.get("client_id") and data.get("revision", 0) <= existing.get("revision", 0):
                return existing
            saved = {**data, "fingerprint": fingerprint,
                     "original": finding.get("current_text") or finding["evidence"]}
            db.execute("INSERT INTO decisions(survey_id,version,fingerprint,data) VALUES (?,?,?,?) "
                       "ON CONFLICT(survey_id,version,fingerprint) DO UPDATE SET data=excluded.data, "
                       "updated_at=CURRENT_TIMESTAMP", (survey_id, version, fingerprint, json.dumps(saved)))
            return saved
