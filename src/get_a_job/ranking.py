from __future__ import annotations

import re

from get_a_job.matching import score_job
from get_a_job.learning import DecisionSignals, apply_learning
from get_a_job.models import CandidateProfile, Job, MatchResult


def _role_key(job: Job) -> tuple[str, str]:
    title = re.sub(r"\b(remote|hybrid|west|east|central|us|usa)\b", "", job.title.lower())
    title = re.sub(r"[^a-z0-9]+", " ", title).strip()
    return job.company.lower().strip(), title


def _preselection_signal(profile: CandidateProfile, job: Job) -> int:
    """Cheaply identify likely matches before running the detailed matcher.

    Public ATS descriptions can be very large.  The dashboard only needs the best
    small set, so reserve the more expensive, boundary-aware scoring for jobs that
    have at least some title, skill, or industry signal.
    """
    title = job.title.lower()
    text = f"{title}\n{job.description}\n{job.company}\n{job.location}".lower()
    title_hits = sum(target.lower() in title for target in profile.target_titles)
    priority_hits = sum(target.lower() in title for target in profile.title_priorities)
    skill_hits = sum(
        any(term.lower() in text for term in [skill, *profile.skill_aliases.get(skill, [])])
        for skill in profile.skills
    )
    industry_hits = sum(
        industry.lower() in f"{job.company}\n{job.title}".lower()
        for industry in profile.industries
    )
    return title_hits * 100 + priority_hits * 100 + skill_hits * 10 + industry_hits


def shortlist(
    profile: CandidateProfile,
    jobs: list[Job],
    limit: int = 10,
    per_company: int = 1,
    decision_signals: DecisionSignals | None = None,
    eligibility_prevalidated: bool = False,
) -> list[tuple[MatchResult, Job]]:
    """Rank eligible jobs, retaining the best regional variant and limiting company repetition."""
    # Apply the inexpensive hard filters first. Otherwise, high-signal foreign
    # roles can consume the preselection window and hide eligible US roles.
    if len(jobs) > 500:
        eligible_jobs = jobs if eligibility_prevalidated else [
            job for job in jobs
            if score_job(
                profile, job, include_evidence=False, include_details=False,
                eligibility_only=True,
            ).eligible
        ]
        ranked_preselection = sorted(
            ((_preselection_signal(profile, job), job) for job in eligible_jobs),
            key=lambda item: item[0],
            reverse=True,
        )
        candidate_limit = max(limit * 6, 300)
        candidates_per_company = max(per_company * 5, 5)
        preselected: list[Job] = []
        preselected_company_counts: dict[str, int] = {}
        for _, job in ranked_preselection:
            company = job.company.lower().strip()
            if preselected_company_counts.get(company, 0) >= candidates_per_company:
                continue
            preselected.append(job)
            preselected_company_counts[company] = preselected_company_counts.get(company, 0) + 1
            if len(preselected) == candidate_limit:
                break
        jobs = preselected
    def score(job: Job, detailed: bool) -> MatchResult:
        result = score_job(profile, job, include_evidence=detailed, include_details=detailed)
        return apply_learning(result, job, decision_signals, detailed) if decision_signals else result

    candidates = [(score(job, detailed=False), job) for job in jobs]
    candidates.sort(key=lambda item: (item[0].eligible, item[0].score, item[1].posted_at or ""), reverse=True)
    chosen: list[tuple[MatchResult, Job]] = []
    seen_roles: set[tuple[str, str]] = set()
    company_counts: dict[str, int] = {}
    for result, job in candidates:
        if not result.eligible:
            continue
        role = _role_key(job)
        company = job.company.lower().strip()
        if role in seen_roles or company_counts.get(company, 0) >= per_company:
            continue
        seen_roles.add(role)
        company_counts[company] = company_counts.get(company, 0) + 1
        chosen.append((score(job, detailed=True), job))
        if len(chosen) == limit:
            break
    return chosen
