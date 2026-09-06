from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from get_a_job.text import plain_text


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("expected a list of strings")
    return [item.strip() for item in value if item.strip()]


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    target_titles: list[str]
    skills: list[str]
    headline: str = ""
    industries: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_ok: bool = True
    minimum_salary: int | None = None
    employment_types: list[str] = field(default_factory=list)
    max_travel_percentage: int | None = None
    title_priorities: list[str] = field(default_factory=list)
    eligible_countries: list[str] = field(default_factory=list)
    work_authorized_countries: list[str] = field(default_factory=list)
    consider_sponsorship_roles: bool = True
    excluded_terms: list[str] = field(default_factory=list)
    skill_aliases: dict[str, list[str]] = field(default_factory=dict)
    experience_summary: dict[str, Any] = field(default_factory=dict)
    evidence_inventory: list[dict[str, Any]] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    preferences_to_confirm: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    source_date: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateProfile":
        return cls(
            name=str(data.get("name", "Candidate")).strip(),
            target_titles=_strings(data.get("target_titles")),
            skills=_strings(data.get("skills")),
            headline=str(data.get("headline", "")).strip(),
            industries=_strings(data.get("industries")),
            locations=_strings(data.get("locations")),
            remote_ok=bool(data.get("remote_ok", True)),
            minimum_salary=data.get("minimum_salary"),
            employment_types=_strings(data.get("employment_types")),
            max_travel_percentage=data.get("max_travel_percentage"),
            title_priorities=_strings(data.get("title_priorities")),
            eligible_countries=_strings(data.get("eligible_countries")),
            work_authorized_countries=_strings(
                data.get("work_authorized_countries")
            ),
            consider_sponsorship_roles=bool(
                data.get("consider_sponsorship_roles", True)
            ),
            excluded_terms=_strings(data.get("excluded_terms")),
            skill_aliases={
                str(skill): _strings(aliases)
                for skill, aliases in dict(data.get("skill_aliases", {})).items()
            },
            experience_summary=dict(data.get("experience_summary", {})),
            evidence_inventory=list(data.get("evidence_inventory", [])),
            education=_strings(data.get("education")),
            certifications=_strings(data.get("certifications")),
            preferences_to_confirm=dict(data.get("preferences_to_confirm", {})),
            source=str(data.get("source", "")),
            source_date=str(data.get("source_date", "")),
        )


@dataclass(frozen=True)
class Job:
    source: str
    external_id: str
    title: str
    company: str
    url: str
    description: str
    location: str = ""
    remote: bool = False
    country: str = ""
    countries: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    employment_type: str = ""
    travel_percentage: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    posted_at: str | None = None
    first_seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        required = ("source", "external_id", "title", "company", "url", "description")
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValueError(f"job is missing required fields: {', '.join(missing)}")
        country = str(data.get("country", "")).strip()
        countries = _strings(data.get("countries"))
        return cls(
            source=str(data["source"]),
            external_id=str(data["external_id"]),
            title=str(data["title"]),
            company=str(data["company"]),
            url=str(data["url"]),
            description=plain_text(data["description"]),
            location=str(data.get("location", "")),
            remote=bool(data.get("remote", False)),
            country=country,
            countries=countries or ([country] if country else []),
            regions=_strings(data.get("regions")),
            employment_type=str(data.get("employment_type", "")),
            travel_percentage=data.get("travel_percentage"),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            posted_at=data.get("posted_at"),
            first_seen_at=str(data.get("first_seen_at") or datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class MatchResult:
    score: int
    eligible: bool
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str]
    matched_required_skills: list[str] = field(default_factory=list)
    matched_preferred_skills: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    score_breakdown: dict[str, int] = field(default_factory=dict)
    required_role_skills: list[str] = field(default_factory=list)
    country_verification: str = "not_required"
    buried_role_skills: list[str] = field(default_factory=list)
    matched_role_skill_count: int = 0
    role_skill_count: int = 0
    role_skill_contexts: list[dict[str, str]] = field(default_factory=list)
    authorization_verification: str = "not_configured"
