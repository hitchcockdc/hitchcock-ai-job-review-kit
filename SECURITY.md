# Security Policy

## Supported version

Security fixes are applied to the current `main` branch. The project is alpha software and
does not currently publish versioned support guarantees.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when it is available for the
repository. If it is unavailable, contact the maintainer privately through the GitHub
profile rather than opening a public issue.

Include the affected component, impact, reproduction steps, and a proposed mitigation when
known. Use synthetic fixtures only. Never attach a real resume, profile, decision history,
database, API key, generated document, or employer correspondence.

Public issues or pull requests that expose sensitive candidate data may be removed without
notice.

## Security boundaries

- The Python API binds to `127.0.0.1` and accepts browser requests only from configured local
  dashboard origins.
- Candidate data and generated artifacts are local files excluded by `.gitignore`.
- Connectors read public employer feeds; authenticated job-board scraping is out of scope.
- The project does not submit applications, send messages, or make unsupported resume claims.
- Raw public source payloads may be retained locally for debugging and change detection.
- A hosted deployment is not supported because it would require a separate authentication,
  authorization, secret-management, and private-storage design.

## Dependency checks

The dashboard security workflow installs the lockfile, audits production dependencies,
runs interaction tests, and builds the application. Run the same gate locally before a
release:

```bash
cd dashboard
npm run verify:release
```

## Public-release hygiene

Public releases must come from a fresh sanitized export, not by changing a personal working
repository from private to public. The export must contain synthetic examples only and must
be scanned for local paths, credentials, databases, resumes, generated documents, and
candidate identifiers before publication.
