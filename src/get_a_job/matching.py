from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from get_a_job.locations import (
    countries_from_text,
    eligible_targets_match,
    primary_country,
    regions_from_text,
)
from get_a_job.models import CandidateProfile, Job, MatchResult


# Common concrete capabilities that can be reliably recognized in a role description.
# This list intentionally avoids vague traits (such as "communication") so a red item
# represents a specific capability absent from the candidate profile, not a judgment.
_ROLE_SKILL_TERMS: dict[str, tuple[str, ...]] = {
    "Python": ("Python",), "SQL": ("SQL",), "Java": ("Java",), "JavaScript": ("JavaScript",),
    "TypeScript": ("TypeScript",), "C++": ("C++",), "C#": ("C#",), "Go": ("Golang", "Go"),
    "AWS": ("AWS", "Amazon Web Services"), "Azure": ("Azure", "Microsoft Azure"),
    "GCP": ("GCP", "Google Cloud Platform"), "Docker": ("Docker",), "Kubernetes": ("Kubernetes", "K8s"),
    "Terraform": ("Terraform",), "React": ("React",), "Node.js": ("Node.js", "NodeJS"),
    "Spark": ("Apache Spark", "Spark"), "Airflow": ("Apache Airflow", "Airflow"),
    "Snowflake": ("Snowflake",), "Databricks": ("Databricks",), "Salesforce": ("Salesforce",),
    "Tableau": ("Tableau",), "Power BI": ("Power BI",), "REST APIs": ("REST API", "RESTful API"),
    "GraphQL": ("GraphQL",), "Machine learning": ("machine learning",), "Deep learning": ("deep learning",),
    "LLM": ("LLM", "large language model"), "RAG": ("RAG", "retrieval augmented generation"),
    "Generative AI": ("generative AI",), "AI evaluation": ("AI evaluation", "model evaluation"),
    "Agent architecture": ("agent architecture", "agentic architecture", "agent and MCP architecture"),
    "MCP": ("MCP", "Model Context Protocol"),
    "Identity & access management": ("identity", "identity and access", "identity management", "identity systems"),
    "OAuth": ("OAuth", "OpenID Connect", "OIDC"),
    "CI/CD": ("CI/CD", "continuous integration", "continuous delivery", "continuous deployment"),
    "Infrastructure as code": ("infrastructure as code", "IaC", "CloudFormation"),
    "Observability": ("observability",), "OpenTelemetry": ("OpenTelemetry", "open telemetry"),
    "Prometheus": ("Prometheus",), "Grafana": ("Grafana",), "SSO": ("single sign-on", "SSO"),
    "SAML": ("SAML",), "RBAC": ("RBAC",), "Linux": ("Linux",),
    "PostgreSQL": ("PostgreSQL", "Postgres"), "Redis": ("Redis",), "Kafka": ("Kafka",),
    "Microservices": ("microservices", "microservice"), "Helm": ("Helm",),
    "Argo CD": ("Argo CD", "ArgoCD"), "GitHub Actions": ("GitHub Actions",), "Jenkins": ("Jenkins",),
    "MLOps": ("MLOps", "ML Ops"), "Model serving": ("model serving", "inference serving"),
    "Vector databases": ("vector database", "vector DB"), "API gateway": ("API gateway",),
    "Agile": ("Agile",), "Scrum": ("Scrum",), "Jira": ("Jira",),
}


def _alternation_pattern(terms: Iterable[str]) -> re.Pattern[str]:
    """Compile one boundary-aware matcher for a set of literal terms."""
    alternatives = "|".join(
        re.escape(term) for term in sorted(set(terms), key=len, reverse=True)
    )
    # A lookahead preserves overlapping phrases. For example, matching
    # "agent and MCP architecture" must not hide the nested "MCP" skill.
    return re.compile(
        rf"(?=(?<!\w)({alternatives})(?!\w))" if alternatives else r"(?!)"
    )


_ROLE_SKILLS_BY_TERM: dict[str, list[str]] = {}
for _role_skill, _role_terms in _ROLE_SKILL_TERMS.items():
    for _role_term in _role_terms:
        _ROLE_SKILLS_BY_TERM.setdefault(_role_term.lower(), []).append(_role_skill)
_ROLE_SKILL_PATTERN = _alternation_pattern(_ROLE_SKILLS_BY_TERM)

