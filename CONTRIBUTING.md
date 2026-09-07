# Contributing

Thank you for helping improve Hitchcock AI Job Review Kit.

## Project boundaries

Contributions must preserve the human-review and privacy model:

- Use synthetic profiles, jobs, decisions, resumes, and screenshots.
- Do not add automatic application submission or employer outreach.
- Do not scrape authenticated job boards or bypass access controls.
- Do not infer or add resume claims without explicit candidate evidence.
- Keep the local API loopback-only unless a complete hosted security model is designed and
  reviewed separately.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cd dashboard
npm ci
```

## Tests

Run the Python suite from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Run dashboard formatting, linting, and the production test, build, and security gate from
`dashboard/`:

```bash
npm run format
npm run lint
npm run verify:release
```

Keep the repository-wide lint command passing. Fix findings at their source; narrow,
documented suppression is appropriate only for a reusable primitive whose caller supplies
the required accessibility relationship.

## Pull requests

Keep pull requests focused and include:

1. The user-facing problem and intended behavior.
2. Tests that fail before the change and pass afterward.
3. Privacy, data-retention, and performance implications.
4. Synthetic screenshots only when the interface changed.
5. Any remaining limitations or follow-up work.

Do not commit `.env` files, databases, resumes, profile exports, decision notes, source
credentials, tailored documents, or local filesystem paths.

## Connector contributions

New connectors must use documented public employer endpoints, normalize into the shared
`Job` model, isolate source failures, preserve source attribution, and include fixture-based
tests. A connector must never apply on behalf of a user.

Read the [connector contract and synthetic example](docs/CONNECTORS.md) before adding a
source. The example demonstrates the required fields, location metadata, description
normalization, failure behavior, and privacy boundary without using a real employer feed.

## Code style

Prefer focused modules, explicit data transformations, deterministic matching behavior, and
plain-language explanations. Avoid adding dependencies when the standard library or existing
project stack is sufficient.
