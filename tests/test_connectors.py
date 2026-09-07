import json
import unittest
from pathlib import Path

from get_a_job.connectors import (
    fetch_ashby,
    fetch_greenhouse,
    fetch_lever,
    fetch_smartrecruiters,
    fetch_usajobs,
    fetch_yc,
    fetch_sources_resilient,
)


class ConnectorTests(unittest.TestCase):
    def test_greenhouse_normalizes_public_job(self):
        payload = {
            "jobs": [
                {
                    "id": 42,
                    "title": "AI Architect",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/42",
                    "content": "<p>Build <strong>RAG</strong> systems.</p>",
                    "location": {"name": "Remote - US"},
                    "updated_at": "2026-08-29T12:00:00Z",
                }
            ]
        }
        jobs = fetch_greenhouse(
            {"company": "Acme", "board_token": "acme"}, lambda _: payload
        )
        self.assertEqual(jobs[0].key, "greenhouse:acme:42")
        self.assertEqual(jobs[0].description, "Build RAG systems.")
        self.assertTrue(jobs[0].remote)
        self.assertEqual(jobs[0].country, "US")
        self.assertEqual(jobs[0].countries, ["US"])

    def test_greenhouse_removes_encoded_and_backslash_escaped_markup(self):
        payload = {
            "jobs": [
                {
                    "id": 43,
                    "title": "Platform Architect",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/43",
                    "content": (
                        "Lead architecture.&amp;nbsp;\\</p> "
                        "\\&lt;p&gt;\\&lt;br&gt;Improve delivery &amp;amp; reliability."
                    ),
                    "location": {"name": "Remote - US"},
                }
            ]
        }

        job = fetch_greenhouse(
            {"company": "Acme", "board_token": "acme"}, lambda _: payload
        )[0]

        self.assertEqual(
            job.description,
            "Lead architecture. Improve delivery & reliability.",
        )

    def test_lever_normalizes_public_job(self):
        payload = [
            {
                "id": "abc",
                "text": "Principal TPM",
                "categories": {"location": "Boise, Idaho"},
                "descriptionPlain": "Lead platform delivery.",
                "additionalPlain": "Python preferred.",
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "createdAt": 1788004800000,
            }
        ]
        jobs = fetch_lever({"company": "Acme", "site": "acme"}, lambda _: payload)
        self.assertEqual(jobs[0].key, "lever:acme:abc")
        self.assertIn("Python preferred", jobs[0].description)
        self.assertIsNotNone(jobs[0].posted_at)
        self.assertEqual(jobs[0].countries, ["US"])

    def test_ashby_skips_unlisted_and_extracts_annual_usd_salary(self):
        payload = {
            "jobs": [
                {
                    "id": "listed",
                    "title": "AI Program Lead",
                    "location": "Remote",
                    "address": {"postalAddress": {"addressCountry": "Ireland"}},
                    "jobUrl": "https://jobs.ashbyhq.com/acme/listed",
                    "descriptionHtml": "<p>Lead AI programs.</p>",
                    "isListed": True,
                    "compensation": {
                        "summaryComponents": [
                            {
                                "compensationType": "Salary",
                                "interval": "1 YEAR",
                                "currencyCode": "USD",
                                "minValue": 150000,
                                "maxValue": 190000,
                            }
                        ]
                    },
                },
                {
                    "id": "hidden",
                    "title": "Hidden Role",
                    "jobUrl": "https://jobs.ashbyhq.com/acme/hidden",
                    "isListed": False,
                },
            ]
        }
        jobs = fetch_ashby(
            {"company": "Acme", "job_board_name": "acme"}, lambda _: payload
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].salary_min, 150000)
        self.assertEqual(jobs[0].salary_max, 190000)
        self.assertTrue(jobs[0].remote)
        self.assertEqual(jobs[0].country, "IE")
        self.assertEqual(jobs[0].countries, ["IE"])

    def test_smartrecruiters_fetches_details_and_normalizes_public_posting(self):
        fixture_path = (
            Path(__file__).parents[1]
            / "examples"
            / "fixtures"
            / "smartrecruiters-public-postings.json"
        )
        payloads = json.loads(fixture_path.read_text(encoding="utf-8"))
        urls = []

        def fetch(url):
            urls.append(url)
            return payloads["detail"] if url.endswith("/101") else payloads["list"]

        jobs = fetch_smartrecruiters(
            {
                "type": "smartrecruiters",
                "company_identifier": "Acme",
                "title_terms": ["architect"],
            },
            fetch,
        )

        self.assertIn("destination=PUBLIC", urls[0])
        self.assertEqual(len(urls), 2)
        self.assertEqual(jobs[0].key, "smartrecruiters:Acme:101")
        self.assertEqual(jobs[0].countries, ["ES"])
        self.assertTrue(jobs[0].remote)
        self.assertEqual(jobs[0].employment_type, "Full-time")
        self.assertEqual((jobs[0].salary_min, jobs[0].salary_max), (150000, 190000))
        self.assertEqual(
            jobs[0].description,
            "Job Description: Lead AI platform delivery. Qualifications: Python & Kubernetes required. Company Description: Acme builds enterprise products.",
        )
        self.assertEqual(jobs[0].location, "Remote - Madrid, ES")

        no_matches = fetch_smartrecruiters(
            {
                "type": "smartrecruiters",
                "company_identifier": "Acme",
                "title_terms": ["accountant"],
            },
            lambda _: payloads["list"],
        )
        self.assertEqual(no_matches, [])

    def test_smartrecruiters_rejects_invalid_list_and_detail_shapes(self):
        source = {"type": "smartrecruiters", "company_identifier": "Acme"}
        with self.assertRaisesRegex(ValueError, "must be an object"):
            fetch_smartrecruiters(source, lambda _: [])

        calls = iter([{"content": [{"id": "1", "name": "Architect"}]}, []])
        with self.assertRaisesRegex(ValueError, "details must be an object"):
            fetch_smartrecruiters(source, lambda _: next(calls))
        with self.assertRaisesRegex(ValueError, "title_terms"):
            fetch_smartrecruiters(
                {**source, "title_terms": "architect"}, lambda _: {"content": []}
            )

    def test_smartrecruiters_can_find_prioritized_titles_on_later_pages(self):
        source = {
            "type": "smartrecruiters",
            "company_identifier": "Acme",
            "max_postings": 1,
            "max_listing_pages": 2,
            "title_terms": ["technical program manager", "architect"],
        }
        first_page = {
            "totalFound": 101,
            "content": [
                {"id": str(index), "name": "Unrelated role"}
                for index in range(100)
            ],
        }
        second_page = {
            "totalFound": 101,
            "content": [{"id": "target", "name": "Principal Technical Program Manager"}],
        }
        detail = {
            "id": "target",
            "name": "Principal Technical Program Manager",
            "active": True,
            "postingUrl": "https://jobs.smartrecruiters.com/Acme/target",
            "location": {"country": "us", "remote": True},
            "jobAd": {"sections": {"jobDescription": {"text": "Lead delivery."}}},
        }

        def fetch(url):
            if url.endswith("/target"):
                return detail
            return second_page if "offset=100" in url else first_page

        jobs = fetch_smartrecruiters(source, fetch)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Principal Technical Program Manager")

    def test_resilient_fetch_retains_all_multi_request_payloads(self):
        responses = iter(
            [
                {"content": [{"id": "1", "name": "Architect"}]},
                {
                    "id": "1",
                    "name": "Architect",
                    "active": True,
                    "postingUrl": "https://jobs.smartrecruiters.com/Acme/1",
                    "location": {"country": "us", "remote": True},
                    "jobAd": {"sections": {"jobDescription": {"text": "Python"}}},
                },
            ]
        )
        result = fetch_sources_resilient(
            [{"type": "smartrecruiters", "company_identifier": "Acme"}],
            lambda _: next(responses),
        )[0]

        self.assertIsNone(result.error)
        self.assertEqual(len(result.jobs), 1)
        self.assertIsInstance(result.payload, list)
        self.assertEqual(len(result.payload), 2)

    def test_resilient_fetch_keeps_success_when_another_source_fails(self):
        payload = {"jobs": []}

        def fetch(url):
            if "broken" in url:
                raise RuntimeError("temporary outage")
            return payload

        results = fetch_sources_resilient(
            [
                {"type": "greenhouse", "company": "Working", "board_token": "working"},
                {"type": "greenhouse", "company": "Broken", "board_token": "broken"},
            ],
            fetch,
        )
        self.assertIsNone(results[0].error)
        self.assertEqual(results[1].error, "temporary outage")

    def test_country_can_be_in_a_greenhouse_title_when_location_is_remote(self):
        payload = {
            "jobs": [
                {
                    "id": 99,
                    "title": "Senior Customer Engineer, East China",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/99",
                    "content": "<p>Customer engineering.</p>",
                    "location": {"name": "Remote"},
                }
            ]
        }
        job = fetch_greenhouse({"company": "Acme", "board_token": "acme"}, lambda _: payload)[0]
        self.assertEqual(job.country, "CN")

    def test_yc_normalizes_public_page_payload(self):
        page = {"props": {"jobPostings": [{
            "id": 123, "title": "Technical Program Manager", "url": "/companies/acme/jobs/123-tpm",
            "location": "Remote (US)", "type": "Full-time", "companyName": "Acme",
            "companyOneLiner": "AI infrastructure for enterprises.", "prettyRole": "Operations",
            "skills": ["Python"], "salaryRange": "$180K - $220K",
        }]}}
        markup = '<div data-page="' + json.dumps(page).replace('"', '&quot;') + '"></div>'
        job = fetch_yc({"company": "YC", "board_token": "work-at-a-startup"}, lambda _: markup)[0]
        self.assertEqual(job.key, "yc:work-at-a-startup:123")
        self.assertEqual(job.country, "US")
        self.assertEqual(job.countries, ["US"])
        self.assertEqual((job.salary_min, job.salary_max), (180000, 220000))

    def test_connectors_preserve_multi_country_and_region_targets(self):
        greenhouse_payload = {
            "jobs": [{
                "id": 1,
                "title": "Platform Engineer",
                "absolute_url": "https://example.com/greenhouse",
                "content": "Build platforms.",
                "location": {"name": "Remote - Spain or Portugal"},
            }]
        }
        greenhouse_job = fetch_greenhouse(
            {"company": "Acme", "board_token": "acme"},
            lambda _: greenhouse_payload,
        )[0]
        self.assertEqual(greenhouse_job.countries, ["ES", "PT"])

        lever_payload = [{
            "id": "eu",
            "text": "Platform Engineer",
            "categories": {"location": "Remote - Europe"},
            "descriptionPlain": "Build platforms.",
            "hostedUrl": "https://example.com/lever",
        }]
        lever_job = fetch_lever(
            {"company": "Acme", "site": "acme", "region": "eu"},
            lambda _: lever_payload,
        )[0]
        self.assertEqual(lever_job.regions, ["EUROPE"])

        ashby_payload = {"jobs": [{
            "id": "es",
            "title": "Platform Engineer",
            "location": "Remote",
            "address": {"postalAddress": {"addressCountry": "ES"}},
            "jobUrl": "https://example.com/ashby",
            "descriptionPlain": "Build platforms.",
            "isListed": True,
        }]}
        ashby_job = fetch_ashby(
            {"company": "Acme", "job_board_name": "acme"},
            lambda _: ashby_payload,
        )[0]
        self.assertEqual(ashby_job.countries, ["ES"])

        yc_page = {"props": {"jobPostings": [{
            "id": 2,
            "title": "Platform Engineer",
            "url": "/jobs/2",
            "location": "GB / US / CA / Remote (GB; US; CA)",
            "companyName": "Acme",
        }]}}
        yc_markup = '<div data-page="' + json.dumps(yc_page).replace('"', '&quot;') + '"></div>'
        yc_job = fetch_yc(
            {"company": "YC", "board_token": "work-at-a-startup"},
            lambda _: yc_markup,
        )[0]
        self.assertEqual(yc_job.countries, ["US", "CA", "GB"])

    def test_usajobs_requires_key_and_normalizes_search_result(self):
        with self.assertRaisesRegex(ValueError, "requires private"):
            fetch_usajobs({"company": "USAJOBS"}, lambda _: {})
        payload = {"SearchResult": {"SearchResultItems": [{"MatchedObjectId": "9", "MatchedObjectDescriptor": {
            "PositionID": "ABC-123", "PositionTitle": "IT Specialist", "OrganizationName": "Department of Example",
            "PositionURI": "https://www.usajobs.gov/job/123", "PositionLocation": [{"LocationName": "Boise, Idaho"}],
            "PositionRemuneration": [{"MinimumRange": "120000", "MaximumRange": "150000"}],
            "UserArea": {"Details": {"JobSummary": "Lead cloud delivery."}}, "PublicationStartDate": "2026-08-29",
        }}]}}
        job = fetch_usajobs({"api_key": "secret", "user_agent": "person@example.com"}, lambda _: payload)[0]
        self.assertEqual(job.key, "usajobs:search:ABC-123")
        self.assertEqual(job.country, "US")
        self.assertEqual(job.countries, ["US"])
        self.assertEqual(job.salary_max, 150000)


if __name__ == "__main__":
    unittest.main()
