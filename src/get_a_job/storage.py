from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from get_a_job.connectors import SourceFetchResult
from get_a_job.models import CandidateProfile, Job
from get_a_job.learning import DecisionSignals
from get_a_job.text import plain_text


SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    job_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'new'
);
CREATE TABLE IF NOT EXISTS job_versions (
    job_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(job_key, payload_hash)
);
CREATE TABLE IF NOT EXISTS source_fetches (
    source_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    payload_hash TEXT,
    payload TEXT,
    job_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    PRIMARY KEY(source_id, fetched_at)
);
CREATE TABLE IF NOT EXISTS decision_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS application_followups (
    job_key TEXT PRIMARY KEY,
    follow_up_date TEXT NOT NULL DEFAULT '',
    reminder_note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboard_diagnostics (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboard_diagnostic_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class UpsertReport:
    inserted: int
    changed: int


@dataclass(frozen=True)
class DescriptionNormalizationReport:
    scanned: int
    changed: int
    changed_by_source: dict[str, int]


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)")}
            if "content_hash" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN content_hash TEXT")
            if "change_count" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN change_count INTEGER NOT NULL DEFAULT 0")
            if "last_changed_at" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN last_changed_at TEXT")
            if "fingerprint" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN fingerprint TEXT")
            if "duplicate_of" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN duplicate_of TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS jobs_fingerprint_idx ON jobs(fingerprint)")
            rows = connection.execute("SELECT job_key, payload FROM jobs WHERE fingerprint IS NULL").fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE jobs SET fingerprint = ? WHERE job_key = ?",
                    (self._fingerprint(Job.from_dict(json.loads(row["payload"]))), row["job_key"]),
                )

    @staticmethod
    def _fingerprint(job: Job) -> str:
        """Stable cross-board identity for the same employer, title, and location."""
        def normalize(value: str) -> str:
            value = re.sub(r"\b(remote|hybrid|onsite|on site)\b", "", value.lower())
            return re.sub(r"[^a-z0-9]+", "", value)
        return "|".join(normalize(value) for value in (job.company, job.title, job.location))

    def save_profile(self, profile: CandidateProfile) -> None:
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO profile(id, payload) VALUES(1, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
                (json.dumps(asdict(profile)),),
            )

    def load_profile(self) -> CandidateProfile:
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM profile WHERE id = 1").fetchone()
        if row is None:
            raise RuntimeError("no profile loaded; run import-profile first")
        return CandidateProfile.from_dict(json.loads(row["payload"]))

    def save_dashboard_diagnostics(self, key: str, payload: dict[str, int]) -> None:
        """Persist small local counters, never cached candidate or job data."""
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO dashboard_diagnostics(key, payload, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at",
                (key, json.dumps(payload, sort_keys=True), datetime.now(timezone.utc).isoformat()),
            )

    def load_dashboard_diagnostics(self, key: str) -> dict[str, int]:
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM dashboard_diagnostics WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return {}
        payload = json.loads(row["payload"])
        if not isinstance(payload, dict):
            return {}
        return {
            name: value
            for name, value in payload.items()
            if isinstance(name, str) and isinstance(value, int) and not isinstance(value, bool)
        }

    def record_dashboard_diagnostics(self, key: str, payload: dict[str, int]) -> None:
        """Keep a bounded local timeline of aggregate diagnostics."""
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO dashboard_diagnostic_events(key, observed_at, payload) VALUES(?, ?, ?)",
                (key, datetime.now(timezone.utc).isoformat(), json.dumps(payload, sort_keys=True)),
            )
            connection.execute(
                "DELETE FROM dashboard_diagnostic_events WHERE key = ? AND id NOT IN "
                "(SELECT id FROM dashboard_diagnostic_events WHERE key = ? ORDER BY id DESC LIMIT 100)",
                (key, key),
            )

    def list_dashboard_diagnostics(self, key: str, limit: int = 12) -> list[dict[str, object]]:
        self.initialize()
        limit = min(max(limit, 1), 100)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT observed_at, payload FROM dashboard_diagnostic_events WHERE key = ? "
                "ORDER BY id DESC LIMIT ?",
                (key, limit),
            ).fetchall()
        samples: list[dict[str, object]] = []
        for row in reversed(rows):
            payload = json.loads(row["payload"])
            if isinstance(payload, dict):
                samples.append({
                    "observed_at": str(row["observed_at"]),
                    **{
                        name: value for name, value in payload.items()
                        if isinstance(name, str) and isinstance(value, int) and not isinstance(value, bool)
                    },
                })
        return samples

    def clear_dashboard_diagnostics_history(self, key: str) -> None:
        """Remove only retained aggregate history, preserving current counters."""
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM dashboard_diagnostic_events WHERE key = ?", (key,)
            )

    def upsert_jobs(self, jobs: list[Job]) -> UpsertReport:
        self.initialize()
        inserted = 0
        changed = 0
        observed_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            for job in jobs:
                exists = connection.execute(
                    "SELECT payload, content_hash, status, duplicate_of FROM jobs WHERE job_key = ?", (job.key,)
                ).fetchone()
                fingerprint = self._fingerprint(job)
                duplicate = None
                if exists is None:
                    duplicate = connection.execute(
                        "SELECT job_key FROM jobs WHERE fingerprint = ? ORDER BY first_seen_at LIMIT 1",
                        (fingerprint,),
                    ).fetchone()
                content = asdict(job)
                content.pop("first_seen_at", None)
                content_hash = sha256(
                    json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                stored_job = job
                if exists is not None:
                    stored_job = replace(job, first_seen_at=json.loads(exists["payload"])["first_seen_at"])
                status = str(exists["status"]) if exists is not None else ("duplicate" if duplicate else "new")
                duplicate_of = str(exists["duplicate_of"]) if exists is not None else (str(duplicate["job_key"]) if duplicate else None)
                payload = json.dumps(asdict(stored_job), sort_keys=True)
                is_changed = exists is not None and exists["content_hash"] not in (None, content_hash)
                if is_changed:
                    changed += 1
                if exists is None or is_changed:
                    connection.execute(
                        "INSERT OR IGNORE INTO job_versions(job_key, observed_at, payload_hash, payload) "
                        "VALUES(?, ?, ?, ?)",
                        (job.key, observed_at, content_hash, payload),
                    )
                connection.execute(
                    "INSERT INTO jobs(job_key, payload, first_seen_at, content_hash, change_count, last_changed_at, status, fingerprint, duplicate_of) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(job_key) DO UPDATE SET payload = excluded.payload, "
                    "last_seen_at = CURRENT_TIMESTAMP, content_hash = excluded.content_hash, "
                    "change_count = jobs.change_count + excluded.change_count, "
                    "fingerprint = excluded.fingerprint, duplicate_of = excluded.duplicate_of, "
                    "last_changed_at = CASE WHEN excluded.change_count = 1 THEN excluded.last_changed_at "
                    "ELSE jobs.last_changed_at END",
                    (job.key, payload, stored_job.first_seen_at, content_hash, int(is_changed), observed_at, status, fingerprint, duplicate_of),
                )
                inserted += exists is None
        return UpsertReport(inserted, changed)

    def record_source_fetch(self, result: SourceFetchResult) -> None:
        self.initialize()
        payload = json.dumps(result.payload, sort_keys=True) if result.payload is not None else None
        payload_hash = sha256(payload.encode("utf-8")).hexdigest() if payload else None
        with self.connect() as connection:
            # Keep the first raw copy of an unchanged public source response. Later
            # observations retain their hash, timestamp, count, and error state without
            # multiplying the database size with identical payload blobs.
            previous = connection.execute(
                "SELECT payload_hash FROM source_fetches WHERE source_id = ? "
                "ORDER BY fetched_at DESC LIMIT 1",
                (result.source_id,),
            ).fetchone()
            stored_payload = None if previous and previous["payload_hash"] == payload_hash else payload
            connection.execute(
                "INSERT INTO source_fetches(source_id, fetched_at, payload_hash, payload, job_count, error) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (
                    result.source_id,
                    datetime.now(timezone.utc).isoformat(),
                    payload_hash,
                    stored_payload,
                    len(result.jobs),
                    result.error,
                ),
            )

    def compact_source_payloads(self, reclaim_space: bool = False) -> int:
        """Discard duplicate raw payload copies while retaining every fetch record and hash."""
        self.initialize()
        duplicate_row_ids: list[int] = []
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT rowid, source_id, payload_hash FROM source_fetches "
                "WHERE payload IS NOT NULL AND payload_hash IS NOT NULL "
                "ORDER BY source_id, payload_hash, fetched_at DESC"
            ).fetchall()
            retained: set[tuple[str, str]] = set()
            for row in rows:
                identity = (str(row["source_id"]), str(row["payload_hash"]))
                if identity in retained:
                    duplicate_row_ids.append(int(row["rowid"]))
                else:
                    retained.add(identity)
            for start in range(0, len(duplicate_row_ids), 500):
                batch = duplicate_row_ids[start : start + 500]
                placeholders = ", ".join("?" for _ in batch)
                connection.execute(f"UPDATE source_fetches SET payload = NULL WHERE rowid IN ({placeholders})", batch)
        if reclaim_space and duplicate_row_ids:
            with self.connect() as connection:
                connection.execute("VACUUM")
        return len(duplicate_row_ids)

    def backup(self, destination: str | Path) -> Path:
        """Create a consistent SQLite backup without interrupting readers."""
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError(f"backup already exists: {destination}")
        self.initialize()
        with self.connect() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        return destination

    def normalize_job_descriptions(
        self,
        *,
        apply: bool = False,
        include_expired: bool = False,
    ) -> DescriptionNormalizationReport:
        """Normalize active job payloads without changing source-history semantics."""
        self.initialize()
        where = "" if include_expired else " WHERE status != 'expired'"
        changed_rows: list[tuple[str, str, str]] = []
        changed_by_source: dict[str, int] = {}
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT job_key, payload FROM jobs{where} ORDER BY job_key"
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                description = str(payload.get("description", ""))
                normalized = plain_text(description)
                if not normalized or normalized == description:
                    continue
                payload["description"] = normalized
                content = dict(payload)
                content.pop("first_seen_at", None)
                content_hash = sha256(
                    json.dumps(
                        content,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                changed_rows.append(
                    (
                        json.dumps(payload, sort_keys=True),
                        content_hash,
                        str(row["job_key"]),
                    )
                )
                source = str(payload.get("source", "unknown"))
                changed_by_source[source] = changed_by_source.get(source, 0) + 1

            if apply and changed_rows:
                connection.executemany(
                    "UPDATE jobs SET payload = ?, content_hash = ? WHERE job_key = ?",
                    changed_rows,
                )

        return DescriptionNormalizationReport(
            scanned=len(rows),
            changed=len(changed_rows),
            changed_by_source=dict(sorted(changed_by_source.items())),
        )

    def list_jobs(self, statuses: list[str] | None = None) -> list[Job]:
        return [job for job, _ in self.list_job_records(statuses)]

    def get_job(self, job_key: str) -> Job:
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
        if row is None:
            raise ValueError(f"job not found: {job_key}")
        return Job.from_dict(json.loads(row["payload"]))

    def list_job_records(self, statuses: list[str] | None = None) -> list[tuple[Job, str]]:
        self.initialize()
        query = "SELECT payload, status FROM jobs"
        params: list[str] = []
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            query += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY first_seen_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [(Job.from_dict(json.loads(row["payload"])), str(row["status"])) for row in rows]

    def status_counts(self) -> dict[str, int]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute("SELECT status, count(*) AS count FROM jobs GROUP BY status").fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def ranking_revision(self, status: str) -> tuple[int, str, str, int]:
        """Small cache key that changes whenever ranking inputs for a queue change."""
        self.initialize()
        with self.connect() as connection:
            jobs = connection.execute(
                "SELECT count(*) AS count, COALESCE(MAX(last_seen_at), '') AS last_seen, "
                "COALESCE(MAX(last_changed_at), '') AS last_changed FROM jobs WHERE status = ?",
                (status,),
            ).fetchone()
            decision_id = connection.execute("SELECT COALESCE(MAX(id), 0) AS value FROM decision_events").fetchone()["value"]
        return int(jobs["count"]), str(jobs["last_seen"]), str(jobs["last_changed"]), int(decision_id)

    def expire_stale_jobs(self, days: int = 30) -> int:
        """Hide old unreviewed jobs after a successful source refresh without deleting history."""
        if days < 1:
            raise ValueError("stale-job age must be at least one day")
        self.initialize()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self.connect() as connection:
            return connection.execute(
                "UPDATE jobs SET status = 'expired' WHERE status = 'new' AND last_seen_at < ?",
                (cutoff,),
            ).rowcount

    def expire_stale_jobs_for_sources(self, source_ids: list[str], days: int = 30) -> int:
        """Expire only roles from sources that completed a successful refresh."""
        if days < 1:
            raise ValueError("stale-job age must be at least one day")
        source_ids = [source_id for source_id in source_ids if source_id]
        if not source_ids:
            return 0
        self.initialize()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        source_clauses = " OR ".join("job_key LIKE ?" for _ in source_ids)
        params = [cutoff, *(f"{source_id}:%" for source_id in source_ids)]
        with self.connect() as connection:
            return connection.execute(
                "UPDATE jobs SET status = 'expired' WHERE status = 'new' AND last_seen_at < ? "
                f"AND ({source_clauses})",
                params,
            ).rowcount

    def source_health(self) -> list[dict[str, object]]:
        """Return the latest result for each public source without exposing payloads."""
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT latest.source_id, latest.fetched_at, latest.job_count, latest.error "
                "FROM source_fetches AS latest "
                "INNER JOIN (SELECT source_id, MAX(fetched_at) AS fetched_at "
                "FROM source_fetches GROUP BY source_id) AS most_recent "
                "ON latest.source_id = most_recent.source_id "
                "AND latest.fetched_at = most_recent.fetched_at "
                "ORDER BY latest.source_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def activity_status(self) -> dict[str, str | None]:
        self.initialize()
        with self.connect() as connection:
            last_fetch = connection.execute("SELECT MAX(fetched_at) AS value FROM source_fetches").fetchone()["value"]
            last_job_seen = connection.execute("SELECT MAX(last_seen_at) AS value FROM jobs").fetchone()["value"]
        return {"last_fetch_at": last_fetch, "last_job_seen_at": last_job_seen}

    def set_review(self, job_key: str, status: str, note: str = "") -> None:
        allowed = {"saved", "rejected", "applied"}
        if status not in allowed:
            raise ValueError(f"review status must be one of: {', '.join(sorted(allowed))}")
        self.initialize()
        with self.connect() as connection:
            updated = connection.execute(
                "UPDATE jobs SET status = ? WHERE job_key = ?", (status, job_key)
            ).rowcount
            if updated == 0:
                raise ValueError(f"job not found: {job_key}")
            connection.execute(
                "INSERT INTO decision_events(job_key, status, note, decided_at) VALUES(?, ?, ?, ?)",
                (job_key, status, note, datetime.now(timezone.utc).isoformat()),
            )

    def list_decisions(self, limit: int = 20) -> list[sqlite3.Row]:
        self.initialize()
        with self.connect() as connection:
            return connection.execute(
                "SELECT job_key, status, note, decided_at FROM decision_events "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def list_decision_history(self, limit: int = 50) -> list[dict[str, object]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT decision_events.job_key, decision_events.status, decision_events.note, "
                "decision_events.decided_at, jobs.payload FROM decision_events "
                "LEFT JOIN jobs ON jobs.job_key = decision_events.job_key "
                "ORDER BY decision_events.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        history: list[dict[str, object]] = []
        for row in rows:
            job = Job.from_dict(json.loads(row["payload"])) if row["payload"] else None
            history.append(
                {
                    "job_key": row["job_key"],
                    "status": row["status"],
                    "note": row["note"],
                    "decided_at": row["decided_at"],
                    "title": job.title if job else None,
                    "company": job.company if job else None,
                    "url": job.url if job else None,
                }
            )
        return history

    def save_application_followup(self, job_key: str, follow_up_date: str, reminder_note: str) -> None:
        if follow_up_date:
            try:
                date.fromisoformat(follow_up_date)
            except ValueError as error:
                raise ValueError("follow-up date must use YYYY-MM-DD") from error
        if len(reminder_note) > 1000:
            raise ValueError("follow-up reminder must be 1,000 characters or fewer")
        self.initialize()
        with self.connect() as connection:
            job = connection.execute("SELECT status FROM jobs WHERE job_key = ?", (job_key,)).fetchone()
            if job is None:
                raise ValueError(f"job not found: {job_key}")
            if job["status"] != "applied":
                raise ValueError("follow-ups can only be set for currently applied roles")
            connection.execute(
                "INSERT INTO application_followups(job_key, follow_up_date, reminder_note, updated_at) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(job_key) DO UPDATE SET follow_up_date = excluded.follow_up_date, reminder_note = excluded.reminder_note, updated_at = excluded.updated_at",
                (job_key, follow_up_date, reminder_note, datetime.now(timezone.utc).isoformat()),
            )

    def list_application_followups(self) -> list[dict[str, object]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT followups.job_key, followups.follow_up_date, followups.reminder_note, jobs.payload "
                "FROM application_followups AS followups LEFT JOIN jobs ON jobs.job_key = followups.job_key "
                "ORDER BY NULLIF(followups.follow_up_date, ''), followups.updated_at DESC"
            ).fetchall()
        return [{"job_key": row["job_key"], "follow_up_date": row["follow_up_date"], "reminder_note": row["reminder_note"], "title": Job.from_dict(json.loads(row["payload"])).title if row["payload"] else None, "company": Job.from_dict(json.loads(row["payload"])).company if row["payload"] else None} for row in rows]

    def list_applications(self) -> list[dict[str, object]]:
        """Return one row per role whose current status is applied."""
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT jobs.job_key, jobs.payload, event.note, event.decided_at, "
                "COALESCE(followups.follow_up_date, '') AS follow_up_date, "
                "COALESCE(followups.reminder_note, '') AS reminder_note "
                "FROM jobs INNER JOIN decision_events AS event ON event.id = ("
                "SELECT MAX(id) FROM decision_events WHERE job_key = jobs.job_key) "
                "LEFT JOIN application_followups AS followups ON followups.job_key = jobs.job_key "
                "WHERE jobs.status = 'applied' ORDER BY event.decided_at DESC"
            ).fetchall()
        return [
            {"job_key": row["job_key"], "title": job.title, "company": job.company, "url": job.url,
             "applied_at": row["decided_at"], "note": row["note"], "follow_up_date": row["follow_up_date"],
             "reminder_note": row["reminder_note"]}
            for row in rows if (job := Job.from_dict(json.loads(row["payload"])))
        ]

    def decision_signals(self) -> DecisionSignals:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT jobs.payload, decision_events.status FROM decision_events "
                "INNER JOIN jobs ON jobs.job_key = decision_events.job_key"
            ).fetchall()
        return DecisionSignals.from_decisions(
            [(Job.from_dict(json.loads(row["payload"])), str(row["status"])) for row in rows]
        )
