from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from get_a_job.models import Job, MatchResult


_IGNORED_TERMS = {
    "and", "architect", "engineer", "for", "from", "lead", "manager", "of",
    "principal", "senior", "software", "staff", "technical", "the", "to",
}


def _terms(job: Job) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z]{3,}", f"{job.title} {job.company}".lower())
        if term not in _IGNORED_TERMS
    }


@dataclass(frozen=True)
class DecisionSignals:
    positive: Counter[str]
    negative: Counter[str]

    @classmethod
    def from_decisions(cls, decisions: list[tuple[Job, str]]) -> "DecisionSignals":
        positive: Counter[str] = Counter()
        negative: Counter[str] = Counter()
        for job, status in decisions:
            if status in {"saved", "applied"}:
                positive.update(_terms(job))
            elif status == "rejected":
                negative.update(_terms(job))
        return cls(positive, negative)

    def adjustment(self, job: Job) -> tuple[int, list[str]]:
        positives = sum(self.positive[term] for term in _terms(job))
        negatives = sum(self.negative[term] for term in _terms(job))
        adjustment = min(12, positives * 2) - min(15, negatives * 3)
        reasons: list[str] = []
        if positives:
            reasons.append("similar to roles you saved or applied to")
        if negatives:
            reasons.append("similar to roles you rejected")
        return adjustment, reasons

    @property
    def summary(self) -> dict[str, int]:
        return {
            "positive_decision_terms": sum(self.positive.values()),
            "negative_decision_terms": sum(self.negative.values()),
        }

    def filtered(self, ignored: set[str]) -> "DecisionSignals":
        return DecisionSignals(
            Counter({term: count for term, count in self.positive.items() if term not in ignored}),
            Counter({term: count for term, count in self.negative.items() if term not in ignored}),
        )

    def top_terms(self, limit: int = 8) -> dict[str, list[dict[str, object]]]:
        return {
            "positive": [{"term": term, "count": count} for term, count in self.positive.most_common(limit)],
            "negative": [{"term": term, "count": count} for term, count in self.negative.most_common(limit)],
        }


def apply_learning(result: MatchResult, job: Job, signals: DecisionSignals, detailed: bool) -> MatchResult:
    adjustment, learning_reasons = signals.adjustment(job)
    if adjustment == 0:
        return result
    reasons = [*result.reasons, *[f"decision learning: {reason}" for reason in learning_reasons]] if detailed else result.reasons
    breakdown = dict(result.score_breakdown)
    breakdown["decision_learning"] = adjustment
    return MatchResult(
        score=max(0, min(100, result.score + adjustment)),
        eligible=result.eligible,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        reasons=reasons,
        matched_required_skills=result.matched_required_skills,
        matched_preferred_skills=result.matched_preferred_skills,
        evidence=result.evidence,
        score_breakdown=breakdown,
        required_role_skills=result.required_role_skills,
        country_verification=result.country_verification,
        buried_role_skills=result.buried_role_skills,
        matched_role_skill_count=result.matched_role_skill_count,
        role_skill_count=result.role_skill_count,
        role_skill_contexts=result.role_skill_contexts,
        authorization_verification=result.authorization_verification,
    )
