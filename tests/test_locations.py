import unittest

from get_a_job.locations import (
    countries_from_text,
    eligible_targets_match,
    regions_from_text,
)


class LocationTests(unittest.TestCase):
    def test_worldwide_regions_accept_member_countries(self):
        examples = {
            "EMEA": ("Spain", "United Arab Emirates", "South Africa"),
            "APAC": ("Singapore", "Malaysia", "New Zealand"),
            "LATAM": ("Brazil", "Mexico", "Argentina"),
        }

        for region, countries in examples.items():
            for country in countries:
                with self.subTest(region=region, country=country):
                    self.assertTrue(
                        eligible_targets_match([country], [], [region])
                    )

    def test_worldwide_regions_reject_non_member_countries(self):
        examples = (
            ("US", "EMEA"),
            ("Spain", "APAC"),
            ("Japan", "LATAM"),
        )

        for country, region in examples:
            with self.subTest(region=region, country=country):
                self.assertFalse(
                    eligible_targets_match([country], [], [region])
                )

    def test_region_aliases_are_extracted_from_posting_locations(self):
        self.assertEqual(
            regions_from_text("Remote — Europe, Middle East and Africa"),
            ["EUROPE", "EMEA"],
        )
        self.assertEqual(regions_from_text("Remote (Asia-Pacific)"), ["APAC"])
        self.assertEqual(
            regions_from_text("Latin America and the Caribbean"),
            ["LATAM"],
        )

    def test_specific_country_names_do_not_add_shorter_false_matches(self):
        examples = {
            "Papua New Guinea": ["PG"],
            "Equatorial Guinea": ["GQ"],
            "South Sudan": ["SS"],
            "Northern Ireland": ["GB"],
        }

        for location, expected in examples.items():
            with self.subTest(location=location):
                self.assertEqual(countries_from_text(location), expected)


if __name__ == "__main__":
    unittest.main()
