from __future__ import annotations

from datetime import date

from get_a_job.models import Job, MatchResult


def markdown_digest(items: list[tuple[MatchResult, Job]]) -> str:
    lines = [f"# Job discovery digest - {date.today().isoformat()}", ""]
    if not items:
        return "\n".join([*lines, "No unreviewed eligible matches were found today.", ""])
    lines.extend([f"{len(items)} unreviewed, eligible matches", ""])
    for result, job in items:
        lines.extend(
            [
                f"## {job.title} - {job.company}",
                "",
                f"- Score: {result.score}/100",
                f"- Location: {job.location or 'Not stated'}",
                f"- Work country: {job.country or 'Not stated'}",
                f"- Employment type: {job.employment_type or 'Not stated'}",
                f"- Apply: {job.url}",
                f"- Job key: `{job.key}`",
                f"- Why it matches: {'; '.join(result.reasons)}",
                "",
            ]
        )
    return "\n".join(lines)
