# Privacy and data handling

## Data that stays local

- Candidate profile and preferences
- Uploaded PDF and DOCX resumes
- Extracted resume text and profile drafts
- Saved, rejected, and applied decisions and notes
- Application follow-up reminders
- Resume-tailoring plans and generated documents
- SQLite job database and backups
- Private source credentials, when configured

These files are excluded by the repository `.gitignore`. They should also be excluded from
cloud-sync folders, screenshots, issue reports, and public backups unless the user has made a
separate informed decision to store them there.

## Outbound requests

The application requests configured public employer feeds to discover postings. The optional
USAJOBS connector sends the API key and user-agent email required by that service. When the
user selects **Open employer application**, the employer's website opens and is then governed
by that site's privacy policy.

The project contains no analytics, advertising, hosted candidate account, automatic outreach,
or automatic application submission.

## Public source history

The SQLite database may retain changed versions and selected raw responses from public job
feeds for debugging and change detection. This data can be large. The
`compact-source-payloads` command removes redundant copies while preserving fetch history.

## Resume tailoring

Tailoring operates on local documents and approved existing evidence. Generated files are
separate private artifacts. Users should verify every generated document for accuracy and
formatting before sharing it.

## Public contributions

Never submit real candidate data. Use the synthetic fixtures under `examples/` and replace
all names, emails, employers, URLs, decisions, document content, and filesystem paths in bug
reports or tests.
