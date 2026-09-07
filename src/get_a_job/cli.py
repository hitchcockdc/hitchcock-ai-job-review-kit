from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from get_a_job.digest import markdown_digest
from get_a_job.models import CandidateProfile, Job
from get_a_job.ranking import shortlist
from get_a_job.refresher import refresh_sources
from get_a_job.storage import Store


def _load_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="get-a-job")
    parser.add_argument("--db", default="get_a_job.db", help="SQLite database path")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="create the database")
    compact = commands.add_parser("compact-source-payloads", help="remove redundant raw source snapshots")
    compact.add_argument("--reclaim-space", action="store_true", help="rewrite SQLite to return freed disk space")
    normalize = commands.add_parser(
        "normalize-descriptions",
        help="audit or normalize HTML artifacts in stored job descriptions",
    )
    normalize.add_argument(
        "--apply",
        action="store_true",
        help="back up the database and apply normalization; otherwise report only",
    )
    normalize.add_argument(
        "--include-expired",
        action="store_true",
        help="include expired roles in the audit or normalization",
    )
    profile = commands.add_parser("import-profile", help="load a candidate profile JSON file")
    profile.add_argument("path")
    preferences = commands.add_parser("apply-preferences", help="merge private preferences into the profile")
    preferences.add_argument("path")
    jobs = commands.add_parser("import-jobs", help="load normalized jobs from a JSON file")
    jobs.add_argument("path")
    fetch = commands.add_parser("fetch", help="fetch jobs from configured public ATS sources")
    fetch.add_argument("path", help="JSON source configuration")
    matches = commands.add_parser("matches", help="show ranked job matches")
    matches.add_argument("--limit", type=int, default=10)
    matches.add_argument("--per-company", type=int, default=1)
    matches.add_argument("--include-reviewed", action="store_true")
    review = commands.add_parser("review", help="record a saved, rejected, or applied decision")
    review.add_argument("job_key")
    review.add_argument("status", choices=("saved", "rejected", "applied"))
    review.add_argument("--note", default="")
    decisions = commands.add_parser("decisions", help="show recent review decisions")
    decisions.add_argument("--limit", type=int, default=20)
    digest = commands.add_parser("digest", help="render a Markdown digest of unreviewed matches")
    digest.add_argument("--limit", type=int, default=10)
    digest.add_argument("--per-company", type=int, default=1)
    digest.add_argument("--output", help="optional Markdown output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.db)
    if args.command == "init-db":
        store.initialize()
        print(f"Initialized {args.db}")
    elif args.command == "compact-source-payloads":
        removed = store.compact_source_payloads(reclaim_space=args.reclaim_space)
        print(f"Compacted {removed} redundant source payload copies")
    elif args.command == "normalize-descriptions":
        report = store.normalize_job_descriptions(
            include_expired=args.include_expired,
        )
        scope = "all" if args.include_expired else "active"
        if not args.apply:
            print(
                f"Dry run: {report.changed} of {report.scanned} {scope} job "
                "descriptions need normalization"
            )
            for source, count in report.changed_by_source.items():
                print(f"  {source}: {count}")
        elif not report.changed:
            print(f"No {scope} job descriptions need normalization")
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            database_path = Path(args.db)
            backup = database_path.with_name(
                f"{database_path.stem}.description-backup-{timestamp}.db"
            )
            store.backup(backup)
            applied = store.normalize_job_descriptions(
                apply=True,
                include_expired=args.include_expired,
            )
            print(
                f"Normalized {applied.changed} of {applied.scanned} {scope} job "
                f"descriptions; backup: {backup}"
            )
    elif args.command == "import-profile":
        profile = CandidateProfile.from_dict(_load_json(args.path))
        store.save_profile(profile)
        print(f"Imported profile for {profile.name}")
    elif args.command == "apply-preferences":
        preferences = _load_json(args.path)
        if not isinstance(preferences, dict):
            raise ValueError("preferences file must contain a JSON object")
        profile_data = asdict(store.load_profile())
        allowed = {
            "minimum_salary",
            "remote_ok",
            "locations",
            "employment_types",
            "max_travel_percentage",
            "title_priorities",
            "target_titles",
            "eligible_countries",
            "work_authorized_countries",
            "consider_sponsorship_roles",
            "scoring_weights",
        }
        unknown = set(preferences) - allowed
        if unknown:
            raise ValueError(f"unsupported preference fields: {', '.join(sorted(unknown))}")
        profile_data.update(preferences)
        profile = CandidateProfile.from_dict(profile_data)
        store.save_profile(profile)
        print(f"Applied {len(preferences)} preferences for {profile.name}")
    elif args.command == "import-jobs":
        payload = _load_json(args.path)
        if not isinstance(payload, list):
            raise ValueError("jobs file must contain a JSON list")
        jobs = [Job.from_dict(item) for item in payload]
        report = store.upsert_jobs(jobs)
        print(f"Imported {len(jobs)} jobs ({report.inserted} newly discovered, {report.changed} changed)")
    elif args.command == "fetch":
        payload = _load_json(args.path)
        if not isinstance(payload, list):
            raise ValueError("source configuration must contain a JSON list")
        report = refresh_sources(store, Path(args.path))
        # Read the latest source results for concise CLI feedback after the shared refresh path.
        failed = sum(item["error"] is not None for item in store.source_health())
        print(
            f"Fetched {report['fetched']} jobs ({report['new']} newly discovered, "
            f"{report['changed']} changed, {report['expired']} expired, {failed} sources failed)"
        )
    elif args.command == "matches":
        profile = store.load_profile()
        jobs = store.list_jobs(None if args.include_reviewed else ["new"])
        ranked = shortlist(profile, jobs, args.limit, args.per_company)
        for result, job in ranked:
            status = "eligible" if result.eligible else "filtered"
            print(f"{result.score:3d}  {status:8s}  {job.title} — {job.company}")
            print(f"     {'; '.join(result.reasons)}")
            print(f"     Job key: {job.key}")
            print(f"     {job.url}")
    elif args.command == "review":
        store.set_review(args.job_key, args.status, args.note)
        print(f"Marked {args.job_key} as {args.status}")
    elif args.command == "decisions":
        for decision in store.list_decisions(args.limit):
            note = f" - {decision['note']}" if decision["note"] else ""
            print(f"{decision['decided_at']}  {decision['status']:8s}  {decision['job_key']}{note}")
    elif args.command == "digest":
        profile = store.load_profile()
        ranked = shortlist(profile, store.list_jobs(["new"]), args.limit, args.per_company)
        digest = markdown_digest(ranked)
        if args.output:
            Path(args.output).write_text(digest, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(digest)
    return 0
