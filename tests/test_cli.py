import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from get_a_job.cli import main
from get_a_job.models import Job
from get_a_job.storage import Store


class CliTests(unittest.TestCase):
    def test_normalize_descriptions_is_dry_run_by_default_and_backs_up_on_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "jobs.db"
            store = Store(db)
            job_payload = {
                "source": "greenhouse:acme",
                "external_id": "markup",
                "title": "Architect",
                "company": "Acme",
                "url": "https://example.com/markup",
                "description": "Lead.&amp;nbsp;\\</p> \\<p>Build.",
            }
            store.upsert_jobs([Job.from_dict(job_payload)])
            with store.connect() as connection:
                row = connection.execute(
                    "SELECT payload FROM jobs WHERE job_key = ?",
                    ("greenhouse:acme:markup",),
                ).fetchone()
                payload = json.loads(row["payload"])
                payload["description"] = job_payload["description"]
                connection.execute(
                    "UPDATE jobs SET payload = ? WHERE job_key = ?",
                    (json.dumps(payload), "greenhouse:acme:markup"),
                )

            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["--db", str(db), "normalize-descriptions"]),
                    0,
                )
            self.assertIn("Dry run: 1 of 1", output.getvalue())
            with store.connect() as connection:
                raw_description = json.loads(
                    connection.execute("SELECT payload FROM jobs").fetchone()["payload"]
                )["description"]
            self.assertIn("&amp;nbsp;", raw_description)

            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["--db", str(db), "normalize-descriptions", "--apply"]),
                    0,
                )
            self.assertIn("Normalized 1 of 1", output.getvalue())
            self.assertEqual(
                len(list(root.glob("jobs.description-backup-*.db"))),
                1,
            )

    def test_apply_preferences_merges_private_values_into_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "jobs.db"
            profile_path = root / "profile.json"
            preferences_path = root / "preferences.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "Candidate",
                        "target_titles": ["architect"],
                        "skills": ["Python"],
                    }
                ),
                encoding="utf-8",
            )
            preferences_path.write_text(
                json.dumps(
                    {
                        "minimum_salary": 150000,
                        "employment_types": ["full time"],
                        "eligible_countries": ["US"],
                        "work_authorized_countries": ["US"],
                        "consider_sponsorship_roles": False,
                        "title_priorities": ["architect"],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(main(["--db", str(db), "import-profile", str(profile_path)]), 0)
            self.assertEqual(main(["--db", str(db), "apply-preferences", str(preferences_path)]), 0)
            profile = Store(db).load_profile()
            self.assertEqual(profile.minimum_salary, 150000)
            self.assertEqual(profile.employment_types, ["full time"])
            self.assertEqual(profile.eligible_countries, ["US"])
            self.assertEqual(profile.work_authorized_countries, ["US"])
            self.assertFalse(profile.consider_sponsorship_roles)
