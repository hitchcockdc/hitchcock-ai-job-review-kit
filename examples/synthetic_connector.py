"""Minimal connector example using only synthetic, public-feed-shaped data.

This example is intentionally not registered in the production connector map. It shows
the normalization contract without adding another live network dependency.
"""
from __future__ import annotations

from typing import Any, Callable

from get_a_job.locations import countries_from_text, primary_country, regions_from_text
from get_a_job.models import Job
from get_a_job.text import plain_text

JsonFetcher = Callable[[str], dict[str, Any] | list[Any]]


def fetch_synthetic(source: dict[str, Any], fetch: JsonFetcher) -> list[Job]:
    """Normalize a small public JSON feed into the shared Job model."""
    endpoint = str(source.get("endpoint", "")).strip()
    company = str(source.get("company", "")).strip()
    slug = str(source.get("slug", "")).strip()
    if not endpoint.startswith("https://") or not company or not slug:
        raise ValueError("synthetic source requires an HTTPS endpoint, company, and slug")

    payload = fetch(endpoint)
    if not isinstance(payload, dict) or not isinstance(payload.get("positions"), list):
        raise ValueError("synthetic response must contain a positions list")

    jobs: list[Job] = []
    for item in payload["positions"]:
        if not isinstance(item, dict) or not item.get("id") or not item.get("title"):
            continue
        location = plain_text(item.get("location"))
        countries = countries_from_text(location)
        jobs.append(
            Job(
                source=f"synthetic:{slug}",
                external_id=str(item["id"]),
                title=plain_text(item["title"]),
                company=company,
                url=str(item.get("url", "")),
                description=plain_text(item.get("description")),
                location=location,
                remote="remote" in location.lower(),
                country=primary_country(countries),
                countries=countries,
                regions=regions_from_text(location),
                employment_type=plain_text(item.get("employment_type")),
                posted_at=str(item.get("posted_at") or "") or None,
            )
        )
    return jobs