_REQUIREMENT_MARKERS = r"required|must have|minimum qualifications|qualifications"
_CONTEXT_MARKERS = r"hands[- ]on|technical depth|experience (?:with|across|building)|expertise|proficien|deep understanding|strong knowledge|ownership"
_NO_SPONSORSHIP_PATTERNS = (
    r"\b(?:do|does|will|can) not (?:offer|provide|support) (?:employment |visa )?sponsorship\b",
    r"\b(?:unable|not able) to (?:offer|provide|support) (?:employment |visa )?sponsorship\b",
    r"\b(?:we|the company|the employer) (?:are |is )?"
    r"(?:unable to|cannot|can't|will not) "
    r"(?:sponsor|transfer|take over sponsorship)\b",
    r"\bno (?:employment |visa )?sponsorship\b",
    r"\bnot eligible for (?:employment |visa )?sponsorship\b",
    r"\bwithout (?:the need for )?"
    r"(?:(?:current or future|now or in the future|current|future) )?"
    r"(?:employment |employer |visa )?sponsorship\b",
    r"\bwithout (?:now or in the future|currently or in the future) "
    r"requiring (?:employment |employer |visa )?sponsorship\b",
    r"\bwithout (?:employment |employer |visa )?sponsorship "
    r"(?:now or in the future|currently or in the future)\b",
)
_SPONSORSHIP_AVAILABLE_PATTERNS = (
    r"\b(?:employment |immigration |visa )?sponsorship "
    r"(?:(?:is|may be|will be) )?(?:available|considered|offered|provided)\b",
    r"\b(?:we|the company) (?:can|will|may) (?:offer|provide|support) (?:employment |visa )?sponsorship\b",
    r"\b(?:we|the company|the employer) may sponsor\b",
)


