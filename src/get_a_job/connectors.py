from __future__ import annotations

import html
import json
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

import certifi

from get_a_job.models import Job
from get_a_job.locations import countries_from_text, primary_country, regions_from_text
from get_a_job.text import plain_text

JsonObject = dict[str, Any] | list[Any]
FetchPayload = JsonObject | str
JsonFetcher = Callable[[str], FetchPayload]


@dataclass(frozen=True)
class SourceFetchResult:
    source_id: str
    jobs: list[Job]
    payload: FetchPayload | None = None
    error: str | None = None


def source_id(source: dict[str, Any]) -> str:
    source_type = str(source.get("type", "")).lower()
    identifier = (
        source.get("board_token")
        or source.get("site")
        or source.get("job_board_name")
        or source.get("company_identifier")
    )
    if not source_type or not identifier:
        raise ValueError("source needs a type and board identifier")
    return f"{source_type}:{identifier}"


def get_json(url: str) -> JsonObject:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "get-a-job/0.1 (+personal job discovery)",
        },
    )
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=30, context=context) as response:
        return json.load(response)


def get_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": "get-a-job/0.1 (+personal job discovery)",
        },
    )
    context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=30, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def _plain(value: Any) -> str:
    return plain_text(value)


def _remote(location: str, description: str = "") -> bool:
    # Descriptions frequently say "not remote" or discuss remote collaboration. Treat
    # location as authoritative and only use description when it labels the role type.
    location_text = location.lower()
    if re.search(r"\b(remote|work from home|distributed)\b", location_text):
        return not bool(re.search(r"\b(not|no)\s+remote\b", location_text))
    return bool(
        re.search(r"\b(location|work)\s*type\s*[:\-]?\s*remote\b", description.lower())
    )


def _location_metadata(value: Any, *, structured: bool = False) -> tuple[str, list[str], list[str]]:
    text = _plain(value)
    countries = countries_from_text(text, structured=structured)
    return primary_country(countries), countries, regions_from_text(text)


