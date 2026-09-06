import unittest

from get_a_job.models import CandidateProfile, Job
from get_a_job.ranking import shortlist


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.profile = CandidateProfile(
            name="Candidate",
            target_titles=["technical program manager"],
            skills=["Python"],
            remote_ok=True,
        )

    def test_shortlist_keeps_one_company_and_role_variant(self):
        jobs = [
            Job("source", "1", "Technical Program Manager - West", "Acme", "https://x/1", "Python", remote=True),
            Job("source", "2", "Technical Program Manager - East", "Acme", "https://x/2", "Python", remote=True),
            Job("source", "3", "Technical Program Manager", "Beta", "https://x/3", "Python", remote=True),
        ]
        ranked = shortlist(self.profile, jobs, limit=10, per_company=1)
        self.assertEqual([job.company for _, job in ranked], ["Acme", "Beta"])

    def test_shortlist_excludes_ineligible_jobs(self):
        job = Job("source", "1", "Technical Program Manager", "Acme", "https://x/1", "Python", location="Miami")
        profile = CandidateProfile(
            name="Candidate", target_titles=["technical program manager"], skills=["Python"], locations=["Boise"], remote_ok=False
        )
        self.assertEqual(shortlist(profile, [job]), [])

    def test_large_queue_filters_ineligible_roles_before_preselection(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["technical program manager"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["US"],
        )
        foreign_roles = [
            Job(
                "source",
                str(index),
                "Technical Program Manager",
                f"Foreign Company {index}",
                f"https://x/{index}",
                "Python",
                location="Remote - Canada",
                remote=True,
                country="CA",
            )
            for index in range(599)
        ]
        eligible = Job(
            "source",
            "eligible",
            "Operations Leader",
            "US Company",
            "https://x/eligible",
            "Program delivery",
            location="Remote - US",
            remote=True,
            country="US",
        )

        ranked = shortlist(profile, [*foreign_roles, eligible], limit=10)

        self.assertEqual([job.key for _, job in ranked], [eligible.key])
