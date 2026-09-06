# Architecture

## Overview

Job Review Kit is a local Python service with a React dashboard. SQLite is the source of
truth for normalized public postings, candidate preferences, review decisions, source
health, and application follow-ups.

```text
Public employer feeds
        |
        v
Connectors -> normalization -> SQLite -> ranking/matching -> loopback API
                                                              |
                                                              v
                                                     local React dashboard
```

## Python application

- `connectors.py` reads supported public employer feeds and converts them into `Job` records.
- `text.py` removes ATS markup and nested entities at ingestion and legacy-record loading.
- `locations.py` normalizes country and regional scope.
- `matching.py` applies eligibility rules and produces an explainable two-way score.
- `ranking.py` preselects and diversifies large queues before detailed scoring.
- `storage.py` owns SQLite persistence, history, deduplication, and maintenance operations.
- `dashboard_server.py` exposes the local HTTP boundary.
- `dashboard_services.py` isolates application tracking and resume-tailoring orchestration.

## Dashboard

The Vinext/React dashboard keeps selection and mutation coordination in `app/page.tsx` and
delegates the review queue, role detail, settings, application tracking, skill presentation,
and tailoring flow to focused components. API requests use the same development origin and
are proxied to the loopback Python service.

The dashboard build includes a Sites manifest with `d1` and `r2` set to `null` because the
build plugin expects that metadata. It does not configure a deployment or hosted data store;
the supported runtime remains the local Python API and SQLite database.

## Data flow and retention

1. A connector records source success or failure independently.
2. Normalized jobs are upserted by source and external ID.
3. Exact company/title/location duplicates remain stored but are hidden from the queue.
4. Successful source refreshes expire unseen unreviewed roles after the configured window.
5. Review decisions update queue status and append an immutable decision event.
6. Ranking results are cached until profile, decision, or relevant job revisions change.

Raw source payload snapshots contain public posting data and are retained only when their
content changes. Maintenance commands can compact redundant payloads and normalize active
descriptions without deleting history.

## Trust boundaries

The supported application boundary is one user's machine. The API binds to loopback, private
files are ignored by Git, and application submission stays on the employer's website. A
multi-user or hosted deployment would require a different identity, authorization, secret,
and storage architecture.