def _iso_from_millis(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _greenhouse_employment_type(item: dict[str, Any]) -> str:
    for field in item.get("metadata", []) or []:
        name = str(field.get("name", "")).lower()
        if "employment" in name or "commitment" in name or "job type" in name:
            return _plain(field.get("value"))
    return ""


def fetch_greenhouse(source: dict[str, Any], fetch: JsonFetcher = get_json) -> list[Job]:
    token = quote(str(source["board_token"]), safe="")
    payload = fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    if not isinstance(payload, dict):
        raise ValueError("Greenhouse response must be an object")
    jobs = []
    for item in payload.get("jobs", []):
        description = _plain(item.get("content"))
        location = _plain((item.get("location") or {}).get("name"))
        country, countries, regions = _location_metadata(
            f"{location} {item.get('title', '')}"
        )
        jobs.append(
            Job(
                source=f"greenhouse:{source['board_token']}",
                external_id=str(item["id"]),
                title=_plain(item.get("title")),
                company=str(source["company"]),
                url=str(item.get("absolute_url", "")),
                description=description,
                location=location,
                remote=_remote(location, description),
                country=country,
                countries=countries,
                regions=regions,
                employment_type=_greenhouse_employment_type(item),
                posted_at=item.get("updated_at"),
            )
        )
    return jobs


def fetch_lever(source: dict[str, Any], fetch: JsonFetcher = get_json) -> list[Job]:
    site = quote(str(source["site"]), safe="")
    host = "api.eu.lever.co" if source.get("region") == "eu" else "api.lever.co"
    payload = fetch(f"https://{host}/v0/postings/{site}?mode=json")
    if not isinstance(payload, list):
        raise ValueError("Lever response must be a list")
    jobs = []
    for item in payload:
        categories = item.get("categories") or {}
        location = _plain(categories.get("location"))
        description = " ".join(
            part for part in (_plain(item.get("descriptionPlain")), _plain(item.get("additionalPlain"))) if part
        )
        country, countries, regions = _location_metadata(
            f"{location} {item.get('text', '')}"
        )
        jobs.append(
            Job(
                source=f"lever:{source['site']}",
                external_id=str(item["id"]),
                title=_plain(item.get("text")),
                company=str(source["company"]),
                url=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
                description=description,
                location=location,
                remote=_remote(location, description),
                country=country,
                countries=countries,
                regions=regions,
                employment_type=_plain(categories.get("commitment")),
                posted_at=_iso_from_millis(item.get("createdAt")),
            )
        )
    return jobs


def _ashby_salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    compensation = item.get("compensation") or {}
    components = compensation.get("summaryComponents") or []
    salaries = [
        component
        for component in components
        if component.get("compensationType") == "Salary"
        and component.get("interval") == "1 YEAR"
        and component.get("currencyCode") == "USD"
    ]
    if not salaries:
        return None, None
    minimums = [value for component in salaries if (value := component.get("minValue")) is not None]
    maximums = [value for component in salaries if (value := component.get("maxValue")) is not None]
    return (int(min(minimums)) if minimums else None, int(max(maximums)) if maximums else None)


def fetch_ashby(source: dict[str, Any], fetch: JsonFetcher = get_json) -> list[Job]:
    board = quote(str(source["job_board_name"]), safe="")
    payload = fetch(
        f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    )
    if not isinstance(payload, dict):
        raise ValueError("Ashby response must be an object")
    jobs = []
    for item in payload.get("jobs", []):
        if item.get("isListed") is False:
            continue
        location = _plain(item.get("location"))
        address = item.get("address") or {}
        postal_address = address.get("postalAddress") or {}
        structured_country = postal_address.get("addressCountry") or address.get("addressCountry")
        country, countries, regions = _location_metadata(
            structured_country or f"{location} {item.get('title', '')}",
            structured=bool(structured_country),
        )
        description = _plain(item.get("descriptionPlain") or item.get("descriptionHtml"))
        salary_min, salary_max = _ashby_salary(item)
        url = str(item.get("jobUrl") or item.get("applyUrl") or "")
        external_id = str(item.get("id") or url.rstrip("/").rsplit("/", 1)[-1])
        jobs.append(
            Job(
                source=f"ashby:{source['job_board_name']}",
                external_id=external_id,
                title=_plain(item.get("title")),
                company=str(source["company"]),
                url=url,
                description=description,
                location=location,
                remote=_remote(location, description),
                country=country,
                countries=countries,
                regions=regions,
                employment_type=_plain(item.get("employmentType")),
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=item.get("publishedAt"),
            )
        )
    return jobs


def _smartrecruiters_description(item: dict[str, Any]) -> str:
    job_ad = item.get("jobAd") or {}
    if not isinstance(job_ad, dict):
        raise ValueError("SmartRecruiters posting contained an invalid job ad")
    sections = job_ad.get("sections") or {}
    if not isinstance(sections, dict):
        raise ValueError("SmartRecruiters posting contained invalid job-ad sections")
    labels = {
        "companyDescription": "Company description",
        "jobDescription": "Job description",
        "qualifications": "Qualifications",
        "additionalInformation": "Additional information",
    }
    content = []
    for key in labels:
        section = sections.get(key) or {}
        if not isinstance(section, dict):
            continue
        text = _plain(section.get("text"))
        if text:
            content.append(f"{_plain(section.get('title')) or labels[key]}: {text}")
    return " ".join(content)


def _smartrecruiters_salary(item: dict[str, Any]) -> tuple[int | None, int | None]:
    compensation = item.get("compensation") or {}
    if not isinstance(compensation, dict):
        return None, None
    period = str(compensation.get("period", "")).upper()
    if str(compensation.get("currency", "")).upper() != "USD" or period not in {
        "ANNUAL",
        "ANNUALLY",
        "YEAR",
        "YEARLY",
    }:
        return None, None

    def amount(name: str) -> int | None:
        try:
            value = compensation.get(name)
            if isinstance(value, bool):
                return None
            return int(float(value)) if value is not None else None
        except (TypeError, ValueError, OverflowError):
            return None

    return amount("min"), amount("max")


def fetch_smartrecruiters(
    source: dict[str, Any], fetch: JsonFetcher = get_json
) -> list[Job]:
    """Normalize one company's unauthenticated SmartRecruiters public postings."""
    identifier = quote(str(source["company_identifier"]), safe="")
    requested_max = source.get("max_postings", 100)
    if not isinstance(requested_max, int) or isinstance(requested_max, bool):
        raise ValueError("SmartRecruiters max_postings must be a whole number")
    max_postings = min(max(requested_max, 1), 100)
    base = f"https://api.smartrecruiters.com/v1/companies/{identifier}/postings"
    payload = fetch(
        f"{base}?limit={max_postings}&offset=0&destination=PUBLIC"
    )
    if not isinstance(payload, dict):
        raise ValueError("SmartRecruiters response must be an object")
    postings = payload.get("content", [])
    if not isinstance(postings, list):
        raise ValueError("SmartRecruiters response contained invalid postings")

    jobs = []
    for summary in postings[:max_postings]:
        if not isinstance(summary, dict):
            continue
        posting_id = str(summary.get("id") or summary.get("uuid") or "").strip()
        title = _plain(summary.get("name"))
        if not posting_id or not title:
            continue
        detail = fetch(f"{base}/{quote(posting_id, safe='')}")
        if not isinstance(detail, dict):
            raise ValueError("SmartRecruiters posting details must be an object")
        if detail.get("active") is False:
            continue
        title = _plain(detail.get("name")) or title
        company_data = detail.get("company") or summary.get("company") or {}
        company = (
            _plain(company_data.get("name"))
            if isinstance(company_data, dict)
            else ""
        ) or str(source.get("company") or source["company_identifier"])
        location_data = detail.get("location") or summary.get("location") or {}
        if not isinstance(location_data, dict):
            location_data = {}
        location_parts = [
            _plain(location_data.get("city")),
            _plain(location_data.get("region")),
            _plain(location_data.get("country")),
        ]
        location = ", ".join(part for part in location_parts if part)
        remote = bool(location_data.get("remote")) or str(
            detail.get("locationType", "")
        ).upper() == "REMOTE"
        if remote:
            location = f"Remote - {location}" if location else "Remote"
        structured_country = _plain(location_data.get("country"))
        country, countries, regions = _location_metadata(
            structured_country or location,
            structured=bool(structured_country),
        )
        employment = detail.get("typeOfEmployment") or summary.get(
            "typeOfEmployment"
        ) or {}
        salary_min, salary_max = _smartrecruiters_salary(detail)
        url = str(
            detail.get("postingUrl")
            or detail.get("applyUrl")
            or summary.get("ref")
            or f"{base}/{quote(posting_id, safe='')}"
        )
        description = _smartrecruiters_description(detail) or title
        jobs.append(
            Job(
                source=f"smartrecruiters:{source['company_identifier']}",
                external_id=posting_id,
                title=title,
                company=company,
                url=url,
                description=description,
                location=location,
                remote=remote,
                country=country,
                countries=countries,
                regions=regions,
                employment_type=(
                    _plain(employment.get("label"))
                    if isinstance(employment, dict)
                    else _plain(employment)
                ),
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=detail.get("releasedDate") or summary.get("releasedDate"),
            )
        )
    return jobs


def _salary_range(value: Any) -> tuple[int | None, int | None]:
    amounts = [int(amount.replace(",", "")) * 1000 for amount in re.findall(r"\$(\d[\d,]*)K", str(value))]
    if not amounts:
        return None, None
    return min(amounts), max(amounts)


def fetch_yc(source: dict[str, Any], fetch: JsonFetcher = get_text) -> list[Job]:
    """Normalize the public, account-free YC Work at a Startup listing page."""
    path = str(source.get("path") or "/jobs/role/all")
    if not path.startswith("/"):
        path = f"/{path}"
    payload = fetch(f"https://www.ycombinator.com{path}")
    if not isinstance(payload, str):
        raise ValueError("YC response must be HTML")
    match = re.search(r'data-page="(.*?)"', payload, flags=re.DOTALL)
    if not match:
        raise ValueError("YC response did not include public job listings")
    page = json.loads(html.unescape(match.group(1)))
    postings = page.get("props", {}).get("jobPostings", [])
    if not isinstance(postings, list):
        raise ValueError("YC response contained invalid job listings")
    jobs = []
    for item in postings:
        if not isinstance(item, dict) or not item.get("id") or not item.get("title"):
            continue
        location = _plain(item.get("location"))
        salary_min, salary_max = _salary_range(item.get("salaryRange"))
        description = " ".join(
            value
            for value in (
                _plain(item.get("companyOneLiner")),
                _plain(item.get("prettyRole")),
                _plain(item.get("roleSpecificType")),
                "Skills: " + ", ".join(_plain(skill) for skill in item.get("skills", []) if skill),
                _plain(item.get("visa")),
            )
            if value
        )
        role_url = str(item.get("url", ""))
        if role_url.startswith("/"):
            role_url = f"https://www.ycombinator.com{role_url}"
        country, countries, regions = _location_metadata(location, structured=True)
        jobs.append(
            Job(
                source="yc:work-at-a-startup",
                external_id=str(item["id"]),
                title=_plain(item["title"]),
                company=_plain(item.get("companyName")) or "YC startup",
                url=role_url,
                description=description or "YC Work at a Startup listing.",
                location=location,
                remote=_remote(location),
                country=country,
                countries=countries,
                regions=regions,
                employment_type=_plain(item.get("type")),
                salary_min=salary_min,
                salary_max=salary_max,
            )
        )
    return jobs


def fetch_usajobs(source: dict[str, Any], fetch: JsonFetcher = get_json) -> list[Job]:
    """Fetch public federal announcements through the official USAJOBS Search API."""
    api_key = str(source.get("api_key", "")).strip()
    user_agent = str(source.get("user_agent", "")).strip()
    if not api_key or not user_agent:
        raise ValueError("USAJOBS source requires private api_key and user_agent")
    # The standard JSON fetcher cannot attach USAJOBS's required headers. A URL-only
    # test fetcher remains supported for fixture testing.
    if fetch is get_json:
        query = str(source.get("query", "Keyword=Technology&WhoMayApply=public&Fields=full"))
        url = f"https://data.usajobs.gov/api/Search?{query}"
        request = Request(url, headers={"Host": "data.usajobs.gov", "User-Agent": user_agent, "Authorization-Key": api_key})
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=30, context=context) as response:
            payload: FetchPayload = json.load(response)
    else:
        payload = fetch("https://data.usajobs.gov/api/Search")
    if not isinstance(payload, dict):
        raise ValueError("USAJOBS response must be an object")
    items = payload.get("SearchResult", {}).get("SearchResultItems", [])
    if not isinstance(items, list):
        raise ValueError("USAJOBS response contained invalid job listings")
    jobs = []
    for item in items:
        descriptor = item.get("MatchedObjectDescriptor", {}) if isinstance(item, dict) else {}
        if not isinstance(descriptor, dict):
            continue
        position_id = str(descriptor.get("PositionID") or item.get("MatchedObjectId") or "")
        title = _plain(descriptor.get("PositionTitle"))
        if not position_id or not title:
            continue
        locations = descriptor.get("PositionLocation") or []
        location = "; ".join(_plain(value.get("LocationName")) for value in locations if isinstance(value, dict))
        remuneration = descriptor.get("PositionRemuneration") or []
        salaries = [value for value in remuneration if isinstance(value, dict)]
        minimums = [int(float(value["MinimumRange"])) for value in salaries if value.get("MinimumRange")]
        maximums = [int(float(value["MaximumRange"])) for value in salaries if value.get("MaximumRange")]
        jobs.append(Job(
            source="usajobs:search",
            external_id=position_id,
            title=title,
            company=_plain(descriptor.get("OrganizationName")) or "U.S. Federal Government",
            url=str(descriptor.get("PositionURI") or descriptor.get("ApplyURI") or ""),
            description=_plain(descriptor.get("UserArea", {}).get("Details", {}).get("JobSummary")) or title,
            location=location,
            remote=_remote(location),
            country="US",
            countries=["US"],
            employment_type=_plain(descriptor.get("PositionSchedule")),
            salary_min=min(minimums) if minimums else None,
            salary_max=max(maximums) if maximums else None,
            posted_at=descriptor.get("PublicationStartDate"),
        ))
    return jobs


