import tempfile
import unittest
from pathlib import Path

from get_a_job.dashboard_services import ApplicationService, TailoringService
from get_a_job.models import CandidateProfile, Job
from get_a_job.storage import Store


class DashboardServiceTests(unittest.TestCase):
    def test_application_service_exposes_current_applied_roles_only(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.db")
            job = Job("test", "1", "Architect", "Acme", "https://example.com", "Python")
            store.upsert_jobs([job])
            service = ApplicationService(store)
            store.set_review(job.key, "applied")
            service.save_followup(job.key, "2026-09-10", "Check status")
            self.assertEqual(service.applications()[0]["follow_up_date"], "2026-09-10")
            store.set_review(job.key, "rejected")
            self.assertEqual(service.applications(), [])

    def test_tailoring_plan_preserves_selected_evidence_and_detects_resume_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "jobs.db")
            store.save_profile(CandidateProfile("Candidate", ["AI Architect"], ["Python", "AI Architecture"]))
            job = Job("test", "2", "AI Architect", "Acme", "https://example.com", "Required: Python and AI Architecture")
            store.upsert_jobs([job])
            config = root / "config"
            config.mkdir()
            resume_text = """PROFESSIONAL SUMMARY\nTechnology leader. Built AI architecture with Python.\nCORE EXPERTISE\nPython | AI Architecture\nPROFESSIONAL EXPERIENCE\n• Built AI architecture with Python.\n"""
            (config / "resume.private.txt").write_text(resume_text, encoding="utf-8")
            (config / "resume.private.docx").write_bytes(b"placeholder DOCX")
            service = TailoringService(store, config)

            draft, returned_job, resume_path = service.create_draft(job.key)
            selected = service.select_experience_evidence(draft, ["Built AI architecture with Python."])
            approved = service.approve(selected, returned_job, resume_path)
            plan, plan_job = service.approved_plan(str(approved["plan_id"]), job.key)

            self.assertEqual(plan_job.key, job.key)
            self.assertEqual(plan["selected_experience_bullets"], ["Built AI architecture with Python."])
            (config / "resume.private.txt").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "resume changed"):
                service.approved_plan(str(approved["plan_id"]), job.key)


if __name__ == "__main__":
    unittest.main()
