import json
import tempfile
import unittest
from pathlib import Path

from get_a_job.connectors import SourceFetchResult
from get_a_job.models import Job
from get_a_job.storage import Store


class StorageTests(unittest.TestCase):
    def test_description_normalization_supports_dry_run_apply_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "jobs.db")
            active = Job(
                "greenhouse:acme",
                "markup",
                "Architect",
                "Acme",
                "https://x/markup",
                "Readable placeholder",
            )
            expired = Job(
                "greenhouse:acme",
                "expired-markup",
                "Architect",
                "Acme",
                "https://x/expired",
                "Readable placeholder",
            )
            store.upsert_jobs([active, expired])
            with store.connect() as connection:
                for job in (active, expired):
                    row = connection.execute(
                        "SELECT payload FROM jobs WHERE job_key = ?",
                        (job.key,),
                    ).fetchone()
                    payload = json.loads(row["payload"])
                    payload["description"] = "Lead.&amp;nbsp;\\</p> \\<p>Build."
                    connection.execute(
                        "UPDATE jobs SET payload = ? WHERE job_key = ?",
                        (json.dumps(payload), job.key),
                    )
                connection.execute(
                    "UPDATE jobs SET status = 'expired' WHERE job_key = ?",
                    (expired.key,),
                )

            dry_run = store.normalize_job_descriptions()
            self.assertEqual((dry_run.scanned, dry_run.changed), (1, 1))
            self.assertEqual(dry_run.changed_by_source, {"greenhouse:acme": 1})
            with store.connect() as connection:
                raw = json.loads(
                    connection.execute(
                        "SELECT payload FROM jobs WHERE job_key = ?",
                        (active.key,),
                    ).fetchone()["payload"]
                )["description"]
            self.assertIn("&amp;nbsp;", raw)

            backup = store.backup(root / "before.db")
            applied = store.normalize_job_descriptions(apply=True)
            self.assertTrue(backup.exists())
            self.assertEqual(applied.changed, 1)
            with store.connect() as connection:
                active_description = json.loads(
                    connection.execute(
                        "SELECT payload FROM jobs WHERE job_key = ?",
                        (active.key,),
                    ).fetchone()["payload"]
                )["description"]
                expired_description = json.loads(
                    connection.execute(
                        "SELECT payload FROM jobs WHERE job_key = ?",
                        (expired.key,),
                    ).fetchone()["payload"]
                )["description"]
            self.assertEqual(active_description, "Lead. Build.")
            self.assertIn("&amp;nbsp;", expired_description)

            all_roles = store.normalize_job_descriptions(
                apply=True,
                include_expired=True,
            )
            self.assertEqual(all_roles.changed, 1)

    def test_changed_job_and_source_payload_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            first = Job("source", "1", "Architect", "Acme", "https://x/1", "Python", remote=True)
            report = store.upsert_jobs([first])
            self.assertEqual((report.inserted, report.changed), (1, 0))
            changed = Job("source", "1", "Architect", "Acme", "https://x/1", "Python and SQL", remote=True)
            report = store.upsert_jobs([changed])
            self.assertEqual((report.inserted, report.changed), (0, 1))
            store.record_source_fetch(SourceFetchResult("greenhouse:acme", [changed], {"jobs": [1]}))
            with store.connect() as connection:
                versions = connection.execute("SELECT count(*) AS count FROM job_versions").fetchone()
                snapshots = connection.execute("SELECT count(*) AS count FROM source_fetches").fetchone()
            self.assertEqual(versions["count"], 2)
            self.assertEqual(snapshots["count"], 1)

    def test_unchanged_source_payload_is_not_stored_repeatedly(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            result = SourceFetchResult("greenhouse:acme", [], {"jobs": ["unchanged"]})
            store.record_source_fetch(result)
            store.record_source_fetch(result)
            with store.connect() as connection:
                rows = connection.execute(
                    "SELECT payload_hash, payload FROM source_fetches ORDER BY fetched_at"
                ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["payload_hash"], rows[1]["payload_hash"])
            self.assertIsNotNone(rows[0]["payload"])
            self.assertIsNone(rows[1]["payload"])

    def test_compaction_keeps_one_payload_per_source_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            result = SourceFetchResult("greenhouse:acme", [], {"jobs": ["unchanged"]})
            store.record_source_fetch(result)
            store.record_source_fetch(result)
            with store.connect() as connection:
                connection.execute(
                    "UPDATE source_fetches SET payload = ? WHERE payload IS NULL",
                    ('{"jobs": ["unchanged"]}',),
                )
            self.assertEqual(store.compact_source_payloads(), 1)
            with store.connect() as connection:
                payload_count = connection.execute(
                    "SELECT count(*) AS count FROM source_fetches WHERE payload IS NOT NULL"
                ).fetchone()["count"]
            self.assertEqual(payload_count, 1)

    def test_review_decisions_update_status_and_keep_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            job = Job("source", "1", "Architect", "Acme", "https://x/1", "Python", remote=True)
            store.upsert_jobs([job])
            store.set_review(job.key, "saved", "Strong architecture fit")
            self.assertEqual(store.list_jobs(["new"]), [])
            self.assertEqual(store.list_jobs(["saved"])[0].key, job.key)
            decision = store.list_decisions()[0]
            self.assertEqual(decision["note"], "Strong architecture fit")

    def test_applications_reflect_current_status_and_validate_followups(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            job = Job("source", "application", "Architect", "Acme", "https://x/1", "Python", remote=True)
            store.upsert_jobs([job])
            store.set_review(job.key, "applied", "Applied through employer site")
            store.save_application_followup(job.key, "2026-09-15", "Check application status")
            self.assertEqual(store.list_applications()[0]["follow_up_date"], "2026-09-15")
            store.set_review(job.key, "rejected", "Role closed")
            self.assertEqual(store.list_applications(), [])
            with self.assertRaisesRegex(ValueError, "currently applied"):
                store.save_application_followup(job.key, "2026-09-16", "Retry")

    def test_get_job_returns_stored_role_and_rejects_unknown_key(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            job = Job("source", "1", "Architect", "Acme", "https://x/1", "Python", remote=True)
            store.upsert_jobs([job])
            self.assertEqual(store.get_job(job.key), job)
            with self.assertRaisesRegex(ValueError, "job not found"):
                store.get_job("missing")

    def test_expire_stale_jobs_keeps_history_without_deleting_job(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            job = Job("source", "1", "Architect", "Acme", "https://x/1", "Python", remote=True)
            store.upsert_jobs([job])
            with store.connect() as connection:
                connection.execute(
                    "UPDATE jobs SET last_seen_at = '2000-01-01T00:00:00+00:00' WHERE job_key = ?",
                    (job.key,),
                )
            self.assertEqual(store.expire_stale_jobs(30), 1)
            self.assertEqual(store.list_job_records(["expired"])[0][0].key, job.key)

    def test_source_specific_expiration_keeps_jobs_from_failed_sources_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            refreshed = Job("greenhouse:acme", "1", "Architect", "Acme", "https://x/1", "Python", remote=True)
            failed_source = Job("lever:beta", "1", "Architect", "Beta", "https://x/2", "Python", remote=True)
            store.upsert_jobs([refreshed, failed_source])
            with store.connect() as connection:
                connection.execute("UPDATE jobs SET last_seen_at = '2000-01-01T00:00:00+00:00'")
            self.assertEqual(store.expire_stale_jobs_for_sources(["greenhouse:acme"], 30), 1)
            self.assertEqual([job.key for job, _ in store.list_job_records(["new"])], [failed_source.key])

    def test_ranking_revision_changes_after_a_review(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            job = Job("source", "revision", "Architect", "Acme", "https://x/1", "Python", remote=True)
            store.upsert_jobs([job])
            before = store.ranking_revision("new")
            store.set_review(job.key, "saved")
            self.assertNotEqual(store.ranking_revision("new"), before)

    def test_cross_source_duplicate_is_hidden_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            direct = Job("greenhouse:acme", "1", "Technical Program Manager", "Acme", "https://x/1", "Python", location="Remote (US)", remote=True)
            mirrored = Job("yc:work-at-a-startup", "2", "Technical Program Manager", "Acme", "https://x/2", "Python", location="Remote US", remote=True)
            store.upsert_jobs([direct, mirrored])
            self.assertEqual(store.status_counts()["duplicate"], 1)
            with store.connect() as connection:
                row = connection.execute("SELECT duplicate_of FROM jobs WHERE job_key = ?", (mirrored.key,)).fetchone()
            self.assertEqual(row["duplicate_of"], direct.key)
