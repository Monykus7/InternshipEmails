import json
import os
import unittest
from email import message_from_string
from email.header import decode_header, make_header
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import config
import main
from core.deduplicator import deduplicate, merge_job_details
from core.details import parse_details, enrich_jobs
from core.email_sender import send_digest
from core.filter import filter_jobs, is_us_location
from core.text import html_text
from core.freshness import filter_recent_jobs
from scrapers.simplify_jobs import fetch_simplify_jobs


def job(**overrides):
    return {
        "title": "Software Engineer Intern - Summer 2027",
        "company": "Example",
        "location": "Seattle, WA",
        "url": "https://example.com/jobs/1",
        "source": "Test",
        "description": "Currently pursuing a Bachelor's degree in Computer Science.",
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "posting_date_source": "Test publication date",
        **overrides,
    }


class EligibilityTests(unittest.TestCase):
    def screen(self, posting, **profile):
        return filter_jobs([posting], config.KEYWORDS, "2027", "summer", {**config.APPLICANT, **profile})

    def test_full_time_and_false_intern_matches_are_excluded(self):
        for title in ("Software Engineer Full Time", "Software Engineer International", "Research Internal Auditor"):
            with self.subTest(title=title):
                self.assertEqual(self.screen(job(title=title)), [])
        self.assertTrue(self.screen(job(description="Full-time internship, 40 hours per week. Bachelor's CS students.")))

    def test_foreign_and_unknown_remote_locations_are_excluded(self):
        for location in ("London, UK", "Toronto, ON, Canada", "Bangalore, India", "Remote", "", "Georgia"):
            with self.subTest(location=location):
                self.assertFalse(is_us_location(location))
                self.assertEqual(self.screen(job(location=location)), [])
        for location in ("San Francisco, CA", "SF", "NYC", "Remote - United States", "Boston, Massachusetts"):
            self.assertTrue(self.screen(job(location=location)))

    def test_advanced_degree_requirement_in_body_and_marker(self):
        for description in ("Must be enrolled in a PhD program.", "Currently pursuing a Masters degree.", "MS required."):
            with self.subTest(description=description):
                self.assertEqual(self.screen(job(description=description)), [])
        self.assertEqual(self.screen(job(advanced_degree_required=True)), [])
        self.assertTrue(self.screen(job(description="Pursuing a Bachelor's or Master's degree in Computer Science.")))
        self.assertTrue(self.screen(job(description="Bachelor's in Computer Science required. PhD preferred.")))

    def test_required_other_major_and_compatible_alternatives(self):
        self.assertEqual(self.screen(job(description="Must be pursuing a degree in Mechanical Engineering.")), [])
        self.assertTrue(self.screen(job(description="Pursuing a degree in Computer Science or Electrical Engineering.")))
        self.assertEqual(self.screen(job(description="Degree in Mechanical Engineering or a related field.")), [])

    def test_season_and_year_but_not_graduation_year(self):
        self.assertEqual(self.screen(job(title="Software Engineer Intern - Fall 2027")), [])
        self.assertEqual(self.screen(job(title="Software Engineer Intern - Summer 2026")), [])
        self.assertEqual(self.screen(job(title="Software Engineer Intern", description="Internship for summer 2026.")), [])
        self.assertTrue(self.screen(job(description="Bachelor's CS students graduating in 2028 or 2029.")))

    def test_unavailable_requirements_are_excluded(self):
        self.assertEqual(self.screen(job(description="")), [])
        self.assertTrue(self.screen(job(description=""), require_description=False)[0]["eligibility_notes"])

    def test_authorization_only_excludes_known_mismatches(self):
        self.assertEqual(self.screen(job(no_sponsorship=True), needs_sponsorship=True), [])
        self.assertEqual(self.screen(job(us_citizenship_required=True), us_citizen=False), [])
        self.assertTrue(self.screen(job(no_sponsorship=True))[0]["eligibility_notes"])

    def test_non_citizen_rejects_citizenship_wording_in_either_order(self):
        for description in ("Requires current U.S. citizenship due to contract requirements.",
                            "U.S. citizenship is required.", "Must be a US citizen."):
            self.assertEqual(self.screen(job(description=description)), [])
        self.assertTrue(self.screen(job(description="US citizenship is not required.")))
        self.assertTrue(self.screen(job(description="We do not require U.S. citizenship.")))
        self.assertTrue(self.screen(job(description="No US citizenship required.")))

    def test_av_export_and_contract_requirements_are_screened(self):
        description = (
            "Applicants must qualify as a U.S. person under the ITAR and EAR, or be approved for an export license. "
            "A U.S. person is a citizen, lawful permanent resident, or protected individual. "
            "Some positions will require current U.S. Citizenship due to contract requirements."
        )
        self.assertEqual(self.screen(job(description=description)), [])
        self.assertEqual(self.screen(job(description="Applicants must qualify as a U.S. person under ITAR.")), [])
        self.assertTrue(self.screen(job(description="Applicants must qualify as a U.S. person under ITAR."), us_person=True))
        self.assertEqual(self.screen(job(description="This position requires U.S. citizenship."), us_person=True), [])

    def test_hyphenated_internship_is_matched(self):
        self.assertTrue(self.screen(job(title="Software-Engineering Internship - Summer 2027")))


