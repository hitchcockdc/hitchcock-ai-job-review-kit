# Connector contract

Connectors read a configured public employer feed and return normalized `Job` records.
They discover postings only: a connector must never authenticate as a candidate, submit an
application, contact an employer, or bypass a site's access controls.

## Supported public feeds

| Type | Public endpoint | Configuration identifier | Notes |
| --- | --- | --- | --- |
| `greenhouse` | Greenhouse Job Board API | `board_token` | One request includes job content. |
| `lever` | Lever Postings API | `site` | Set `region` to `eu` for EU-hosted boards. |
| `ashby` | Ashby Posting API | `job_board_name` | Compensation is requested when available. |
| `smartrecruiters` | SmartRecruiters Posting API | `company_identifier` | Reads the public list, then each posting's complete sections; `max_postings` is capped at 100. |
| `yc` | YC Work at a Startup public page | `board_token` | Normalizes public page data without an account. |
| `usajobs` | USAJOBS Search API | `board_token` | Requires a private API key and user-agent email. |

[SmartRecruiters documents](https://developers.smartrecruiters.com/docs/endpoints) separate
list and detail endpoints and notes that list records can omit fields. Requests explicitly
use `destination=PUBLIC`; the connector does not send an API key and does not access internal
postings. It joins the documented company description, job description, qualifications, and
additional-information sections before applying common HTML cleanup.

## Normalized job fields

Every connector must supply these fields:

| Field | Meaning |
| --- | --- |
| `source` | Stable source attribution in `type:board` form. |
| `external_id` | Stable posting identifier within that source. |
| `title` | Plain-text job title. |
| `company` | Employer name from configuration or the feed. |
| `url` | Employer-controlled posting or application URL. |
| `description` | Complete plain-text description. |

Connectors should also populate `location`, `remote`, `country`, `countries`, `regions`,
`employment_type`, `travel_percentage`, salary bounds, and `posted_at` whenever the public
feed provides reliable evidence. Missing values stay empty or `None`; they are not guessed.

The storage identity is `source:external_id`. Source attribution must therefore be stable
across refreshes. It is also retained in source-health records so failures can be diagnosed
without mixing one employer's results with another's.

## Normalization rules

- Pass titles, descriptions, and other display text through `get_a_job.text.plain_text`.
  This removes HTML, escaped tags, nested entities, and control characters before storage.
- Preserve the complete description rather than a card-length summary.
- Prefer structured country metadata when the feed provides it. Otherwise use
  `countries_from_text` and `regions_from_text` conservatively on the posting location.
- Preserve every supported country for multi-country roles. `country` is only the primary
  compatibility value; `countries` and `regions` carry the complete scope.
- Mark a role remote only when the feed's location or structured work-type field says so.
  General references to remote collaboration in a description are not sufficient.
- Never place access tokens, API keys, candidate details, review notes, or private employer
  information in source configuration, fixtures, logs, or tests.

## Failure isolation

`fetch_sources_resilient` calls each configured source independently and returns one
`SourceFetchResult` per source. A connector exception becomes an error result with no jobs;
successful sources from the same run remain available. The store records source health and
only expires stale jobs for sources that completed successfully, preventing an outage or
schema change from making an entire board disappear.

Raise a clear `ValueError` when a response has the wrong top-level shape. Skip malformed
individual postings only when a stable ID or title is absent and the remaining feed can be
processed safely. Do not catch network or schema errors inside a connector merely to return
an empty list—the resilient boundary needs the failure to remain visible.

## Synthetic example

[`examples/synthetic_connector.py`](../examples/synthetic_connector.py) is an executable,
unregistered example. Its matching fixture is
[`examples/fixtures/synthetic-board.json`](../examples/fixtures/synthetic-board.json), and
[`tests/test_connector_example.py`](../tests/test_connector_example.py) verifies source
attribution, description cleanup, geography, and invalid-feed behavior.

To adapt the example for a real public feed:

1. Give the connector the standard `(source, fetch=...) -> list[Job]` signature.
2. Add it to `CONNECTORS` and make its `source_id` configuration unambiguous.
3. Add fixture tests for normal records, incomplete records, malformed payloads, markup,
   remote detection, and all geography shapes the feed exposes.
4. Run it through `fetch_sources_resilient` with one successful and one failing source.
5. Document the public endpoint and confirm its terms allow the intended access.

The example and fixture use reserved `.test` URLs, a fictional employer, synthetic dates,
and no credentials, candidate data, or private employer notes.
