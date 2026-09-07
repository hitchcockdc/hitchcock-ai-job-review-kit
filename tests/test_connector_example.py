import json
from pathlib import Path
import unittest

from examples.synthetic_connector import fetch_synthetic


class SyntheticConnectorExampleTests(unittest.TestCase):
    def test_example_normalizes_source_location_and_description(self):
        fixture_path = Path("examples/fixtures/synthetic-board.json")
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

        jobs = fetch_synthetic(
            {
                "endpoint": "https://jobs.example.test/api/positions",
                "company": "Example Technology Cooperative",
                "slug": "example-tech",
            },
            lambda _: payload,
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].key, "synthetic:example-tech:example-101")
        self.assertEqual(
            jobs[0].description,
            "Build observable Python services & delivery tooling.",
        )
        self.assertEqual(jobs[0].countries, ["ES"])
        self.assertEqual(jobs[0].regions, ["EUROPE"])

    def test_example_rejects_an_invalid_feed_shape(self):
        with self.assertRaisesRegex(ValueError, "positions list"):
            fetch_synthetic(
                {
                    "endpoint": "https://jobs.example.test/api/positions",
                    "company": "Example Technology Cooperative",
                    "slug": "example-tech",
                },
                lambda _: [],
            )
