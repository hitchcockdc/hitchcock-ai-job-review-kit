import http.client
import json
import os
import tempfile
import threading
import unittest
from dataclasses import asdict
from pathlib import Path

from get_a_job.dashboard_server import DashboardHandler
from get_a_job.dashboard_services import ApplicationService, ScoringPreviewService, TailoringService
from get_a_job.models import CandidateProfile, Job
from get_a_job.storage import Store
from http.server import ThreadingHTTPServer


class DashboardHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.store = Store(root / "jobs.db")
        self.store.save_profile(CandidateProfile("Candidate", ["Architect"], ["Python"]))
        self.job = Job("test", "1", "Architect", "Acme", "https://example.com", "Python")
        self.store.upsert_jobs([self.job])
        self.store.set_review(self.job.key, "applied", "Submitted")
        DashboardHandler.store = self.store
        DashboardHandler.config_dir = root / "config"
        DashboardHandler.refresh_minutes = 0
        DashboardHandler.ranking_cache = {}
        DashboardHandler.ranking_cache_sizes = {}
        DashboardHandler.candidate_cache = {}
        DashboardHandler.candidate_cache_hits = 0
        DashboardHandler.candidate_cache_misses = 0
        DashboardHandler.candidate_cache_evictions = 0
        DashboardHandler.candidate_cache_skips = 0
        DashboardHandler.ranking_cache_hits = 0
        DashboardHandler.ranking_cache_misses = 0
        DashboardHandler.ranking_cache_evictions = 0
        DashboardHandler.applications = ApplicationService(self.store)
        DashboardHandler.scoring_preview = ScoringPreviewService(self.store)
        DashboardHandler.tailoring = TailoringService(self.store, DashboardHandler.config_dir)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        body = json.dumps(payload) if payload is not None else None
        connection.request(method, path, body, {"Content-Type": "application/json"} if body else {})
        response = connection.getresponse()
        result = json.loads(response.read())
        connection.close()
        return response.status, result

    def test_application_endpoint_returns_current_state_and_persists_followup(self):
        status, payload = self.request("GET", "/api/applications")
        self.assertEqual(status, 200)
        self.assertEqual(payload["applications"][0]["job_key"], self.job.key)

        status, payload = self.request("POST", "/api/application-followups", {
            "job_key": self.job.key,
            "follow_up_date": "2026-09-10",
            "reminder_note": "Check in",
        })
        self.assertEqual((status, payload), (200, {"ok": True}))
        status, payload = self.request("GET", "/api/applications")
        self.assertEqual(status, 200)
        self.assertEqual(payload["applications"][0]["follow_up_date"], "2026-09-10")

    def test_followup_endpoint_rejects_invalid_date(self):
        status, payload = self.request("POST", "/api/application-followups", {
            "job_key": self.job.key,
            "follow_up_date": "not-a-date",
            "reminder_note": "Check in",
        })
        self.assertEqual(status, 400)
        self.assertIn("date", payload["error"])

    def test_profile_endpoint_validates_scoring_weights(self):
        profile = asdict(self.store.load_profile())
        profile["scoring_weights"]["role_skills"] += 1

        status, payload = self.request(
            "POST", "/api/config/profile", {"profile": profile}
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "scoring weights must total 100")

        profile["scoring_weights"]["required_skills"] -= 1
        DashboardHandler.ranking_cache = {("stale",): {}}
        DashboardHandler.candidate_cache = {("stale",): ([], 0, 0)}
        status, payload = self.request(
            "POST", "/api/config/profile", {"profile": profile}
        )
        self.assertEqual(status, 200)
        self.assertEqual(sum(payload["profile"]["scoring_weights"].values()), 100)
        self.assertEqual(DashboardHandler.ranking_cache, {})
        self.assertEqual(DashboardHandler.candidate_cache, {})

    def test_queue_response_records_ranking_cache_hits_and_misses(self):
        self.store.upsert_jobs([
            Job(
                "test", "ranking", "Architect", "RankCo", "https://example.com/ranking",
                "Python", location="Remote - US", remote=True,
            )
        ])

        status, first = self.request("GET", "/api/jobs?status=new&limit=10")
        self.assertEqual(status, 200)
        self.assertFalse(first["meta"]["cached"])
        status, second = self.request("GET", "/api/jobs?status=new&limit=10")
        self.assertEqual(status, 200)
        self.assertTrue(second["meta"]["cached"])
        self.assertEqual(second["meta"]["ranking_cache"]["misses"], 1)
        self.assertEqual(second["meta"]["ranking_cache"]["hits"], 1)

    def test_cache_reset_endpoint_releases_ranking_and_candidate_entries(self):
        DashboardHandler.ranking_cache = {("new",): {"jobs": []}}
        DashboardHandler.candidate_cache = {("new",): ([], 0, 0)}

        status, payload = self.request("POST", "/api/cache/reset")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(DashboardHandler.ranking_cache, {})
        self.assertEqual(DashboardHandler.candidate_cache, {})

    def test_cache_history_reset_endpoint_preserves_current_counters(self):
        self.store.record_dashboard_diagnostics("candidate_cache", {"hits": 3})
        DashboardHandler.candidate_cache_hits = 3

        status, payload = self.request("POST", "/api/cache/history/reset")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["candidate_cache"]["hits"], 3)
        self.assertEqual(payload["candidate_cache_history"], [])
        self.assertEqual(self.store.list_dashboard_diagnostics("candidate_cache"), [])

    def test_candidate_cache_diagnostics_restore_between_server_starts(self):
        DashboardHandler.candidate_cache_hits = 7
        DashboardHandler.candidate_cache_misses = 3
        DashboardHandler.candidate_cache_evictions = 2
        DashboardHandler.candidate_cache_skips = 1
        self.store.save_dashboard_diagnostics(
            "candidate_cache",
            {"hits": 7, "misses": 3, "evictions": 2, "skips": 1},
        )
        DashboardHandler.candidate_cache_hits = 0
        DashboardHandler.candidate_cache_misses = 0
        DashboardHandler.candidate_cache_evictions = 0
        DashboardHandler.candidate_cache_skips = 0

        DashboardHandler.restore_candidate_cache_diagnostics()

        self.assertEqual(DashboardHandler.candidate_cache_hits, 7)
        self.assertEqual(DashboardHandler.candidate_cache_misses, 3)
        self.assertEqual(DashboardHandler.candidate_cache_evictions, 2)
        self.assertEqual(DashboardHandler.candidate_cache_skips, 1)

    def test_scoring_preview_validates_without_persisting_weights(self):
        preview_job = Job(
            "test",
            "2",
            "Cloud Solution Architect",
            "BetaCo",
            "https://example.com/2",
            "Design Python and Kubernetes cloud platforms for enterprise customers.",
            location="Remote - US",
            remote=True,
        )
        self.store.upsert_jobs([preview_job])
        weights = asdict(self.store.load_profile())["scoring_weights"]
        weights = {**weights, "required_skills": 35, "role_skills": 20}

        status, uncached_payload = self.request(
            "POST", "/api/scoring-preview", {"weights": weights, "limit": 5}
        )
        self.assertEqual(status, 200)
        self.assertFalse(uncached_payload["current_snapshot_reused"])
        self.assertFalse(uncached_payload["candidate_set_reused"])

        status, _ = self.request("GET", "/api/jobs?status=new&limit=50")
        self.assertEqual(status, 200)

        status, payload = self.request(
            "POST", "/api/scoring-preview", {"weights": weights, "limit": 5}
        )

        self.assertEqual(status, 200)
        self.assertFalse(payload["persisted"])
        self.assertTrue(payload["current_snapshot_reused"])
        self.assertTrue(payload["candidate_set_reused"])
        self.assertEqual(payload["queue_size"], 1)
        self.assertEqual(payload["rows"][0]["job_key"], preview_job.key)
        self.assertNotEqual(
            payload["proposed_weights"],
            asdict(self.store.load_profile())["scoring_weights"],
        )

        self.store.upsert_jobs([
            Job(
                "test", "3", "Platform Architect", "GammaCo",
                "https://example.com/3", "Python", location="Remote - US",
                remote=True,
            )
        ])
        status, refreshed_payload = self.request(
            "POST", "/api/scoring-preview", {"weights": weights, "limit": 5}
        )
        self.assertEqual(status, 200)
        self.assertFalse(refreshed_payload["candidate_set_reused"])
        self.assertEqual(refreshed_payload["queue_size"], 2)

        status, stats = self.request("GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(stats["candidate_cache"]["hits"], 2)
        self.assertEqual(stats["candidate_cache"]["misses"], 2)
        self.assertEqual(stats["candidate_cache"]["entries"], 2)
        self.assertEqual(stats["candidate_cache"]["cached_jobs"], 3)
        self.assertGreater(stats["candidate_cache"]["estimated_bytes"], 0)
        self.assertEqual(stats["candidate_cache"]["max_bytes"], 32 * 1024 * 1024)

        previous_limit = os.environ.get("GET_A_JOB_CANDIDATE_CACHE_MAX_MB")
        os.environ["GET_A_JOB_CANDIDATE_CACHE_MAX_MB"] = "1"
        try:
            self.store.upsert_jobs([
                Job(
                    "test", "medium", "Medium Architect", "DeltaCo",
                    "https://example.com/medium", "Python " * 60_000,
                    location="Remote - US", remote=True,
                )
            ])
            status, _ = self.request(
                "POST", "/api/scoring-preview", {"weights": weights, "limit": 5}
            )
            self.assertEqual(status, 200)
            self.store.upsert_jobs([
                Job(
                    "test", "medium-two", "Medium Architect II", "EchoCo",
                    "https://example.com/medium-two", "Python " * 60_000,
                    location="Remote - US", remote=True,
                )
            ])
            status, _ = self.request(
                "POST", "/api/scoring-preview", {"weights": weights, "limit": 5}
            )
            self.assertEqual(status, 200)
            self.store.upsert_jobs([
                Job(
                    "test", "large", "Large Architect", "DeltaCo",
                    "https://example.com/large", "Python " * 300_000,
                    location="Remote - US", remote=True,
                )
            ])
            status, _ = self.request(
                "POST", "/api/scoring-preview", {"weights": weights, "limit": 5}
            )
            self.assertEqual(status, 200)
            status, capped_stats = self.request("GET", "/api/stats")
            self.assertEqual(status, 200)
            self.assertEqual(capped_stats["candidate_cache"]["max_bytes"], 1024 * 1024)
            self.assertGreaterEqual(capped_stats["candidate_cache"]["evictions"], 1)
            self.assertGreaterEqual(capped_stats["candidate_cache"]["skips"], 1)
        finally:
            if previous_limit is None:
                os.environ.pop("GET_A_JOB_CANDIDATE_CACHE_MAX_MB", None)
            else:
                os.environ["GET_A_JOB_CANDIDATE_CACHE_MAX_MB"] = previous_limit

        status, payload = self.request(
            "POST", "/api/scoring-preview", {"weights": {"required_skills": 100}}
        )
        self.assertEqual(status, 400)
        self.assertIn("seven documented components", payload["error"])

    def test_jobs_endpoint_filters_company_and_keeps_distinct_roles(self):
        self.store.upsert_jobs([
            Job(
                "test", "company-1", "Platform Architect", "Example",
                "https://example.com/company-1", "Python", remote=True,
            ),
            Job(
                "test", "company-2", "Solution Architect", "Example",
                "https://example.com/company-2", "Python", remote=True,
            ),
            Job(
                "test", "other", "Enterprise Architect", "Other",
                "https://example.com/other", "Python", remote=True,
            ),
        ])

        status, payload = self.request(
            "GET", "/api/jobs?status=new&limit=10&company=Example"
        )

        self.assertEqual(status, 200)
        self.assertEqual(len(payload["jobs"]), 2)
        self.assertEqual(
            {entry["job"]["company"] for entry in payload["jobs"]},
            {"Example"},
        )

        status, payload = self.request(
            "GET", f"/api/jobs?company={'x' * 121}"
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "company filter is too long")