CONNECTORS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "yc": fetch_yc,
    "usajobs": fetch_usajobs,
}


def fetch_sources(sources: list[dict[str, Any]], fetch: JsonFetcher = get_json) -> list[Job]:
    jobs: list[Job] = []
    for source in sources:
        source_type = str(source.get("type", "")).lower()
        try:
            connector = CONNECTORS[source_type]
        except KeyError as error:
            raise ValueError(f"unsupported source type: {source_type or '<missing>'}") from error
        jobs.extend(connector(source, get_text if source_type == "yc" and fetch is get_json else fetch))
    return jobs


def fetch_sources_resilient(
    sources: list[dict[str, Any]], fetch: JsonFetcher = get_json
) -> list[SourceFetchResult]:
    """Fetch independently so one unavailable board does not suppress other results."""
    results: list[SourceFetchResult] = []
    for source in sources:
        identifier = source_id(source)
        payload: FetchPayload | None = None
        captured_payloads: list[FetchPayload] = []

        source_type = str(source.get("type", "")).lower()
        source_fetch = get_text if source_type == "yc" and fetch is get_json else fetch

        def capture(url: str) -> FetchPayload:
            nonlocal payload
            captured = source_fetch(url)
            captured_payloads.append(captured)
            payload = captured_payloads[0] if len(captured_payloads) == 1 else captured_payloads
            return captured

        try:
            connector = CONNECTORS[source_type]
            # USAJOBS requires API-key request headers, so its built-in fetcher owns
            # the request in normal runs. Fixture fetchers still receive the URL.
            connector_fetch = get_json if source_type == "usajobs" and fetch is get_json else capture
            jobs = connector(source, connector_fetch)
            results.append(SourceFetchResult(identifier, jobs, payload=payload))
        except Exception as error:  # A public source is unreliable by nature; retain the error.
            results.append(SourceFetchResult(identifier, [], payload=payload, error=str(error)))
    return results
