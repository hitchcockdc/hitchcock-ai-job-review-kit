import unittest
from dataclasses import asdict, replace

from get_a_job.matching import score_job
from get_a_job.models import CandidateProfile, Job


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.profile = CandidateProfile(
            name="Candidate",
            target_titles=["software engineer"],
            skills=["Python", "SQL", "Docker"],
            locations=["Boise"],
            remote_ok=True,
            minimum_salary=100_000,
            excluded_terms=["commission only"],
        )

    def test_strong_remote_match_is_eligible(self):
        job = Job(
            source="test",
            external_id="1",
            title="Senior Software Engineer",
            company="Example",
            url="https://example.com/1",
            description="Build Python and SQL services with Docker.",
            remote=True,
            salary_max=150_000,
        )
        result = score_job(self.profile, job)
        self.assertTrue(result.eligible)
        self.assertEqual(result.score, 85)
        self.assertEqual(result.matched_skills, ["Python", "SQL", "Docker"])

    def test_role_skill_coverage_does_not_drop_when_profile_grows(self):
        job = Job(
            "test", "coverage", "Software Engineer", "Example", "https://example.com/coverage",
            "Required qualifications: Python, SQL, and Docker experience.", remote=True,
        )
        baseline = score_job(self.profile, job)
        broader_profile = replace(self.profile, skills=[*self.profile.skills, "Kubernetes", "React"])
        broader = score_job(broader_profile, job)
        self.assertEqual(broader.score, baseline.score)
        self.assertEqual(broader.score_breakdown["role_skills"], 25)
        self.assertEqual(broader.score_breakdown["required_skills"], 30)

    def test_required_role_coverage_increases_score(self):
        job = Job(
            "test", "required", "Software Engineer", "Example", "https://example.com/required",
            "Required qualifications: Python, SQL, Docker, and Kubernetes experience.", remote=True,
        )
        partial = score_job(self.profile, job)
        complete = score_job(replace(self.profile, skills=[*self.profile.skills, "Kubernetes"]), job)
        self.assertGreater(complete.score, partial.score)
        self.assertEqual(partial.score_breakdown["required_skills"], 22)
        self.assertEqual(complete.score_breakdown["required_skills"], 30)

    def test_custom_scoring_weights_change_only_documented_components(self):
        profile = replace(
            self.profile,
            scoring_weights={
                "required_skills": 40,
                "role_skills": 30,
                "title_target": 10,
                "priority": 5,
                "work_location": 5,
                "preferences": 5,
                "industry": 5,
            },
        )
        job = Job(
            "test", "weighted", "Software Engineer", "Example",
            "https://example.com/weighted",
            "Required qualifications: Python, SQL, and Docker experience.",
            remote=True,
        )

        result = score_job(profile, job)

        self.assertEqual(result.score, 90)
        self.assertEqual(result.score_breakdown["required_skills"], 40)
        self.assertEqual(result.score_breakdown["role_skills"], 30)
        self.assertEqual(result.score_breakdown["title_target"], 10)
        self.assertEqual(result.scoring_weights, profile.scoring_weights)

    def test_profile_rejects_incomplete_or_unbalanced_scoring_weights(self):
        with self.assertRaisesRegex(ValueError, "seven documented components"):
            CandidateProfile.from_dict(
                {"target_titles": [], "skills": [], "scoring_weights": {"role_skills": 100}}
            )
        with self.assertRaisesRegex(ValueError, "must total 100"):
            CandidateProfile.from_dict(
                {
                    "target_titles": [],
                    "skills": [],
                    "scoring_weights": {
                        "required_skills": 30,
                        "role_skills": 30,
                        "title_target": 20,
                        "priority": 10,
                        "work_location": 5,
                        "preferences": 5,
                        "industry": 5,
                    },
                }
            )

    def test_profile_preserves_validated_named_scoring_presets(self):
        weights = asdict(self.profile)["scoring_weights"]
        profile = CandidateProfile.from_dict(
            {
                **asdict(self.profile),
                "scoring_presets": {"Balanced": weights},
            }
        )
        self.assertEqual(profile.scoring_presets, {"Balanced": weights})
        with self.assertRaisesRegex(ValueError, "seven documented components"):
            CandidateProfile.from_dict(
                {
                    **asdict(self.profile),
                    "scoring_presets": {"Invalid": {"required_skills": 100}},
                }
            )

    def test_profile_validates_cache_pressure_warning_threshold(self):
        profile = CandidateProfile.from_dict(
            {**asdict(self.profile), "cache_pressure_warning_threshold": 5}
        )
        self.assertEqual(profile.cache_pressure_warning_threshold, 5)
        with self.assertRaisesRegex(ValueError, "cache pressure warning threshold"):
            CandidateProfile.from_dict(
                {**asdict(self.profile), "cache_pressure_warning_threshold": 0}
            )

    def test_boise_local_role_is_eligible_alongside_remote_roles(self):
        job = Job(
            "test", "boise", "Software Engineer", "Example", "https://example.com/boise",
            "Required qualifications: Python and SQL.", location="Boise, Idaho", remote=False,
        )
        result = score_job(self.profile, job)
        self.assertTrue(result.eligible)
        self.assertIn("work location match: local (Boise, Idaho)", result.reasons)

    def test_hard_filters_cap_score(self):
        job = Job(
            source="test",
            external_id="2",
            title="Software Engineer",
            company="Example",
            url="https://example.com/2",
            description="Python SQL Docker commission only",
            location="Miami, Florida",
            remote=False,
            salary_max=80_000,
        )
        result = score_job(self.profile, job)
        self.assertFalse(result.eligible)
        self.assertLessEqual(result.score, 39)

    def test_profile_preserves_resume_evidence(self):
        profile = CandidateProfile.from_dict(
            {
                "name": "Candidate",
                "target_titles": ["architect"],
                "skills": ["Python"],
                "evidence_inventory": [
                    {"role": "Architect", "evidence": ["Built a platform"]}
                ],
                "education": ["MS Software Engineering"],
            }
        )
        serialized = asdict(profile)
        self.assertEqual(serialized["evidence_inventory"][0]["role"], "Architect")
        self.assertEqual(serialized["education"], ["MS Software Engineering"])

    def test_aliases_classification_and_resume_evidence_are_explained(self):
        profile = CandidateProfile.from_dict(
            {
                "name": "Candidate",
                "target_titles": ["architect"],
                "skills": ["generative AI", "Python"],
                "skill_aliases": {"generative AI": ["LLM", "large language model"]},
                "remote_ok": True,
                "evidence_inventory": [
                    {
                        "evidence": [
                            "Architected governed generative AI and Python workflows."
                        ]
                    }
                ],
            }
        )
        job = Job(
            source="test",
            external_id="3",
            title="AI Architect",
            company="Example",
            url="https://example.com/3",
            description=(
                "Required qualifications: LLM and Python experience. "
                "Preferred: large language model evaluation."
            ),
            remote=True,
        )
        result = score_job(profile, job)
        self.assertEqual(result.matched_skills, ["generative AI", "Python"])
        self.assertEqual(result.matched_required_skills, ["generative AI", "Python"])
        self.assertEqual(result.matched_preferred_skills, ["generative AI"])
        self.assertTrue(result.evidence)

    def test_missing_skills_are_role_requirements_absent_from_profile(self):
        job = Job(
            source="test",
            external_id="gaps",
            title="Software Engineer",
            company="Example",
            url="https://example.com/gaps",
            description="Required qualifications: Python, Java, Kubernetes, and AWS experience.",
            remote=True,
        )
        result = score_job(self.profile, job)
        self.assertEqual(result.matched_skills, ["Python"])
        self.assertEqual(result.missing_skills, ["Java", "AWS", "Kubernetes"])
        self.assertEqual(result.required_role_skills, ["Python", "Java", "AWS", "Kubernetes"])
        self.assertIn("role skills not yet in resume: Java, AWS, Kubernetes", result.reasons)

    def test_buried_description_capabilities_are_reviewed(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["architect"], skills=["LLM", "OAuth"], remote_ok=True,
        )
        job = Job(
            "test", "buried", "AI Architect", "Example", "https://example.com/buried",
            "Hands-on technical depth across LLM platform tooling, agent and MCP architecture, identity and OAuth, CI/CD, and infrastructure as code.",
            remote=True,
        )
        result = score_job(profile, job)
        self.assertEqual(result.required_role_skills, [])
        self.assertEqual(
            result.buried_role_skills,
            ["LLM", "Agent architecture", "MCP", "Identity & access management", "OAuth", "CI/CD", "Infrastructure as code"],
        )
        self.assertEqual(
            result.missing_skills,
            ["Agent architecture", "MCP", "Identity & access management", "CI/CD", "Infrastructure as code"],
        )
        self.assertEqual((result.matched_role_skill_count, result.role_skill_count), (2, 7))
        self.assertTrue(all(entry["confidence"] == "medium" for entry in result.role_skill_contexts))

    def test_equal_opportunity_identity_language_is_not_an_iam_skill(self):
        job = Job(
            "test", "eeo", "Solution Architect", "Example", "https://example.com/eeo",
            (
                "Required qualifications: Tableau experience. "
                "All qualified applicants will receive consideration without regard "
                "to gender identity or any other characteristic protected by law."
            ),
            remote=True,
        )
        result = score_job(self.profile, job)
        self.assertNotIn("Identity & access management", result.missing_skills)
        self.assertNotIn("Identity & access management", result.required_role_skills)

    def test_solution_architect_title_matches_solutions_architect_target(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["solutions architect"],
            skills=["Python"],
            remote_ok=True,
        )
        job = Job(
            "test", "singular-title", "Solution Architect", "Example",
            "https://example.com/singular-title", "Python", remote=True,
        )

        result = score_job(profile, job)

        self.assertEqual(result.score_breakdown["title_target"], 20)
        self.assertIn("target title match: solutions architect", result.reasons)

    def test_qualifications_section_skills_remain_required_until_next_section(self):
        job = Job(
            "test", "qualification-section", "Solution Architect", "Example",
            "https://example.com/qualification-section",
            (
                "Qualifications: Background in data governance, data catalogs, "
                "ontologies, and knowledge graphs. Proficiency in SQL. "
                "Additional Information: Our internal platform also uses AWS."
            ),
            remote=True,
        )

        result = score_job(self.profile, job)

        self.assertEqual(
            result.required_role_skills,
            [
                "SQL",
                "Data governance",
                "Data catalogs",
                "Knowledge graphs",
                "Ontologies",
            ],
        )
        self.assertNotIn("AWS", result.required_role_skills)

    def test_explicit_identity_and_oauth_language_is_an_iam_skill(self):
        job = Job(
            "test", "iam", "Platform Architect", "Example", "https://example.com/iam",
            "Hands-on technical depth across identity and OAuth platform architecture.",
            remote=True,
        )
        result = score_job(self.profile, job)
        self.assertIn("Identity & access management", result.buried_role_skills)
        self.assertIn("OAuth", result.buried_role_skills)

    def test_recurring_platform_capabilities_are_detected_in_role_narrative(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["architect"], skills=["PostgreSQL", "SSO"], remote_ok=True,
        )
        job = Job(
            "test", "platform", "Platform Architect", "Example", "https://example.com/platform",
            "Hands-on platform ownership across observability, OpenTelemetry, Kafka, Helm, PostgreSQL, and single sign-on.",
            remote=True,
        )
        result = score_job(profile, job)
        self.assertEqual(result.matched_role_skill_count, 2)
        self.assertEqual(result.role_skill_count, 6)
        self.assertEqual(result.missing_skills, ["Observability", "OpenTelemetry", "Kafka", "Helm"])

    def test_employment_type_and_travel_preferences_filter_jobs(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["architect"],
            skills=["Python"],
            remote_ok=True,
            employment_types=["full time"],
            max_travel_percentage=10,
        )
        job = Job(
            "test", "4", "Architect", "Example", "https://example.com/4", "Python", remote=True,
            employment_type="Contract", travel_percentage=25,
        )
        result = score_job(profile, job)
        self.assertFalse(result.eligible)
        self.assertIn("employment type does not match", result.reasons)
        self.assertIn("travel requirement exceeds the configured maximum", result.reasons)

    def test_known_ineligible_work_country_is_filtered(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["architect"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["US"],
        )
        job = Job(
            "test", "5", "Architect", "Example", "https://example.com/5", "Python", remote=True,
            country="IE",
        )
        result = score_job(profile, job)
        self.assertFalse(result.eligible)
        self.assertIn("work country or region is not eligible: IE", result.reasons)

    def test_explicit_foreign_location_is_not_treated_as_us_remote(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["engineer"], skills=["Python"], remote_ok=True,
            eligible_countries=["US"],
        )
        job = Job(
            "test", "spain-remote", "Software Engineer", "Example", "https://example.com/spain",
            "Python", location="Spain (Remote)", remote=True,
        )
        result = score_job(profile, job)
        self.assertFalse(result.eligible)
        self.assertEqual(result.country_verification, "ineligible")
        self.assertIn("work country or region is not eligible: ES", result.reasons)

    def test_explicit_foreign_region_is_not_treated_as_us_remote(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["engineer"], skills=["Python"], remote_ok=True,
            eligible_countries=["US"],
        )
        job = Job(
            "test", "emea-remote", "Software Engineer", "Example", "https://example.com/emea",
            "Python", location="Remote - EMEA", remote=True,
        )
        result = score_job(profile, job)
        self.assertFalse(result.eligible)
        self.assertEqual(result.country_verification, "ineligible")
        self.assertIn("work country or region is not eligible: EMEA", result.reasons)

    def test_expanded_queue_foreign_locations_are_not_treated_as_us_remote(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["engineer"], skills=["Python"], remote_ok=True,
            eligible_countries=["US"],
        )
        locations = {
            "Remote - Estonia": "EE",
            "Bengaluru, KA, IN / Bengaluru, Karnataka, IN / Remote": "IN",
            "SP, BR / State of São Paulo, BR / Remote (BR)": "BR",
        }

        for index, (location, country) in enumerate(locations.items()):
            with self.subTest(location=location):
                job = Job(
                    "test", f"foreign-{index}", "Software Engineer", "Example",
                    f"https://example.com/foreign-{index}", "Python",
                    location=location, remote=True,
                )
                result = score_job(profile, job)
                self.assertFalse(result.eligible)
                self.assertEqual(result.country_verification, "ineligible")
                self.assertIn(
                    f"work country or region is not eligible: {country}",
                    result.reasons,
                )

    def test_explicit_us_location_is_verified_without_country_metadata(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["engineer"], skills=["Python"], remote_ok=True,
            eligible_countries=["US"],
        )

        for index, location in enumerate(("Remote - United States", "Remote - California")):
            with self.subTest(location=location):
                job = Job(
                    "test", f"us-{index}", "Software Engineer", "Example",
                    f"https://example.com/us-{index}", "Python",
                    location=location, remote=True,
                )
                result = score_job(profile, job)
                self.assertTrue(result.eligible)
                self.assertEqual(result.country_verification, "verified")

    def test_spain_candidate_matches_spain_and_europe_not_us(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
        )
        jobs = {
            "spain": Job(
                "test", "spain", "Software Engineer", "Example",
                "https://example.com/spain-role", "Python", remote=True,
                country="ES", countries=["ES"],
            ),
            "europe": Job(
                "test", "europe", "Software Engineer", "Example",
                "https://example.com/europe-role", "Python", remote=True,
                regions=["EUROPE"],
            ),
            "eu": Job(
                "test", "eu", "Software Engineer", "Example",
                "https://example.com/eu-role", "Python", remote=True,
                regions=["EU"],
            ),
            "us": Job(
                "test", "us", "Software Engineer", "Example",
                "https://example.com/us-role", "Python", remote=True,
                country="US", countries=["US"],
            ),
        }

        self.assertTrue(score_job(profile, jobs["spain"]).eligible)
        self.assertTrue(score_job(profile, jobs["europe"]).eligible)
        self.assertTrue(score_job(profile, jobs["eu"]).eligible)
        self.assertFalse(score_job(profile, jobs["us"]).eligible)

    def test_multi_country_role_matches_any_candidate_eligible_country(self):
        role = Job(
            "test", "multi", "Software Engineer", "Example",
            "https://example.com/multi", "Python", remote=True,
            country="US", countries=["US", "ES"],
        )
        spain_profile = CandidateProfile(
            name="Candidate", target_titles=["engineer"], skills=["Python"],
            remote_ok=True, eligible_countries=["ES"],
        )

        result = score_job(spain_profile, role)

        self.assertTrue(result.eligible)
        self.assertEqual(result.country_verification, "verified")

    def test_remote_role_with_unknown_country_requires_us_confirmation(self):
        profile = CandidateProfile(
            name="Candidate", target_titles=["architect"], skills=["Python"], remote_ok=True,
            eligible_countries=["US"],
        )
        job = Job("test", "country-unknown", "Architect", "Example", "https://example.com/6", "Python", remote=True)
        result = score_job(profile, job)
        self.assertTrue(result.eligible)
        self.assertEqual(result.country_verification, "unknown")
        self.assertEqual(result.score_breakdown["preferences"], 0)
        self.assertIn("work country is not stated; confirm US eligibility", result.reasons)

    def test_geographic_match_is_separate_from_work_authorization(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
            work_authorized_countries=["US"],
            consider_sponsorship_roles=True,
        )
        job = Job(
            "test",
            "spain-auth",
            "Software Engineer",
            "Example",
            "https://example.com/spain-auth",
            "Python",
            remote=True,
            country="ES",
        )

        result = score_job(profile, job)

        self.assertTrue(result.eligible)
        self.assertEqual(result.country_verification, "verified")
        self.assertEqual(
            result.authorization_verification,
            "sponsorship_required",
        )
        self.assertEqual(result.score_breakdown["preferences"], 0)

    def test_authorized_country_matches_broader_hiring_region(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
            work_authorized_countries=["Spain"],
        )
        job = Job(
            "test",
            "emea-auth",
            "Software Engineer",
            "Example",
            "https://example.com/emea-auth",
            "Python",
            remote=True,
            regions=["EMEA"],
        )

        result = score_job(profile, job)

        self.assertTrue(result.eligible)
        self.assertEqual(result.country_verification, "verified")
        self.assertEqual(result.authorization_verification, "verified")

    def test_sponsorship_preference_can_exclude_unverified_country(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
            work_authorized_countries=["US"],
            consider_sponsorship_roles=False,
        )
        job = Job(
            "test",
            "spain-no-sponsor",
            "Software Engineer",
            "Example",
            "https://example.com/spain-no-sponsor",
            "Python",
            remote=True,
            country="ES",
        )

        result = score_job(profile, job)

        self.assertFalse(result.eligible)
        self.assertEqual(result.authorization_verification, "ineligible")
        self.assertIn(
            "work authorization does not match and sponsorship roles are disabled",
            result.reasons,
        )

    def test_explicit_no_sponsorship_excludes_unverified_country(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
            work_authorized_countries=["US"],
            consider_sponsorship_roles=True,
        )
        job = Job(
            "test",
            "spain-sponsor-unavailable",
            "Software Engineer",
            "Example",
            "https://example.com/spain-sponsor-unavailable",
            "Python. We do not offer visa sponsorship for this position.",
            remote=True,
            country="ES",
        )

        result = score_job(profile, job)

        self.assertFalse(result.eligible)
        self.assertEqual(result.authorization_verification, "ineligible")
        self.assertIn(
            "work authorization does not match and the posting says sponsorship is unavailable",
            result.reasons,
        )

    def test_incidental_sponsorship_wording_does_not_exclude_role(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
            work_authorized_countries=["US"],
            consider_sponsorship_roles=True,
        )
        job = Job(
            "test",
            "spain-sponsor-incidental",
            "Software Engineer",
            "Example",
            "https://example.com/spain-sponsor-incidental",
            "We evaluate candidates without regard to sponsorship history.",
            remote=True,
            country="ES",
        )

        result = score_job(profile, job)

        self.assertTrue(result.eligible)
        self.assertEqual(
            result.authorization_verification,
            "sponsorship_required",
        )

    def test_common_employer_sponsorship_language_is_classified(self):
        profile = CandidateProfile(
            name="Candidate",
            target_titles=["engineer"],
            skills=["Python"],
            remote_ok=True,
            eligible_countries=["Spain"],
            work_authorized_countries=["US"],
            consider_sponsorship_roles=True,
        )
        descriptions = {
            "future employer sponsorship": (
                "Candidates must be authorized to work in Spain without now or in "
                "the future requiring employer sponsorship.",
                False,
                "ineligible",
            ),
            "visa transfer unavailable": (
                "We are unable to sponsor or take over sponsorship of an employment visa "
                "at this time.",
                False,
                "ineligible",
            ),
            "conditional sponsorship": (
                "Visa sponsorship may be available for exceptionally qualified candidates.",
                True,
                "sponsorship_required",
            ),
        }

        for index, (label, (description, eligible, verification)) in enumerate(
            descriptions.items()
        ):
            with self.subTest(label=label):
                job = Job(
                    "test",
                    f"sponsorship-wording-{index}",
                    "Software Engineer",
                    "Example",
                    f"https://example.com/sponsorship-wording-{index}",
                    description,
                    remote=True,
                    country="ES",
                )
                result = score_job(profile, job)
                self.assertEqual(result.eligible, eligible)
                self.assertEqual(result.authorization_verification, verification)


if __name__ == "__main__":
    unittest.main()
