"""Contract tests using fictional calendar exports; no accounts or network required."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check-deadlines/scripts/read_calendars.py"


def calendar(*events):
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Deadline tests//EN",
        *events, "END:VCALENDAR", "",
    ])


def event(uid, start, extra=""):
    return "\r\n".join([
        "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20261024T230000Z",
        f"DTSTART{start}", f"SUMMARY:{uid}", extra, "END:VEVENT",
    ])


class CalendarReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def source(self, text, source_id="school", **fields):
        path = self.root / f"{source_id}.ics"
        path.write_text(text, encoding="utf-8")
        return {
            "id": source_id, "label": source_id, "kind": "ics_file",
            "status": "ready", "path": str(path), **fields,
        }

    def run_reader(self, sources, *args, expected_exit=0, **profile_fields):
        path = self.root / "sources.json"
        profile = {
            "version": 1, "timezone": "America/Chicago", "default_days": 7,
            "sources": sources, **profile_fields,
        }
        path.write_text(json.dumps(profile), encoding="utf-8")
        before = path.read_bytes()
        run = subprocess.run([
            sys.executable, str(SCRIPT), "--config", str(path),
            "--now", "2026-10-24T18:00:00-05:00", *args,
        ], capture_output=True, text=True)
        self.assertEqual(run.returncode, expected_exit, run.stderr or run.stdout)
        self.assertEqual(path.read_bytes(), before, "Checking must not rewrite the profile")
        return json.loads(run.stdout)

    def test_window_uses_start_not_end_and_preserves_date_precision(self):
        source = self.source(calendar(
            event("earlier", ":20261024T150000Z"),
            event("essay", ":20261026T045900Z"),
            event("today-unspecified", ";VALUE=DATE:20261024"),
            event("boundary", ":20261031T050000Z"),
            event("old-start", ":20261023T120000Z", "DTEND:20261027T120000Z"),
        ))
        result = self.run_reader([source])
        self.assertEqual([(r["title"], r["due"], r["precision"]) for r in result["candidates"]], [
            ("today-unspecified", "2026-10-24", "date"),
            ("essay", "2026-10-25T23:59:00-05:00", "datetime"),
        ])
        self.assertEqual(result["window"]["end_exclusive"], "2026-10-31T00:00:00-05:00")
        self.assertEqual(result["sources"][0]["freshness"], "snapshot")

    def test_recurring_exceptions_cancellation_and_dst(self):
        source = self.source(calendar(
            event("daily", ";TZID=America/Chicago:20261030T090000",
                  "RRULE:FREQ=DAILY;COUNT=5\r\nEXDATE;TZID=America/Chicago:20261031T090000"),
            event("daily", ";TZID=America/Chicago:20261101T090000",
                  "RECURRENCE-ID;TZID=America/Chicago:20261101T090000\r\nSTATUS:CANCELLED"),
            event("daily", ";TZID=America/Chicago:20261102T110000",
                  "RECURRENCE-ID;TZID=America/Chicago:20261102T090000"),
        ))
        result = self.run_reader([source], "--now", "2026-10-30T00:00:00-05:00")
        self.assertEqual([r["due"] for r in result["candidates"]], [
            "2026-10-30T09:00:00-05:00", "2026-11-02T11:00:00-06:00",
            "2026-11-03T09:00:00-06:00",
        ])

    def test_floating_time_uses_source_zone_with_visible_basis(self):
        source = self.source(calendar(event("floating", ":20261026T000000")), timezone="America/New_York")
        row = self.run_reader([source])["candidates"][0]
        self.assertEqual(row["due"], "2026-10-25T23:00:00-05:00")
        self.assertEqual(row["timezone_basis"], "source_timezone")

    def test_unknown_explicit_timezone_is_not_silently_replaced(self):
        source = self.source(calendar(event("unknown", ";TZID=Imaginary/Moon:20261026T120000")))
        result = self.run_reader([source])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["sources"][0]["status"], "error")
        self.assertEqual(result["sources"][0]["error"], "unresolved_timezone")

    def test_html_failure_keeps_other_source_and_is_not_empty_success(self):
        result = self.run_reader([
            self.source("<html>Please sign in</html>", "broken"),
            self.source(calendar(event("good", ":20261026T045900Z")), "ok"),
        ])
        self.assertEqual([r["title"] for r in result["candidates"]], ["good"])
        self.assertEqual([s["status"] for s in result["sources"]], ["error", "ok"])

    def test_private_feed_url_is_not_exposed_on_failure(self):
        result = self.run_reader([{
            "id": "private", "label": "Private calendar", "kind": "ics", "status": "ready",
            "feed_url": "http://example.invalid/private-secret-token/calendar.ics",
        }])
        self.assertEqual(result["sources"][0]["status"], "error")
        self.assertNotIn("private-secret-token", json.dumps(result))

    def test_connector_and_pending_sources_remain_unread(self):
        result = self.run_reader([
            {"id": "work", "label": "Work", "kind": "calendar", "status": "ready", "calendar_id": "private-id"},
            {"id": "other", "label": "Other", "kind": "ics", "status": "pending"},
        ])
        self.assertEqual([s["status"] for s in result["sources"]], ["needs_connector", "pending"])
        self.assertEqual(result["candidates"], [])
        self.assertNotIn("private-id", json.dumps(result))

    def test_events_remain_candidates_and_submission_stays_unknown(self):
        source = self.source(calendar(event(
            "Office hours", ":20261025T150000Z", "URL:https://lms.example.edu/calendar?event=22",
        )))
        row = self.run_reader([source])["candidates"][0]
        self.assertEqual(row["title"], "Office hours")
        self.assertEqual(row["submission_status"], "unknown")
        self.assertEqual(row["url"], "https://lms.example.edu/calendar?event=22")

    def test_unsupported_todos_report_a_coverage_gap(self):
        source = self.source(calendar("BEGIN:VTODO\r\nUID:task\r\nDUE:20261026T045900Z\r\nSUMMARY:Task\r\nEND:VTODO"))
        result = self.run_reader([source])
        self.assertIn("vtodo_requires_separate_reader", result["sources"][0]["warnings"])

    def test_invalid_profile_fails_without_traceback_or_silent_default(self):
        result = self.run_reader([], expected_exit=2, timezone="Missing/Timezone")
        self.assertEqual(result["error"], "invalid_profile")

    def test_absolute_instants_survive_the_repeated_dst_hour(self):
        for header in ("", "X-WR-TIMEZONE:America/Chicago\r\n"):
            with self.subTest(header=header):
                body = calendar(
                    event("first-hour", ":20261101T064500Z"),
                    event("second-hour-early", ":20261101T071500Z"),
                    event("second-hour-late", ":20261101T074500Z"),
                ).replace("BEGIN:VEVENT", header + "BEGIN:VEVENT", 1)
                result = self.run_reader([self.source(body)], "--now", "2026-11-01T01:30:00-05:00", "--days", "1")
                self.assertEqual([r["due"] for r in result["candidates"]], [
                    "2026-11-01T01:45:00-05:00",
                    "2026-11-01T01:15:00-06:00",
                    "2026-11-01T01:45:00-06:00",
                ])

    def test_webcal_secret_is_redacted_in_https_form_too(self):
        result = self.run_reader([
            {"id": "private", "label": "Private", "kind": "ics", "status": "disabled",
             "feed_url": "webcal://example.invalid/private-secret-token/calendar.ics"},
            self.source(calendar(event("mirrored", ":20261026T045900Z",
                "URL:https://example.invalid/private-secret-token/calendar.ics"))),
        ])
        self.assertNotIn("private-secret-token", json.dumps(result))

    def test_utc_recurrence_stays_at_the_same_utc_hour_across_dst(self):
        source = self.source(calendar(event("utc-series", ":20261030T140000Z", "RRULE:FREQ=DAILY;COUNT=5")))
        result = self.run_reader([source], "--now", "2026-10-30T00:00:00-05:00")
        self.assertEqual([r["due"] for r in result["candidates"]], [
            "2026-10-30T09:00:00-05:00", "2026-10-31T09:00:00-05:00",
            "2026-11-01T08:00:00-06:00", "2026-11-02T08:00:00-06:00",
            "2026-11-03T08:00:00-06:00",
        ])

    def test_explicit_range_can_cross_the_repeated_hour(self):
        source = self.source(calendar(event("future", ":20261101T071500Z")))
        result = self.run_reader([source], "--start", "2026-11-01T01:30:00-05:00",
                                 "--end", "2026-11-01T01:20:00-06:00")
        self.assertEqual([r["due"] for r in result["candidates"]], ["2026-11-01T01:15:00-06:00"])

    def test_date_only_survives_a_positive_offset_partial_day_window(self):
        source = self.source(calendar(event("date-only", ";VALUE=DATE:20261024")))
        result = self.run_reader([source], "--start", "2026-10-24T01:00:00+09:00",
                                 "--end", "2026-10-24T05:00:00+09:00", timezone="Asia/Tokyo")
        self.assertEqual([(r["due"], r["precision"]) for r in result["candidates"]], [("2026-10-24", "date")])


if __name__ == "__main__":
    unittest.main()
