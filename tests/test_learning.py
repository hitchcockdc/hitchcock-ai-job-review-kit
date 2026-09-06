import unittest

from get_a_job.learning import DecisionSignals, apply_learning
from get_a_job.models import Job, MatchResult


class LearningTests(unittest.TestCase):
    def test_saved_roles_raise_similar_role_score(self):
        saved = Job("source", "1", "AI Solutions Architect", "Acme", "https://x/1", "Python")
        candidate = Job("source", "2", "Solutions Architect", "Beta", "https://x/2", "Python")
        signals = DecisionSignals.from_decisions([(saved, "saved")])
        result = MatchResult(60, True, [], [], [])
        adjusted = apply_learning(result, candidate, signals, detailed=True)
        self.assertGreater(adjusted.score, result.score)
        self.assertIn("decision learning: similar to roles you saved or applied to", adjusted.reasons)

    def test_rejected_roles_lower_similar_role_score(self):
        rejected = Job("source", "1", "Sales Manager", "Acme", "https://x/1", "Python")
        candidate = Job("source", "2", "Sales Specialist", "Beta", "https://x/2", "Python")
        signals = DecisionSignals.from_decisions([(rejected, "rejected")])
        adjusted = apply_learning(MatchResult(60, True, [], [], []), candidate, signals, detailed=False)
        self.assertLess(adjusted.score, 60)
