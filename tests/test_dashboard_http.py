import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from get_a_job.dashboard_server import DashboardHandler
from get_a_job.dashboard_services import ApplicationService, TailoringService
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
        DashboardHandler.applications = ApplicationService(self.store)
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