class ScraperTests(unittest.TestCase):
    @patch("scrapers.simplify_jobs.requests.get")
    def test_direct_links_and_eligibility_markers(self, get):
        get.return_value.text = '''<table>
        <tr><td><a href="https://company.example">Example</a> 🛂 🇺🇸</td>
        <td>Software Engineer Intern 🎓</td><td>Seattle, WA</td>
        <td><a href="https://employer.example/jobs/1?utm_source=Simplify">Apply</a>
        <a href="https://simplify.jobs/p/1?utm_source=GHList">Simplify</a></td></tr>
        <tr><td>↳</td><td>Software Engineer Intern</td><td>Seattle, WA</td>
        <td>🔒 <a href="https://employer.example/jobs/2">Apply</a></td></tr>
        <tr><td>↳</td><td>Software Engineer Intern</td><td>Seattle, WA</td>
        <td><a href="https://employer.example/jobs/3">Apply</a></td></tr></table>'''
        jobs = fetch_simplify_jobs(config.KEYWORDS["roles"])
        self.assertEqual(len(jobs), 2)
        self.assertTrue(jobs[0]["url"].startswith("https://employer.example/"))
        self.assertTrue(jobs[0]["advanced_degree_required"])
        self.assertTrue(jobs[0]["no_sponsorship"])
        self.assertTrue(jobs[0]["us_citizenship_required"])
        self.assertEqual(jobs[1]["company"], "Example")
        self.assertFalse(jobs[1]["advanced_degree_required"])
        self.assertNotIn("posted_at", jobs[0])

    def test_structured_description_and_location(self):
        posting = {"@type": "JobPosting", "description": "<p>Must be pursuing a <b>Masters</b> degree.</p>",
                   "jobLocation": {"address": {"addressLocality": "Seattle", "addressRegion": "WA", "addressCountry": "US"}}}
        details = parse_details('<script type="application/ld+json">' + json.dumps({"@graph": [posting]}) + '</script>')
        self.assertIn("Masters degree", details["description"])
        self.assertEqual(details["location"], "Seattle, WA, US")
        self.assertEqual(filter_jobs([job(**details)], config.KEYWORDS, "2027", "summer", config.APPLICANT), [])
        self.assertIn("Bachelor's or Master's", html_text("<p>Pursuing a <b>Bachelor's</b> or <b>Master's</b> degree.</p>"))

    def test_employer_original_date_is_used_not_modification(self):
        posting = {"@type": "JobPosting", "description": "Bachelor's CS internship.",
                   "datePosted": "2026-09-01T10:00:00Z", "dateModified": "2026-10-08T10:00:00Z"}
        details = parse_details('<script type="application/ld+json">' + json.dumps(posting) + '</script>')
        self.assertEqual(details["posted_at"], posting["datePosted"])
        self.assertEqual(filter_recent_jobs([job(**details)], now=datetime(2026, 10, 8, 20, tzinfo=timezone.utc)), [])

    @patch("core.details.requests.get")
    def test_existing_requirements_still_retrieve_missing_posting_date(self, get):
        get.return_value.status_code = 200
        get.return_value.text = '<script type="application/ld+json">' + json.dumps({
            "@type": "JobPosting", "datePosted": "2026-10-08T10:00:00Z",
        }) + '</script>'
        enriched = enrich_jobs([job(posted_at=None)])[0]
        get.assert_called_once()
        self.assertEqual(enriched["posted_at"], "2026-10-08T10:00:00Z")
        self.assertTrue(enriched["description"])