def _contains(text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


@lru_cache(maxsize=32)
def _literal_matcher(terms: tuple[str, ...]) -> re.Pattern[str]:
    return _alternation_pattern(term.lower() for term in terms)


def _matched_literals(text: str, terms: list[str]) -> list[str]:
    """Return boundary-aware literal matches after scanning the text once."""
    if not terms:
        return []
    matched = {
        occurrence.group(1)
        for occurrence in _literal_matcher(tuple(terms)).finditer(text.lower())
    }
    return [term for term in terms if term.lower() in matched]


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _sponsorship_policy(description: str) -> str:
    normalized = " ".join(description.lower().split())
    if any(re.search(pattern, normalized) for pattern in _NO_SPONSORSHIP_PATTERNS):
        return "unavailable"
    if any(
        re.search(pattern, normalized)
        for pattern in _SPONSORSHIP_AVAILABLE_PATTERNS
    ):
        return "available"
    return "unknown"


def _skill_terms(profile: CandidateProfile, skill: str) -> list[str]:
    return [skill, *profile.skill_aliases.get(skill, [])]


def _matches_skill(profile: CandidateProfile, text: str, skill: str) -> bool:
    return any(_contains(text, term) for term in _skill_terms(profile, skill))


@lru_cache(maxsize=16)
def _profile_skill_matcher(
    signature: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[re.Pattern[str], dict[str, tuple[str, ...]]]:
    skills_by_term: dict[str, list[str]] = {}
    for skill, terms in signature:
        for term in terms:
            skills_by_term.setdefault(term.lower(), []).append(skill)
    return (
        _alternation_pattern(skills_by_term),
        {term: tuple(skills) for term, skills in skills_by_term.items()},
    )


def _matched_profile_skills(profile: CandidateProfile, text: str) -> list[str]:
    """Find every matched profile skill with one pass over the role text."""
    signature = tuple(
        (skill, tuple(_skill_terms(profile, skill))) for skill in profile.skills
    )
    pattern, skills_by_term = _profile_skill_matcher(signature)
    matched = {
        skill
        for occurrence in pattern.finditer(text.lower())
        for skill in skills_by_term[occurrence.group(1)]
    }
    return [skill for skill in profile.skills if skill in matched]


def _sentences(text: str) -> Iterable[str]:
    return (sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if sentence.strip())


def _classified_skills(profile: CandidateProfile, description: str) -> tuple[list[str], list[str]]:
    required: list[str] = []
    preferred: list[str] = []
    for sentence in _sentences(description):
        lowered = sentence.lower()
        target = (
            required
            if re.search(r"\b(required|must have|minimum qualifications|qualifications)\b", lowered)
            else preferred
            if re.search(r"\b(preferred|nice to have|bonus)\b", lowered)
            else None
        )
        if target is not None:
            target.extend(
                skill for skill in profile.skills if skill not in target and _matches_skill(profile, sentence, skill)
            )
    return required, preferred


def _role_requirement_skills(description: str, required_only: bool = False) -> list[str]:
    """Find concrete skills called out in requirement-style role text."""
    markers = _REQUIREMENT_MARKERS
    if not required_only:
        markers += r"|preferred|nice to have|bonus"
    requirement_text = " ".join(
        sentence for sentence in _sentences(description)
        if re.search(rf"\b({markers})\b", sentence.lower())
    )
    return _description_role_skills(requirement_text)


def _description_role_skills(description: str) -> list[str]:
    """Find concrete technical capabilities mentioned anywhere in a role description."""
    matched = {
        skill
        for occurrence in _ROLE_SKILL_PATTERN.finditer(description.lower())
        for skill in _ROLE_SKILLS_BY_TERM[occurrence.group(1)]
    }
    return [skill for skill in _ROLE_SKILL_TERMS if skill in matched]


def _role_skill_contexts(description: str, role_skills: list[str]) -> list[dict[str, str]]:
    """Explain where each role capability was found and how strongly it is stated."""
    wanted = set(role_skills)
    first_context: dict[str, str] = {}
    for sentence in _sentences(description):
        for skill in _description_role_skills(sentence):
            if skill in wanted and skill not in first_context:
                first_context[skill] = sentence

    contexts: list[dict[str, str]] = []
    for skill in role_skills:
        sentence = first_context.get(skill, "")
        lowered = sentence.lower()
        confidence = (
            "high" if re.search(rf"\b({_REQUIREMENT_MARKERS})\b", lowered)
            else "medium" if re.search(rf"\b({_CONTEXT_MARKERS})\b", lowered)
            else "low"
        )
        contexts.append({"skill": skill, "confidence": confidence, "context": sentence[:280]})
    return contexts


def _weighted_role_coverage(matched_role_skills: list[str], contexts: list[dict[str, str]]) -> float:
    weights = {"high": 1.0, "medium": 0.65, "low": 0.35}
    total = sum(weights.get(context["confidence"], 0.35) for context in contexts)
    matched = sum(
        weights.get(context["confidence"], 0.35)
        for context in contexts if context["skill"] in matched_role_skills
    )
    return matched / total if total else 0.0


def _matched_role_skills(profile: CandidateProfile, role_skills: list[str]) -> list[str]:
    """Return role-language skills that the candidate profile covers, including aliases."""
    return [
        role_skill for role_skill in role_skills
        if any(_matches_skill(profile, role_skill, profile_skill) for profile_skill in profile.skills)
    ]


def _resume_evidence(profile: CandidateProfile, skills: list[str]) -> list[str]:
    evidence: list[str] = []
    for entry in profile.evidence_inventory:
        for statement in entry.get("evidence", []):
            if any(_matches_skill(profile, str(statement), skill) for skill in skills):
                evidence.append(str(statement))
                if len(evidence) == 3:
                    return evidence
    return evidence


def score_job(
    profile: CandidateProfile,
    job: Job,
    include_evidence: bool = True,
    include_details: bool = True,
    eligibility_only: bool = False,
) -> MatchResult:
    title_and_description = f"{job.title}\n{job.description}"
    all_text = f"{title_and_description}\n{job.company}\n{job.location}"
    excluded = _matched_literals(all_text, profile.excluded_terms)
    remote_match = job.remote and profile.remote_ok
    local_match = bool(profile.locations) and any(
        _contains(job.location, place) for place in profile.locations
    )
    location_ok = remote_match or local_match
    if not profile.remote_ok and not profile.locations:
        location_ok = True

    salary_ok = True
    if profile.minimum_salary and job.salary_max is not None:
        salary_ok = job.salary_max >= profile.minimum_salary

    employment_ok = True
    if profile.employment_types and job.employment_type:
        job_type = _normalized(job.employment_type)
        employment_ok = any(_normalized(value) == job_type for value in profile.employment_types)

    travel_ok = True
    if profile.max_travel_percentage is not None and job.travel_percentage is not None:
        travel_ok = job.travel_percentage <= profile.max_travel_percentage

    effective_countries = list(
        dict.fromkeys(
            [
                *job.countries,
                *([job.country] if job.country else []),
                *countries_from_text(job.location),
            ]
        )
    )
    effective_regions = list(
        dict.fromkeys([*job.regions, *regions_from_text(job.location)])
    )
    target_match = eligible_targets_match(
        profile.eligible_countries, effective_countries, effective_regions
    )
    country_ok = not profile.eligible_countries or target_match is not False
    effective_country = primary_country(effective_countries)
    effective_scope = ", ".join([*effective_countries, *effective_regions])
    country_verification = (
        "not_required" if not profile.eligible_countries
        else "ineligible" if target_match is False
        else "verified" if target_match is True or local_match
        else "unknown"
    )

    authorization_match = eligible_targets_match(
        profile.work_authorized_countries,
        effective_countries,
        effective_regions,
    )
    sponsorship_policy = "unknown"
    if not profile.work_authorized_countries:
        authorization_verification = "not_configured"
        authorization_ok = True
    elif authorization_match is True:
        authorization_verification = "verified"
        authorization_ok = True
    elif authorization_match is None:
        authorization_verification = "unknown"
        authorization_ok = True
    elif not country_ok or not profile.consider_sponsorship_roles:
        authorization_verification = "ineligible"
        authorization_ok = False
    else:
        sponsorship_policy = _sponsorship_policy(job.description)
        authorization_ok = sponsorship_policy != "unavailable"
        authorization_verification = (
            "sponsorship_required" if authorization_ok else "ineligible"
        )

    eligible = (
        not excluded
        and location_ok
        and salary_ok
        and employment_ok
        and travel_ok
        and country_ok
        and authorization_ok
    )
    if eligibility_only:
        return MatchResult(
            score=0,
            eligible=eligible,
            matched_skills=[],
            missing_skills=[],
            reasons=[],
            country_verification=country_verification,
            authorization_verification=authorization_verification,
        )

    title_matches = [title for title in profile.target_titles if _contains(job.title, title)]
    priority_matches = [title for title in profile.title_priorities if _contains(job.title, title)]
    matched_skills = _matched_profile_skills(profile, title_and_description)
    required_role_skills = _role_requirement_skills(job.description, required_only=True)
    requirement_role_skills = _role_requirement_skills(job.description)
    role_skills = _description_role_skills(job.description)
    buried_role_skills = [skill for skill in role_skills if skill not in requirement_role_skills]
    matched_role_skills = _matched_role_skills(profile, role_skills)
    matched_role_skill_set = set(matched_role_skills)
    missing_skills = [skill for skill in role_skills if skill not in matched_role_skill_set]
    matched_required_role_skills = [
        skill for skill in required_role_skills if skill in matched_role_skill_set
    ]
    role_skill_contexts = _role_skill_contexts(job.description, role_skills)
    # Job descriptions often mention many verticals as examples. Restrict industry matches
    # to the company and title to avoid promoting incidental references.
    industry_text = f"{job.company}\n{job.title}"
    industry_matches = [industry for industry in profile.industries if _contains(industry_text, industry)]
    # The score deliberately answers two separate questions:
    # 1) Does the candidate cover the concrete capabilities requested by this role?
    # 2) Does the role meet the candidate's stated title, industry, and work preferences?
    # Role-skill coverage uses the role as its denominator, so adding an unrelated
    # skill to the profile can never lower an otherwise good match.
    if role_skills:
        role_skill_score = round(25 * _weighted_role_coverage(matched_role_skills, role_skill_contexts))
        required_skill_score = (
            round(30 * len(matched_required_role_skills) / len(required_role_skills))
            if required_role_skills else min(30, 10 * len(matched_role_skills))
        )
    else:
        # Some postings omit a qualifications section. Preserve useful signal from
        # direct profile-skill mentions without penalizing a broader profile.
        role_skill_score = min(25, 8 * len(matched_skills))
        required_skill_score = min(30, 10 * len(matched_skills))

    title_score = min(20, 20 * len(title_matches))
    industry_score = min(5, 5 * len(industry_matches))
    location_score = 5 if location_ok else 0
    preference_score = 5 if (
        salary_ok and employment_ok and travel_ok and country_ok
        and country_verification != "unknown"
        and authorization_verification in {"verified", "not_configured"}
    ) else 0
    priority_score = 10 if priority_matches else 0
    score = min(
        100,
        required_skill_score + role_skill_score + title_score + industry_score
        + location_score + preference_score + priority_score,
    )
    score_breakdown = {
        "required_skills": required_skill_score,
        "role_skills": role_skill_score,
        "title_target": title_score,
        "work_location": location_score,
        "preferences": preference_score,
        "priority": priority_score,
        "industry": industry_score,
    }
    if not eligible:
        score = min(score, 39)
        score_breakdown["eligibility_cap"] = score

    if not include_details:
        return MatchResult(
            score, eligible, matched_skills, missing_skills, [],
            score_breakdown=score_breakdown, required_role_skills=required_role_skills,
            country_verification=country_verification,
            authorization_verification=authorization_verification,
            buried_role_skills=buried_role_skills,
            matched_role_skill_count=len(matched_role_skills),
            role_skill_count=len(role_skills),
            role_skill_contexts=role_skill_contexts,
        )

    reasons: list[str] = []
    eligible_label = " / ".join(profile.eligible_countries) or "configured locations"
    if excluded:
        reasons.append(f"excluded term: {', '.join(excluded)}")
    if not location_ok:
        reasons.append("location preference does not match")
    elif remote_match and country_verification == "verified":
        reasons.append(f"work location match: remote ({eligible_label})")
    elif remote_match:
        reasons.append(f"work location match: remote ({eligible_label} eligibility to confirm)")
    elif local_match:
        reasons.append(f"work location match: local ({job.location})")
    if not salary_ok:
        reasons.append("maximum salary is below the configured minimum")
    if not employment_ok:
        reasons.append("employment type does not match")
    if not travel_ok:
        reasons.append("travel requirement exceeds the configured maximum")
    if not country_ok:
        reasons.append(f"work country or region is not eligible: {effective_scope}")
    elif country_verification == "unknown":
        reasons.append(f"work country is not stated; confirm {eligible_label} eligibility")
    authorized_label = " / ".join(profile.work_authorized_countries)
    if authorization_verification == "not_configured":
        reasons.append("work authorization countries are not configured")
    elif authorization_verification == "verified":
        reasons.append(f"work authorization match: {authorized_label}")
    elif authorization_verification == "unknown":
        reasons.append("work authorization cannot be verified without a specific job country")
    elif authorization_verification == "sponsorship_required":
        reasons.append(
            "employer sponsorship appears available"
            if sponsorship_policy == "available"
            else "work authorization is not confirmed; employer sponsorship may be required"
        )
    elif authorization_match is False and country_ok:
        reasons.append(
            "work authorization does not match and the posting says sponsorship is unavailable"
            if sponsorship_policy == "unavailable"
            else "work authorization does not match and sponsorship roles are disabled"
        )

    required_skills, preferred_skills = _classified_skills(profile, job.description)
    matched_required = [skill for skill in matched_skills if skill in required_skills]
    matched_preferred = [skill for skill in matched_skills if skill in preferred_skills]
    evidence = _resume_evidence(profile, matched_skills) if include_evidence else []

    if title_matches:
        reasons.append(f"target title match: {', '.join(title_matches)}")
    if priority_matches:
        reasons.append(f"title priority: {', '.join(priority_matches)}")
    if matched_skills:
        reasons.append(f"matched skills: {', '.join(matched_skills)}")
    if role_skills:
        reasons.append(f"role-skill coverage: {len(matched_role_skills)}/{len(role_skills)}")
    if required_role_skills:
        reasons.append(
            f"required-skill coverage: {len(matched_required_role_skills)}/{len(required_role_skills)}"
        )
    if missing_skills:
        reasons.append(f"role skills not yet in resume: {', '.join(missing_skills)}")
    if matched_required:
        reasons.append(f"matched required skills: {', '.join(matched_required)}")
    if matched_preferred:
        reasons.append(f"matched preferred skills: {', '.join(matched_preferred)}")
    if industry_matches:
        reasons.append(f"industry match: {', '.join(industry_matches)}")
    if evidence:
        reasons.append(f"resume evidence: {evidence[0]}")
    if not reasons:
        reasons.append("no strong evidence match found")

    return MatchResult(
        score=score,
        eligible=eligible,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        reasons=reasons,
        matched_required_skills=matched_required,
        matched_preferred_skills=matched_preferred,
        evidence=evidence,
        score_breakdown=score_breakdown,
        required_role_skills=required_role_skills,
        country_verification=country_verification,
        buried_role_skills=buried_role_skills,
        matched_role_skill_count=len(matched_role_skills),
        role_skill_count=len(role_skills),
        role_skill_contexts=role_skill_contexts,
        authorization_verification=authorization_verification,
    )
