import unittest

from get_a_job.models import Job
from get_a_job.text import plain_text


class PlainTextTests(unittest.TestCase):
    def test_decodes_nested_entities_and_escaped_html(self):
        value = (
            "First sentence.&amp;nbsp;\\</p> "
            "\\&lt;p&gt;\\&lt;br&gt;Second &amp;amp; final sentence."
        )

        self.assertEqual(
            plain_text(value),
            "First sentence. Second & final sentence.",
        )

    def test_legacy_stored_job_description_is_cleaned_when_loaded(self):
        job = Job.from_dict(
            {
                "source": "test",
                "external_id": "legacy",
                "title": "Architect",
                "company": "Example",
                "url": "https://example.com/legacy",
                "description": "Plan systems.&nbsp;\\</p> \\<p>Build platforms.",
            }
        )

        self.assertEqual(job.description, "Plan systems. Build platforms.")


if __name__ == "__main__":
    unittest.main()