class FreshnessTests(unittest.TestCase):
    NOW = datetime(2026, 10, 8, 20, tzinfo=timezone.utc)

    def test_rolling_twenty_four_hours_and_timezone_offsets(self):
        for posted in ("2026-10-07T20:00:00Z", "2026-10-08T19:30:00Z", "2026-10-08T05:00:00-07:00"):
            self.assertEqual(len(filter_recent_jobs([job(posted_at=posted)], now=self.NOW)), 1)
        for posted in ("2026-10-07T19:59:59Z", "2026-10-08T20:00:01Z"):
            self.assertEqual(filter_recent_jobs([job(posted_at=posted)], now=self.NOW), [])

    def test_unknown_invalid_and_first_seen_are_not_fresh(self):
        for posted in (None, "", "bad-date"):
            self.assertEqual(filter_recent_jobs([job(posted_at=posted, first_seen=self.NOW.isoformat(),
                                                    updated_at=self.NOW.isoformat(), source_age="0d")], now=self.NOW), [])

    def test_date_only_is_conservative(self):
        self.assertEqual(len(filter_recent_jobs([job(posted_at="2026-10-08")], now=self.NOW)), 1)
        self.assertEqual(filter_recent_jobs([job(posted_at="2026-10-07")], now=self.NOW), [])


class DeliveryTests(unittest.TestCase):
    def run_main(self, jobs, fail=False):
        sources = {name: False for name in config.SOURCES}
        sources["simplify_jobs"] = True
        with patch.object(config, "SOURCES", sources), \
             patch("main.fetch_simplify_jobs", return_value=jobs), \
             patch("main.enrich_jobs", side_effect=lambda candidates: candidates), \
             patch("main.load_seen", return_value={}), \
             patch("main.save_seen") as save, \
             patch("main.send_digest", side_effect=RuntimeError("SMTP failed") if fail else None) as send:
            if fail:
                with self.assertRaisesRegex(RuntimeError, "SMTP failed"):
                    main.main()
            else:
                self.assertEqual(main.main(), 0)
            return send, save

    def test_sends_zero_or_less_than_twenty(self):
        for postings in ([], [job()]):
            send, save = self.run_main(postings)
            self.assertEqual(len(send.call_args.args[0]), len(postings))
            save.assert_called_once()

    def test_overflow_is_not_marked_delivered(self):
        postings = [job(company=f"Company {i}", url=f"https://example.com/jobs/{i}") for i in range(25)]
        send, save = self.run_main(postings)
        delivered = send.call_args.args[0]
        self.assertEqual(len(delivered), 20)
        seen = save.call_args.args[0]
        self.assertEqual(len(seen), 20)
        self.assertEqual(len(deduplicate(postings, seen)[0]), 5)

    def test_smtp_failure_does_not_write_cache(self):
        _, save = self.run_main([job()], fail=True)
        save.assert_not_called()

    def test_stale_or_undated_jobs_are_not_emailed_or_cached(self):
        send, save = self.run_main([
            job(),
            job(url="https://example.com/jobs/old", posted_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()),
            job(url="https://example.com/jobs/unknown", posted_at=None, source_age="0d"),
        ])
        self.assertEqual(len(send.call_args.args[0]), 1)
        self.assertEqual(len(save.call_args.args[0]), 1)

    def test_deduplicate_is_pure_and_ignores_tracking_only(self):
        seen = {}
        postings = [job(url="https://example.com/jobs/1?utm_source=Simplify"), job()]
        fresh, updated = deduplicate(postings, seen)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(seen, {})
        self.assertEqual(len(updated), 1)
        # Workday/Greenhouse job-identifying query parameters must survive.
        self.assertEqual(len(deduplicate([job(url="https://example.com/jobs?gh_jid=1"),
                                          job(url="https://example.com/jobs?gh_jid=2")], {})[0]), 2)

    def test_merge_keeps_employer_requirements_and_community_restrictions(self):
        merged = merge_job_details([
            job(url="https://example.com/jobs/1?utm_source=Simplify", description="", advanced_degree_required=True, cohort_year="2027"),
            job(),
        ])
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0]["description"])
        self.assertTrue(merged[0]["advanced_degree_required"])
        self.assertEqual(merged[0]["cohort_year"], "2027")

    def test_duplicate_sources_cannot_make_an_old_posting_new(self):
        merged = merge_job_details([
            job(posted_at="2026-09-01T00:00:00Z", posting_date_source="Employer datePosted"),
            job(posted_at="2026-10-08T10:00:00Z", posting_date_source="Another source"),
            job(posted_at=None),
        ])
        self.assertEqual(merged[0]["posted_at"], "2026-09-01T00:00:00Z")
        self.assertEqual(merged[0]["posting_date_source"], "Employer datePosted")

    @patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "test-password"})
    @patch("core.email_sender.smtplib.SMTP_SSL")
    def test_empty_email_has_html_and_plain_text(self, smtp):
        send_digest([], "to@example.com", "from@example.com")
        raw = smtp.return_value.__enter__.return_value.sendmail.call_args.args[2]
        message = message_from_string(raw)
        self.assertIn("0 new listings", str(make_header(decode_header(message["Subject"]))))
        for part in message.get_payload():
            self.assertIn("No new matching internships", part.get_payload(decode=True).decode())


if __name__ == "__main__":
    unittest.main()
