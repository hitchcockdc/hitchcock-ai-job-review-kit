import unittest

from get_a_job.digest import markdown_digest
from get_a_job.models import Job, MatchResult


class DigestTests(unittest.TestCase):
    def test_digest_contains_reviewable_job_details(self):
        job = Job("source", "1", "AI Architect", "Acme", "https://x/1", "Python", remote=True)
        result = MatchResult(80, True, ["Python"], [], ["matched skills: Python"])
        digest = markdown_digest([(result, job)])
        self.assertIn("AI Architect - Acme", digest)
        self.assertIn(job.key, digest)
        self.assertIn("https://x/1", digest)
